"""Stap 3: beleidsregels over de beoordeling heen.

Het taalmodel beoordeelt de inhoud; deze laag bepaalt wat er vervolgens mag
gebeuren. Bewust als losse, leesbare regels in plaats van als promptinstructie:
een medewerker moet kunnen nakijken waarom een dossier geescaleerd is, en die
uitleg mag niet per aanroep verschillen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..knowledge.loader import load_taxonomie
from ..models import Merit
from .analyse import AnalyseUitkomst
from .verify import BESTAAT_NIET, INGETROKKEN, NIET_VAN_TOEPASSING, Bronoordeel


@dataclass
class Beoordeling:
    globale_kans: Merit
    escalatie: bool
    escalatie_redenen: list[str] = field(default_factory=list)
    ai_signaal: float = 0.0
    ai_signaal_toelichting: str = ""
    mag_concept_genereren: bool = True

    @property
    def escalatie_reden(self) -> str | None:
        return "; ".join(self.escalatie_redenen) or None


def _merit(score: float) -> Merit:
    if score >= 0.5:
        return Merit.KANSRIJK
    if score >= 0.25:
        return Merit.TWIJFELACHTIG
    return Merit.KANSARM


def bepaal_beoordeling(
    tekst: str,
    analyse: AnalyseUitkomst,
    bronoordelen: list[Bronoordeel],
    *,
    escalatie_drempel: float = 0.35,
) -> Beoordeling:
    taxonomie = load_taxonomie()
    redenen: list[str] = []

    # 1. Tekstuele signalen die altijd om een mens vragen.
    laag = tekst.lower()
    for signaal in taxonomie.escalatie_signalen:
        for patroon in signaal.patronen:
            if re.search(patroon, laag, re.IGNORECASE):
                redenen.append(signaal.label)
                break

    # 2. Categorieen die per definitie naar een mens gaan.
    for argument in analyse.argumenten:
        categorie = taxonomie.get(argument.categorie)
        if categorie.escalatie:
            redenen.append(f"Categorie vereist juridische beoordeling: {categorie.label}")

    # 3. Een argument dat hout snijdt weegt zwaarder dan de rest van de brief.
    #    Ook als negen van de tien argumenten onzin zijn, beslist het tiende.
    hoogste = max((a.merit_score for a in analyse.argumenten), default=0.0)
    if hoogste >= escalatie_drempel:
        sterkste = max(analyse.argumenten, key=lambda a: a.merit_score)
        redenen.append(
            f"Ten minste een argument is mogelijk terecht ({taxonomie.get(sterkste.categorie).label})"
        )

    # 4. Advies van het model zelf.
    if analyse.escalatie_aanbevolen and analyse.escalatie_reden:
        redenen.append(analyse.escalatie_reden)

    # 5. Grove indeling zonder model.
    if analyse.methode == "regels":
        redenen.append("Ingedeeld zonder taalmodel; indeling is grof")

    # --- signaal dat de brief geautomatiseerd is opgesteld ---------------
    signaalscore = analyse.ai_signaal
    toelichtingen: list[str] = []
    if analyse.ai_signaal_toelichting:
        toelichtingen.append(analyse.ai_signaal_toelichting)

    verzonnen = [o for o in bronoordelen if o.uitkomst == BESTAAT_NIET]
    verkeerd_recht = [o for o in bronoordelen if o.uitkomst == NIET_VAN_TOEPASSING]
    verouderd = [o for o in bronoordelen if o.uitkomst == INGETROKKEN]

    if verzonnen:
        signaalscore = min(1.0, signaalscore + 0.45)
        toelichtingen.append(
            f"{len(verzonnen)} aangehaalde vindplaats(en) bestaan niet: "
            + ", ".join(o.verwijzing.ruw for o in verzonnen[:5])
        )
    if verkeerd_recht:
        signaalscore = min(1.0, signaalscore + 0.25)
        toelichtingen.append(
            "Beroep op recht dat hier niet geldt: "
            + ", ".join(o.verwijzing.ruw for o in verkeerd_recht[:5])
        )
    if verouderd:
        toelichtingen.append(
            "Beroep op een bepaling die op de peildatum niet (meer) gold: "
            + ", ".join(o.verwijzing.ruw for o in verouderd[:5])
        )

    return Beoordeling(
        globale_kans=_merit(hoogste),
        escalatie=bool(redenen),
        escalatie_redenen=list(dict.fromkeys(redenen)),
        ai_signaal=round(signaalscore, 2),
        ai_signaal_toelichting=" ".join(toelichtingen).strip(),
        # Ook bij escalatie maken we een concept: de medewerker begint dan niet
        # met een leeg scherm. Het concept is dan een voorstel, geen antwoord.
        mag_concept_genereren=True,
    )
