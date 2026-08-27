"""Kennisbank: verwijzingen herkennen, opzoeken en op geldigheid toetsen."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import Source, SourceKind, Verification

# --- Herkenning van verwijzingen in een binnengekomen brief ---------------

ECLI_RE = re.compile(r"\bECLI:[A-Z]{2}:[A-Z0-9]{1,10}:\d{4}:[A-Z0-9.\-]{1,20}\b", re.IGNORECASE)

# "artikel 6:217 BW", "art. 3:308 lid 2 BW", "artikel 26 Elektriciteitswet 1998"
ARTIKEL_RE = re.compile(
    r"\b(?:art(?:ikel|\.)?)\s*"
    r"(?P<nummer>\d+[a-z]?(?::\d+[a-z]?)?)"
    r"(?P<lid>\s*(?:lid|sub)\s*[\w\d]+)?"
    r"\s*(?:van\s+(?:de|het)\s+)?"
    r"(?P<wet>BW|Burgerlijk\s+Wetboek|Awb|Algemene\s+wet\s+bestuursrecht|Energiewet|"
    r"Elektriciteitswet(?:\s*1998)?|Gaswet|Warmtewet|AVG|GDPR|Grondwet|Wetboek\s+van\s+Koophandel)?",
    re.IGNORECASE,
)

WET_ALIASSEN = {
    "bw": "BW",
    "burgerlijk wetboek": "BW",
    "awb": "Awb",
    "algemene wet bestuursrecht": "Awb",
    "energiewet": "Energiewet",
    "elektriciteitswet": "Elektriciteitswet 1998",
    "elektriciteitswet 1998": "Elektriciteitswet 1998",
    "gaswet": "Gaswet",
    "warmtewet": "Warmtewet",
    "avg": "AVG",
    "gdpr": "AVG",
    "grondwet": "Grondwet",
}


@dataclass(frozen=True)
class Verwijzing:
    ruw: str
    soort: str  # ecli | wetsartikel
    genormaliseerd: str
    context: str


def _context(tekst: str, start: int, eind: int, marge: int = 160) -> str:
    fragment = tekst[max(0, start - marge) : min(len(tekst), eind + marge)]
    return " ".join(fragment.split())


def vind_verwijzingen(tekst: str) -> list[Verwijzing]:
    """Haalt elke aangehaalde vindplaats uit de brief van de klant.

    Dit is de basis voor de bronnencontrole: elke verwijzing die niet blijkt te
    bestaan, is een concreet en verifieerbaar punt in het antwoord.
    """
    gevonden: dict[str, Verwijzing] = {}

    for match in ECLI_RE.finditer(tekst):
        ruw = match.group(0)
        genormaliseerd = ruw.upper()
        gevonden.setdefault(
            genormaliseerd,
            Verwijzing(ruw, "ecli", genormaliseerd, _context(tekst, *match.span())),
        )

    for match in ARTIKEL_RE.finditer(tekst):
        wet_ruw = (match.group("wet") or "").strip().lower()
        wet = WET_ALIASSEN.get(" ".join(wet_ruw.split()), "")
        if not wet:
            continue  # zonder wetsnaam is een nummer niet te verifieren
        nummer = match.group("nummer")
        genormaliseerd = f"{wet} {nummer}"
        gevonden.setdefault(
            genormaliseerd,
            Verwijzing(
                match.group(0).strip(), "wetsartikel", genormaliseerd, _context(tekst, *match.span())
            ),
        )

    return list(gevonden.values())


# --- Opzoeken in de kennisbank -------------------------------------------


def _vindplaats_varianten(genormaliseerd: str) -> list[str]:
    """`BW 6:217` -> zoekvarianten zoals ze in `Source.vindplaats` staan."""
    delen = genormaliseerd.split(" ", 1)
    if len(delen) != 2:
        return [genormaliseerd]
    wet, nummer = delen
    return [f"art. {nummer} {wet}", f"artikel {nummer} {wet}", f"{wet} {nummer}", nummer]


def zoek_bron(session: Session, verwijzing: Verwijzing) -> Source | None:
    if verwijzing.soort == "ecli":
        return session.scalar(
            select(Source).where(Source.vindplaats.ilike(verwijzing.genormaliseerd))
        )
    varianten = _vindplaats_varianten(verwijzing.genormaliseerd)
    stmt = select(Source).where(or_(*[Source.vindplaats.ilike(v) for v in varianten]))
    return session.scalar(stmt)


def geldig_op(bron: Source, peildatum: date | None) -> bool:
    """Was deze bron geldig op de peildatum van de vordering?

    Zonder deze toets citeert de agent na 1 januari 2026 vrolijk artikelen uit de
    ingetrokken Elektriciteitswet 1998 - of andersom, de Energiewet bij een
    vordering uit 2023.
    """
    if peildatum is None:
        return bron.geldig_tot is None  # zonder peildatum alleen huidig recht
    if bron.geldig_vanaf and peildatum < bron.geldig_vanaf:
        return False
    if bron.geldig_tot and peildatum > bron.geldig_tot:
        return False
    return True


def haal_bronnen(
    session: Session,
    categorieen: list[str],
    *,
    peildatum: date | None = None,
    alleen_citeerbaar: bool = True,
    limiet: int = 12,
) -> list[Source]:
    """Bronnen die bij deze bezwaarcategorieen horen, gefilterd op geldigheid."""
    if not categorieen:
        return []

    stmt = select(Source)
    if alleen_citeerbaar:
        stmt = stmt.where(Source.verificatie.in_([Verification.BEVESTIGD, Verification.HANDMATIG]))
    else:
        stmt = stmt.where(Source.verificatie != Verification.NIET_GEVONDEN)

    kandidaten = list(session.scalars(stmt))
    gewenst = set(categorieen)

    def score(bron: Source) -> tuple[int, int, int]:
        overlap = len(gewenst & set(bron.categorieen or []))
        # Eigen werkinstructies en geaccordeerde uitspraken gaan voor op ruwe wetteksten.
        voorkeur = {SourceKind.EIGEN: 3, SourceKind.JURISPRUDENTIE: 2, SourceKind.WET: 2, SourceKind.REGELING: 1}
        handmatig = 1 if bron.verificatie == Verification.HANDMATIG else 0
        return (overlap, voorkeur.get(bron.soort, 0), handmatig)

    treffers = [b for b in kandidaten if gewenst & set(b.categorieen or [])]
    treffers = [b for b in treffers if geldig_op(b, peildatum)]
    if alleen_citeerbaar:
        treffers = [b for b in treffers if b.citeerbaar]
    treffers.sort(key=score, reverse=True)
    return treffers[:limiet]


def citeerbare_keys(bronnen: list[Source]) -> set[str]:
    return {b.key for b in bronnen if b.citeerbaar}
