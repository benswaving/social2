"""Controles op een conceptbrief voordat een mens hem te zien krijgt.

De agent mag fouten maken; wat hij niet mag, is fouten maken die er gezaghebbend
uitzien. Deze controles blokkeren precies dat: vindplaatsen die niet uit de
geverifieerde kennisbank komen, bedragen die nergens vandaan komen, en toon die
niet past bij een brief die tot een aansprakelijkstelling kan leiden.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..knowledge.store import vind_verwijzingen

BEDRAG_RE = re.compile(r"(?:€|EUR)\s?\d[\d.,]*", re.IGNORECASE)
DATUM_RE = re.compile(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b")
PLAATSHOUDER_RE = re.compile(r"\[\[[^\]]+\]\]")

# Toon die in geen enkele uitgaande brief thuishoort.
VERBODEN_TOON = [
    (r"\bai[- ]gegenereerd", "Doet een uitspraak over hoe de brief van de klant tot stand kwam"),
    (r"\bchatgpt\b|\btaalmodel\b", "Verwijst naar het gebruik van AI door de klant"),
    (r"\bonzin\b|\bbelachelijk\b|\blachwekkend\b", "Denigrerende toon"),
    (r"\bu begrijpt het niet\b|\bkennelijk niet begrepen\b", "Betuttelende toon"),
    (r"\bwij zijn niet verplicht u te woord te staan\b", "Weigert inhoudelijke behandeling"),
]


@dataclass
class Bevinding:
    code: str
    ernst: str  # blokkerend | waarschuwing
    boodschap: str
    details: list[str] = field(default_factory=list)


@dataclass
class GuardrailRapport:
    bevindingen: list[Bevinding] = field(default_factory=list)

    @property
    def geblokkeerd(self) -> bool:
        return any(b.ernst == "blokkerend" for b in self.bevindingen)

    def as_dict(self) -> dict:
        return {
            "geblokkeerd": self.geblokkeerd,
            "bevindingen": [
                {"code": b.code, "ernst": b.ernst, "boodschap": b.boodschap, "details": b.details}
                for b in self.bevindingen
            ],
        }


def _woordreeksen(tekst: str, lengte: int = 6) -> set[str]:
    woorden = re.findall(r"[a-zà-ü]+", tekst.lower())
    return {" ".join(woorden[i : i + lengte]) for i in range(max(0, len(woorden) - lengte + 1))}


def controleer_concept(
    brief: str,
    *,
    toegestane_vindplaatsen: set[str],
    brontekst: str,
    argumenten: list,
    interne_instructies: list[str] | None = None,
) -> GuardrailRapport:
    rapport = GuardrailRapport()
    genormaliseerd_toegestaan = {v.strip().lower() for v in toegestane_vindplaatsen}

    # 1. Elke vindplaats in de brief moet uit de geverifieerde kennisbank komen.
    onbekend: list[str] = []
    for verwijzing in vind_verwijzingen(brief):
        kandidaten = {
            verwijzing.genormaliseerd.lower(),
            verwijzing.ruw.strip().lower(),
        }
        wet_nummer = verwijzing.genormaliseerd.split(" ", 1)
        if len(wet_nummer) == 2:
            wet, nummer = wet_nummer
            kandidaten |= {
                f"art. {nummer} {wet}".lower(),
                f"artikel {nummer} {wet}".lower(),
            }
        if not (kandidaten & genormaliseerd_toegestaan):
            onbekend.append(verwijzing.ruw)
    if onbekend:
        rapport.bevindingen.append(
            Bevinding(
                code="vindplaats_buiten_kennisbank",
                ernst="blokkerend",
                boodschap=(
                    "De brief verwijst naar vindplaatsen die niet uit de geverifieerde "
                    "kennisbank komen. Verwijder ze of voeg de bron geverifieerd toe."
                ),
                details=sorted(set(onbekend)),
            )
        )

    # 2. Bedragen en datums moeten uit het dossier komen, niet uit het model.
    bron_bedragen = {b.replace(" ", "") for b in BEDRAG_RE.findall(brontekst)}
    nieuwe_bedragen = [
        b for b in BEDRAG_RE.findall(brief) if b.replace(" ", "") not in bron_bedragen
    ]
    if nieuwe_bedragen:
        rapport.bevindingen.append(
            Bevinding(
                code="bedrag_niet_uit_dossier",
                ernst="blokkerend",
                boodschap="De brief noemt bedragen die niet in het dossier voorkomen.",
                details=sorted(set(nieuwe_bedragen)),
            )
        )

    bron_datums = set(DATUM_RE.findall(brontekst))
    nieuwe_datums = [d for d in DATUM_RE.findall(brief) if d not in bron_datums]
    if nieuwe_datums:
        rapport.bevindingen.append(
            Bevinding(
                code="datum_niet_uit_dossier",
                ernst="waarschuwing",
                boodschap="De brief noemt datums die niet in het dossier voorkomen.",
                details=sorted(set(nieuwe_datums)),
            )
        )

    # 3. Toon.
    toonproblemen = [
        reden for patroon, reden in VERBODEN_TOON if re.search(patroon, brief, re.IGNORECASE)
    ]
    if toonproblemen:
        rapport.bevindingen.append(
            Bevinding(
                code="toon",
                ernst="blokkerend",
                boodschap="De toon van de brief is niet passend.",
                details=toonproblemen,
            )
        )

    # 4. Is elk argument behandeld?
    onbehandeld = []
    laag = brief.lower()
    for argument in argumenten:
        kernwoorden = [
            woord
            for woord in re.findall(r"[a-zà-ü]{6,}", (argument.stelling or "").lower())
        ][:6]
        if kernwoorden and not any(woord in laag for woord in kernwoorden):
            onbehandeld.append(argument.stelling[:120])
    if onbehandeld:
        rapport.bevindingen.append(
            Bevinding(
                code="argument_niet_behandeld",
                ernst="waarschuwing",
                boodschap="Mogelijk niet op elk argument van de klant ingegaan.",
                details=onbehandeld,
            )
        )

    # 5. Interne aanwijzingen mogen de klant nooit bereiken.
    #    De taxonomie bevat regels als "nooit standaard afwijzen" en "laat een jurist
    #    meekijken". Dat is werkinstructie, geen briefinhoud.
    gelekt = []
    briefreeksen = _woordreeksen(brief)
    for instructie in interne_instructies or []:
        overlap = _woordreeksen(instructie) & briefreeksen
        if overlap:
            gelekt.append(sorted(overlap)[0])
    if gelekt:
        rapport.bevindingen.append(
            Bevinding(
                code="interne_instructie_in_brief",
                ernst="blokkerend",
                boodschap="De brief bevat tekst uit een interne werkinstructie.",
                details=gelekt,
            )
        )

    # 6. Openstaande invulplekken: geen fout, wel iets om te zien.
    plaatshouders = PLAATSHOUDER_RE.findall(brief)
    if plaatshouders:
        rapport.bevindingen.append(
            Bevinding(
                code="invulplekken",
                ernst="waarschuwing",
                boodschap="De brief bevat invulplekken die de medewerker moet aanvullen.",
                details=sorted(set(plaatshouders)),
            )
        )

    return rapport
