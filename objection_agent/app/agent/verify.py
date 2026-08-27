"""Stap 2: controleren of de bronnen waar de klant zich op beroept echt bestaan.

Dit is het antwoord op het probleem waarvoor deze agent gebouwd wordt. Brieven
die met een taalmodel zijn opgesteld verwijzen regelmatig naar artikelen en
uitspraken die er overtuigend uitzien maar niet bestaan. Zo'n verwijzing is
objectief te controleren en levert een concreet, verifieerbaar punt op in het
antwoord - anders dan een algemene stelling over de kwaliteit van de brief.

Belangrijke terughoudendheid: we schrijven alleen "deze uitspraak bestaat niet"
als we dat daadwerkelijk bij de bron hebben gecontroleerd. Konden we niet
controleren, dan blijft de uitkomst `onbekend` en zwijgt de brief erover.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import httpx
from sqlalchemy.orm import Session

from ..knowledge.rechtspraak import RechtspraakClient
from ..knowledge.store import Verwijzing, geldig_op, vind_verwijzingen, zoek_bron
from ..models import Verification

logger = logging.getLogger(__name__)

BESTAAT_EN_RELEVANT = "bestaat_en_relevant"
NIET_VAN_TOEPASSING = "niet_van_toepassing"
BESTAAT_NIET = "bestaat_niet"
INGETROKKEN = "ingetrokken"
ONBEKEND = "onbekend"

# Rechtsgebieden waar deze afdeling niets mee te maken heeft. Een beroep hierop
# is een sterk signaal dat de brief elders vandaan komt.
NIET_TOEPASSELIJK = {
    "Awb": "De netbeheerder is geen bestuursorgaan; de Algemene wet bestuursrecht is hier niet van toepassing.",
    "Grondwet": "De Grondwet richt zich tot de overheid en schept hier geen zelfstandige aanspraak.",
}


@dataclass
class Bronoordeel:
    verwijzing: Verwijzing
    uitkomst: str
    toelichting: str

    @property
    def is_probleem(self) -> bool:
        return self.uitkomst in (BESTAAT_NIET, NIET_VAN_TOEPASSING, INGETROKKEN)


def controleer_verwijzingen(
    session: Session,
    tekst: str,
    *,
    peildatum: date | None = None,
    online: bool = True,
) -> list[Bronoordeel]:
    oordelen: list[Bronoordeel] = []
    rechtspraak: RechtspraakClient | None = None

    try:
        for verwijzing in vind_verwijzingen(tekst):
            wet = verwijzing.genormaliseerd.split(" ", 1)[0]
            if verwijzing.soort == "wetsartikel" and wet in NIET_TOEPASSELIJK:
                oordelen.append(
                    Bronoordeel(verwijzing, NIET_VAN_TOEPASSING, NIET_TOEPASSELIJK[wet])
                )
                continue

            bron = zoek_bron(session, verwijzing)

            if bron is not None and bron.verificatie == Verification.NIET_GEVONDEN:
                oordelen.append(
                    Bronoordeel(
                        verwijzing,
                        BESTAAT_NIET,
                        "Deze vindplaats is opgezocht bij de officiele bron en bestaat daar niet.",
                    )
                )
                continue

            if bron is not None and bron.citeerbaar:
                if not geldig_op(bron, peildatum):
                    vervanger = f" Zie in plaats daarvan {bron.vervangen_door}." if bron.vervangen_door else ""
                    oordelen.append(
                        Bronoordeel(
                            verwijzing,
                            INGETROKKEN,
                            f"Deze bepaling gold niet op de peildatum van de vordering.{vervanger}",
                        )
                    )
                else:
                    oordelen.append(
                        Bronoordeel(
                            verwijzing,
                            BESTAAT_EN_RELEVANT,
                            f"Bestaat en is geverifieerd: {bron.titel[:200]}",
                        )
                    )
                continue

            if verwijzing.soort == "ecli" and online:
                if rechtspraak is None:
                    rechtspraak = RechtspraakClient()
                try:
                    uitspraak = rechtspraak.haal_uitspraak(verwijzing.genormaliseerd)
                except httpx.HTTPError as exc:
                    logger.warning("ECLI-controle mislukt voor %s: %s", verwijzing.genormaliseerd, exc)
                    oordelen.append(
                        Bronoordeel(
                            verwijzing,
                            ONBEKEND,
                            "Kon niet worden gecontroleerd (bron onbereikbaar). Niet in de brief noemen.",
                        )
                    )
                    continue
                if uitspraak is None:
                    oordelen.append(
                        Bronoordeel(
                            verwijzing,
                            BESTAAT_NIET,
                            "Deze ECLI is opgezocht bij de Rechtspraak en levert geen uitspraak op.",
                        )
                    )
                else:
                    oordelen.append(
                        Bronoordeel(
                            verwijzing,
                            BESTAAT_EN_RELEVANT,
                            f"Bestaat: {uitspraak.titel[:200]}. Of de uitspraak het standpunt "
                            "van de klant steunt, moet een medewerker beoordelen.",
                        )
                    )
                continue

            oordelen.append(
                Bronoordeel(
                    verwijzing,
                    ONBEKEND,
                    "Niet in de kennisbank en niet online gecontroleerd. Niet in de brief noemen.",
                )
            )
    finally:
        if rechtspraak is not None:
            rechtspraak.close()

    return oordelen


def nu() -> datetime:
    return datetime.now(timezone.utc)
