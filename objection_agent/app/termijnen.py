"""Wanneer moet er uiterlijk een antwoord uit?

Drie termijnen, met verschillende status. De AVG-termijn is wettelijk: op een
inzage- of verwijderingsverzoek moet binnen een maand worden gereageerd. De
andere twee zijn een werkafspraak; ze staan in de configuratie zodat de afdeling
ze kan bijstellen zonder de code te wijzigen.

De termijn wordt bij intake gezet en bijgewerkt zodra de analyse laat zien
waarover het gaat - een dossier dat een AVG-verzoek blijkt te bevatten krijgt
alsnog de kortere, wettelijke termijn.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .config import get_settings

AVG_CATEGORIE = "avg_privacy"


@dataclass(frozen=True)
class Termijn:
    uiterlijk: date
    grond: str


def bepaal_termijn(
    *,
    ontvangen_op: date,
    categorieen: list[str] | None = None,
    escalatie: bool = False,
) -> Termijn:
    """De kortste termijn die van toepassing is.

    Bewust de kortste en niet de eerst passende. De AVG-termijn is een wettelijk
    maximum, geen streefdatum: een AVG-verzoek dat ook geescaleerd is, hoort niet
    langer te blijven liggen dan een gewone escalatie. Wie hier de eerste regel
    laat winnen, geeft zichzelf ongemerkt uitstel.
    """
    settings = get_settings()
    categorieen = categorieen or []

    kandidaten: list[Termijn] = [
        Termijn(
            ontvangen_op + timedelta(days=settings.termijn_standaard_dagen),
            "standaardtermijn afdeling",
        )
    ]
    if AVG_CATEGORIE in categorieen:
        kandidaten.append(
            Termijn(
                ontvangen_op + timedelta(days=settings.termijn_avg_dagen),
                "wettelijke reactietermijn AVG-verzoek",
            )
        )
    if escalatie:
        kandidaten.append(
            Termijn(
                ontvangen_op + timedelta(days=settings.termijn_escalatie_dagen),
                "geescaleerd dossier",
            )
        )

    return min(kandidaten, key=lambda t: t.uiterlijk)
