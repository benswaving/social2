"""Stap 1: de brief ontleden in losse, beoordeelbare argumenten."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml

from ..knowledge.loader import SEED_DIR, load_taxonomie
from .llm import LLMClient, LLMOnbeschikbaar

logger = logging.getLogger(__name__)

PROMPT_PAD = Path(__file__).resolve().parent / "prompts" / "analyse.md"
PROMPT_VERSIE = "analyse-2026-08-1"

EAN_RE = re.compile(r"\b(87\d{16})\b")
DOSSIER_RE = re.compile(r"(?:dossier|zaak|kenmerk|referentie)\s*[:#]?\s*([A-Z0-9][A-Z0-9\-/]{3,20})", re.I)
DATUM_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b")


@dataclass
class ArgumentUitkomst:
    categorie: str
    stelling: str
    citaat: str | None
    merit: str
    merit_score: float
    onderbouwing: str
    benodigde_feitencheck: list[str] = field(default_factory=list)


@dataclass
class AnalyseUitkomst:
    samenvatting: str
    argumenten: list[ArgumentUitkomst]
    dossier_ref: str | None = None
    ean: str | None = None
    afzender_naam: str | None = None
    adres: str | None = None
    peildatum: date | None = None
    ai_signaal: float = 0.0
    ai_signaal_toelichting: str = ""
    escalatie_aanbevolen: bool = False
    escalatie_reden: str | None = None
    methode: str = "model"  # model | regels


def _trefwoorden() -> dict[str, list[str]]:
    with (SEED_DIR / "trefwoorden.yaml").open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _velden_uit_tekst(tekst: str) -> dict[str, str | None]:
    ean = EAN_RE.search(tekst)
    dossier = DOSSIER_RE.search(tekst)
    return {
        "ean": ean.group(1) if ean else None,
        "dossier_ref": dossier.group(1) if dossier else None,
    }


def _peildatum_uit_tekst(tekst: str) -> date | None:
    """Vroegste genoemde datum: daarmee kiezen we het toepasselijke recht."""
    volledig: list[date] = []
    for dag, maand, jaar in DATUM_RE.findall(tekst):
        try:
            volledig.append(date(int(jaar), int(maand), int(dag)))
        except ValueError:
            continue
    if volledig:
        return min(volledig)

    # Alleen als er geen enkele volledige datum staat, vallen we terug op een
    # jaartal. Anders zou "2022" een datum als 12-03-2022 overstemmen.
    jaren = [int(j) for j in re.findall(r"\b(20[0-2]\d)\b", tekst)]
    return date(min(jaren), 1, 1) if jaren else None


def analyseer_met_regels(tekst: str) -> AnalyseUitkomst:
    """Terugvaloptie zonder taalmodel: trefwoorden en de priors uit de taxonomie."""
    taxonomie = load_taxonomie()
    laag = tekst.lower()
    argumenten: list[ArgumentUitkomst] = []

    for categorie, patronen in _trefwoorden().items():
        treffer = None
        for patroon in patronen:
            match = re.search(patroon, laag)
            if match:
                treffer = match
                break
        if treffer is None:
            continue
        cat = taxonomie.get(categorie)
        start = max(0, treffer.start() - 120)
        eind = min(len(tekst), treffer.end() + 200)
        argumenten.append(
            ArgumentUitkomst(
                categorie=categorie,
                stelling=cat.label,
                citaat=" ".join(tekst[start:eind].split()),
                merit=_merit_uit_score(cat.prior),
                merit_score=cat.prior,
                onderbouwing=(
                    "Ingedeeld op trefwoorden zonder taalmodel; score is de "
                    "verwachtingswaarde van deze categorie, niet een oordeel over dit dossier."
                ),
                benodigde_feitencheck=list(cat.feitencheck),
            )
        )

    if not argumenten:
        cat = taxonomie.get("overig")
        argumenten.append(
            ArgumentUitkomst(
                categorie="overig",
                stelling="Bezwaar kon niet automatisch worden ingedeeld.",
                citaat=None,
                merit="twijfelachtig",
                merit_score=cat.prior,
                onderbouwing="Geen bekende categorie herkend; handmatige beoordeling nodig.",
                benodigde_feitencheck=[],
            )
        )

    velden = _velden_uit_tekst(tekst)
    return AnalyseUitkomst(
        samenvatting="Automatische indeling op trefwoorden (geen taalmodel beschikbaar).",
        argumenten=argumenten,
        dossier_ref=velden["dossier_ref"],
        ean=velden["ean"],
        peildatum=_peildatum_uit_tekst(tekst),
        methode="regels",
        escalatie_aanbevolen=True,
        escalatie_reden="Zonder taalmodel is de indeling grof; laat een medewerker meekijken.",
    )


def _merit_uit_score(score: float) -> str:
    if score >= 0.5:
        return "kansrijk"
    if score >= 0.25:
        return "twijfelachtig"
    return "kansarm"


def _categorieblok() -> str:
    taxonomie = load_taxonomie()
    regels = []
    for cat in taxonomie.categorieen.values():
        regels.append(f"- {cat.sleutel}: {cat.label}. {cat.kern.strip()}")
    return "\n".join(regels)


def analyseer(tekst: str, client: LLMClient | None = None) -> AnalyseUitkomst:
    client = client or LLMClient()
    if not client.beschikbaar:
        return analyseer_met_regels(tekst)

    prompt = PROMPT_PAD.read_text(encoding="utf-8")
    prompt = prompt.replace("{{categorieen}}", _categorieblok()).replace("{{brief}}", tekst[:40000])

    try:
        antwoord = client.json_completion(
            systeem="Je bent een nauwkeurige juridisch analist. Je antwoordt uitsluitend met JSON.",
            gebruiker=prompt,
        )
    except (LLMOnbeschikbaar, ValueError) as exc:
        logger.warning("Analyse via model mislukt (%s); val terug op regels", exc)
        uitkomst = analyseer_met_regels(tekst)
        uitkomst.escalatie_reden = f"Modelanalyse mislukt: {exc}"
        return uitkomst

    data = antwoord.data
    taxonomie = load_taxonomie()
    argumenten = []
    for ruw in data.get("argumenten") or []:
        categorie = ruw.get("categorie") or "overig"
        if categorie not in taxonomie.categorieen:
            categorie = "overig"
        argumenten.append(
            ArgumentUitkomst(
                categorie=categorie,
                stelling=(ruw.get("stelling") or "").strip(),
                citaat=(ruw.get("citaat") or None),
                merit=ruw.get("merit") or "onbepaald",
                merit_score=float(ruw.get("merit_score") or 0.0),
                onderbouwing=(ruw.get("onderbouwing") or "").strip(),
                benodigde_feitencheck=list(ruw.get("benodigde_feitencheck") or []),
            )
        )

    if not argumenten:
        return analyseer_met_regels(tekst)

    peildatum = None
    if ruwe_datum := data.get("peildatum_vordering"):
        try:
            peildatum = date.fromisoformat(str(ruwe_datum))
        except ValueError:
            peildatum = None
    peildatum = peildatum or _peildatum_uit_tekst(tekst)

    velden = _velden_uit_tekst(tekst)
    return AnalyseUitkomst(
        samenvatting=(data.get("samenvatting") or "").strip(),
        argumenten=argumenten,
        dossier_ref=data.get("dossier_ref") or velden["dossier_ref"],
        ean=data.get("ean") or velden["ean"],
        afzender_naam=data.get("afzender_naam"),
        adres=data.get("adres"),
        peildatum=peildatum,
        ai_signaal=float(data.get("ai_signaal") or 0.0),
        ai_signaal_toelichting=(data.get("ai_signaal_toelichting") or "").strip(),
        escalatie_aanbevolen=bool(data.get("escalatie_aanbevolen")),
        escalatie_reden=data.get("escalatie_reden"),
        methode="model",
    )
