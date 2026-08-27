"""Laadt de seed-bestanden (taxonomie, wetsartikelen, jurisprudentieprofielen)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Source, SourceKind, Verification

SEED_DIR = Path(__file__).resolve().parent / "seed"


@dataclass(frozen=True)
class Categorie:
    sleutel: str
    label: str
    prior: float
    escalatie: bool
    kern: str          # klantgerichte tekst: mag letterlijk in de brief
    instructie: str = ""  # interne aanwijzing: mag NOOIT in de brief
    feitencheck: tuple[str, ...] = ()


@dataclass(frozen=True)
class EscalatieSignaal:
    sleutel: str
    label: str
    patronen: tuple[str, ...]


@dataclass(frozen=True)
class Taxonomie:
    versie: str
    categorieen: dict[str, Categorie]
    escalatie_signalen: tuple[EscalatieSignaal, ...] = ()
    ai_signalen: tuple[dict[str, Any], ...] = field(default=())

    def get(self, sleutel: str) -> Categorie:
        return self.categorieen.get(sleutel) or self.categorieen["overig"]

    @property
    def sleutels(self) -> list[str]:
        return list(self.categorieen)


def _read(name: str) -> dict[str, Any]:
    with (SEED_DIR / name).open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache
def load_taxonomie() -> Taxonomie:
    raw = _read("taxonomie.yaml")
    categorieen = {
        sleutel: Categorie(
            sleutel=sleutel,
            label=item.get("label", sleutel),
            prior=float(item.get("prior", 0.4)),
            escalatie=bool(item.get("escalatie", False)),
            kern=(item.get("kern") or "").strip(),
            instructie=(item.get("instructie") or "").strip(),
            feitencheck=tuple(item.get("feitencheck") or ()),
        )
        for sleutel, item in (raw.get("categorieen") or {}).items()
    }
    signalen = tuple(
        EscalatieSignaal(
            sleutel=item["sleutel"],
            label=item.get("label", item["sleutel"]),
            patronen=tuple(item.get("patronen") or ()),
        )
        for item in (raw.get("escalatie_signalen") or [])
    )
    return Taxonomie(
        versie=raw.get("versie", "onbekend"),
        categorieen=categorieen,
        escalatie_signalen=signalen,
        ai_signalen=tuple(raw.get("ai_signalen") or ()),
    )


@lru_cache
def load_wetsartikelen() -> dict[str, Any]:
    return _read("wetsartikelen.yaml")


@lru_cache
def load_jurisprudentieprofielen() -> dict[str, Any]:
    return _read("jurisprudentie.yaml")


def _as_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def seed_sources(session: Session, *, overschrijf: bool = False) -> dict[str, int]:
    """Zet de seed-items in de kennisbank, allemaal als `ongeverifieerd`.

    De inhoudelijke tekst komt pas binnen bij de synchronisatie met de officiele
    bronnen. Tot die tijd is een item niet citeerbaar.
    """
    data = load_wetsartikelen()
    wetten = {w["afkorting"]: w for w in data.get("wetten", []) if w.get("afkorting")}
    toegevoegd = bijgewerkt = 0

    def _upsert(key: str, **velden: Any) -> None:
        nonlocal toegevoegd, bijgewerkt
        bestaand = session.scalar(select(Source).where(Source.key == key))
        if bestaand is None:
            session.add(Source(key=key, **velden))
            toegevoegd += 1
        elif overschrijf and bestaand.toegevoegd_door == "seed":
            # Handmatige aanvullingen van de afdeling nooit overschrijven.
            for naam, waarde in velden.items():
                setattr(bestaand, naam, waarde)
            bijgewerkt += 1

    for artikel in data.get("artikelen", []):
        wet = wetten.get(artikel.get("wet") or "", {})
        _upsert(
            artikel["key"],
            soort=SourceKind.WET,
            titel=artikel.get("onderwerp", "").strip(),
            vindplaats=artikel["vindplaats"],
            samenvatting=(artikel.get("onderwerp") or "").strip(),
            geldig_vanaf=_as_date(wet.get("geldig_vanaf")),
            geldig_tot=_as_date(wet.get("geldig_tot")),
            vervangen_door=wet.get("vervangen_door"),
            verificatie=Verification.ONGEVERIFIEERD,
            verificatie_toelichting="Seed; tekst nog niet opgehaald bij de officiele bron.",
            categorieen=list(artikel.get("categorieen") or []),
            tags=["seed", "wet"],
            toegevoegd_door="seed",
        )

    for regeling in data.get("regelingen", []):
        _upsert(
            regeling["key"],
            soort=SourceKind.REGELING,
            titel=regeling["titel"],
            vindplaats=regeling["titel"],
            url=regeling.get("url"),
            samenvatting=(
                f"Aan te leveren door {regeling.get('aanleveren_door', 'de afdeling')}. "
                "Niet citeerbaar zolang de tekst ontbreekt."
            ),
            verificatie=Verification.ONGEVERIFIEERD,
            categorieen=list(regeling.get("categorieen") or []),
            tags=["seed", "regeling", "aan-te-leveren"],
            toegevoegd_door="seed",
        )

    session.commit()
    return {"toegevoegd": toegevoegd, "bijgewerkt": bijgewerkt}


def now() -> datetime:
    return datetime.now(timezone.utc)
