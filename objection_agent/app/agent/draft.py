"""Stap 4: het conceptantwoord opstellen."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from ..knowledge.loader import load_taxonomie
from ..models import Source
from .analyse import AnalyseUitkomst
from .guardrails import GuardrailRapport, controleer_concept
from .llm import LLMClient, LLMOnbeschikbaar
from .verify import BESTAAT_NIET, INGETROKKEN, NIET_VAN_TOEPASSING, Bronoordeel

logger = logging.getLogger(__name__)

PROMPT_PAD = Path(__file__).resolve().parent / "prompts" / "concept.md"
PROMPT_VERSIE = "concept-2026-08-1"


@dataclass
class ConceptUitkomst:
    onderwerp: str
    brief: str
    gebruikte_bron_keys: list[str] = field(default_factory=list)
    openstaande_punten: list[str] = field(default_factory=list)
    rapport: GuardrailRapport = field(default_factory=GuardrailRapport)
    model: str = "offline-sjabloon"
    methode: str = "model"


def _toegestane_vindplaatsen(bronnen: list[Source], oordelen: list[Bronoordeel]) -> set[str]:
    """Wat mag de brief noemen?

    Twee dingen: bronnen uit de geverifieerde kennisbank, en de vindplaatsen die de
    klant zelf aanhaalt en die wij hebben weerlegd. Dat tweede is geen uitzondering
    op de regel maar de kern ervan - juist over een niet-bestaande uitspraak moet de
    brief iets kunnen zeggen. Verwijzingen met uitkomst `onbekend` staan er bewust
    niet bij: die hebben we niet gecontroleerd en noemen we dus niet.
    """
    toegestaan = {b.vindplaats for b in bronnen}
    for oordeel in oordelen:
        if oordeel.uitkomst in (BESTAAT_NIET, NIET_VAN_TOEPASSING, INGETROKKEN):
            toegestaan.add(oordeel.verwijzing.genormaliseerd)
            toegestaan.add(oordeel.verwijzing.ruw)
    return toegestaan


def _bronnenblok(bronnen: list[Source]) -> str:
    if not bronnen:
        return "(geen geverifieerde bronnen beschikbaar - schrijf de redenering zonder vindplaats)"
    regels = []
    for bron in bronnen:
        samenvatting = (bron.samenvatting or bron.titel or "").strip().replace("\n", " ")
        regels.append(f"- key={bron.key} | vindplaats: {bron.vindplaats} | {samenvatting[:400]}")
    return "\n".join(regels)


def _argumentenblok(analyse: AnalyseUitkomst) -> str:
    taxonomie = load_taxonomie()
    regels = []
    for index, argument in enumerate(analyse.argumenten, start=1):
        categorie = taxonomie.get(argument.categorie)
        regels.append(
            json.dumps(
                {
                    "nr": index,
                    "categorie": argument.categorie,
                    "categorie_label": categorie.label,
                    "stelling_klant": argument.stelling,
                    "citaat": argument.citaat,
                    "beoordeling": argument.merit,
                    "score": argument.merit_score,
                    "onderbouwing": argument.onderbouwing,
                    "standpunt_afdeling": categorie.kern,
                    "interne_aanwijzing_niet_in_de_brief": categorie.instructie,
                    "nog_te_controleren": argument.benodigde_feitencheck,
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(regels)


def _bronnencontroleblok(oordelen: list[Bronoordeel]) -> str:
    if not oordelen:
        return "(de klant haalt geen concrete vindplaatsen aan)"
    regels = []
    for oordeel in oordelen:
        mag_noemen = oordeel.uitkomst in (BESTAAT_NIET, NIET_VAN_TOEPASSING, INGETROKKEN)
        regels.append(
            f"- {oordeel.verwijzing.ruw}: {oordeel.uitkomst}. {oordeel.toelichting} "
            f"[{'mag in de brief benoemd worden' if mag_noemen else 'NIET in de brief benoemen'}]"
        )
    return "\n".join(regels)


def _dossierblok(analyse: AnalyseUitkomst) -> str:
    return json.dumps(
        {
            "dossier_ref": analyse.dossier_ref,
            "ean": analyse.ean,
            "afzender_naam": analyse.afzender_naam,
            "adres": analyse.adres,
            "peildatum_vordering": analyse.peildatum.isoformat() if analyse.peildatum else None,
            "samenvatting": analyse.samenvatting,
        },
        ensure_ascii=False,
        indent=2,
    )


# --- Terugval zonder taalmodel -------------------------------------------


def _sjabloonbrief(analyse: AnalyseUitkomst, bronnen: list[Source], oordelen: list[Bronoordeel]) -> str:
    taxonomie = load_taxonomie()
    per_categorie = {b.key: b for b in bronnen}
    aanhef = f"Geachte {analyse.afzender_naam}," if analyse.afzender_naam else "Geachte heer, mevrouw,"

    delen = [
        aanhef,
        "",
        "Wij hebben uw brief ontvangen waarin u bezwaar maakt tegen onze vordering "
        f"met kenmerk [[kenmerk]]{f' (EAN {analyse.ean})' if analyse.ean else ''}. "
        "Hieronder gaan wij op uw punten in.",
        "",
    ]

    for index, argument in enumerate(analyse.argumenten, start=1):
        categorie = taxonomie.get(argument.categorie)
        # Bewust niet het categorielabel als kopje: dat is een interne indeling en
        # leest voor de klant als een etiket ("pseudojuridische constructie").
        if argument.stelling and argument.stelling.strip() != categorie.label:
            delen.append(f"{index}. {argument.stelling}")
        else:
            delen.append(f"Punt {index}")
        if argument.merit in ("kansrijk", "twijfelachtig"):
            delen.append(
                "Dit punt onderzoeken wij. Wij komen hier binnen [[termijn]] schriftelijk op terug."
            )
            if argument.benodigde_feitencheck:
                delen.append("Wij controleren daarbij: " + "; ".join(argument.benodigde_feitencheck) + ".")
        else:
            delen.append(categorie.kern)
            steun = [
                b for b in bronnen if argument.categorie in (b.categorieen or []) and b.citeerbaar
            ]
            if steun:
                delen.append("Zie " + ", ".join(b.vindplaats for b in steun[:2]) + ".")
        delen.append("")

    problemen = [o for o in oordelen if o.is_probleem]
    if problemen:
        delen.append("Over de bepalingen waarnaar u verwijst")
        for oordeel in problemen:
            delen.append(f"- {oordeel.verwijzing.ruw}: {oordeel.toelichting}")
        delen.append("")

    delen += [
        "Bent u het niet eens met dit standpunt, dan kunt u binnen [[termijn]] schriftelijk "
        "reageren op [[contactgegevens]]. Komen wij er samen niet uit, dan kunt u het geschil "
        "voorleggen aan [[geschilleninstantie]].",
        "",
        "Met vriendelijke groet,",
        "[[naam medewerker]]",
        "Afdeling Aansluiting Zonder Contract",
    ]
    _ = per_categorie
    return "\n".join(delen)


def schrijf_concept(
    analyse: AnalyseUitkomst,
    bronnen: list[Source],
    oordelen: list[Bronoordeel],
    *,
    brontekst: str,
    client: LLMClient | None = None,
) -> ConceptUitkomst:
    client = client or LLMClient()
    citeerbaar = [b for b in bronnen if b.citeerbaar]
    toegestane_vindplaatsen = _toegestane_vindplaatsen(citeerbaar, oordelen)
    taxonomie = load_taxonomie()
    # De controle op "is elk argument behandeld" kijkt ook naar het standpunt van de
    # afdeling, omdat een brief het bezwaar hoort te parafraseren en niet na te praten.
    for volgnummer, argument in enumerate(analyse.argumenten, start=1):
        argument.volgnummer = volgnummer
        argument.standpunt = taxonomie.get(argument.categorie).kern
    interne_instructies = [
        taxonomie.get(a.categorie).instructie
        for a in analyse.argumenten
        if taxonomie.get(a.categorie).instructie
    ]

    if not client.beschikbaar:
        brief = _sjabloonbrief(analyse, citeerbaar, oordelen)
        rapport = controleer_concept(
            brief,
            toegestane_vindplaatsen=toegestane_vindplaatsen,
            brontekst=brontekst,
            argumenten=analyse.argumenten,
            interne_instructies=interne_instructies,
        )
        return ConceptUitkomst(
            onderwerp="Reactie op uw bezwaar",
            brief=brief,
            gebruikte_bron_keys=[b.key for b in citeerbaar],
            openstaande_punten=["Opgesteld zonder taalmodel; volledig nalopen voor verzending."],
            rapport=rapport,
            methode="sjabloon",
        )

    prompt = (
        PROMPT_PAD.read_text(encoding="utf-8")
        .replace("{{dossier}}", _dossierblok(analyse))
        .replace("{{argumenten}}", _argumentenblok(analyse))
        .replace("{{bronnencontrole}}", _bronnencontroleblok(oordelen))
        .replace("{{bronnen}}", _bronnenblok(citeerbaar))
    )

    try:
        antwoord = client.json_completion(
            systeem=(
                "Je stelt zakelijke Nederlandse brieven op voor een netbeheerder. "
                "Je verzint nooit vindplaatsen, bedragen of data. Je antwoordt met JSON."
            ),
            gebruiker=prompt,
        )
    except (LLMOnbeschikbaar, ValueError) as exc:
        logger.warning("Concept via model mislukt (%s); val terug op sjabloon", exc)
        brief = _sjabloonbrief(analyse, citeerbaar, oordelen)
        rapport = controleer_concept(
            brief,
            toegestane_vindplaatsen=toegestane_vindplaatsen,
            brontekst=brontekst,
            argumenten=analyse.argumenten,
            interne_instructies=interne_instructies,
        )
        return ConceptUitkomst(
            onderwerp="Reactie op uw bezwaar",
            brief=brief,
            gebruikte_bron_keys=[b.key for b in citeerbaar],
            openstaande_punten=[f"Model niet beschikbaar ({exc}); sjabloon gebruikt."],
            rapport=rapport,
            methode="sjabloon",
        )

    data = antwoord.data
    brief = (data.get("brief") or "").strip()
    rapport = controleer_concept(
        brief,
        toegestane_vindplaatsen=toegestane_vindplaatsen,
        brontekst=brontekst,
        argumenten=analyse.argumenten,
        interne_instructies=interne_instructies,
    )
    return ConceptUitkomst(
        onderwerp=(data.get("onderwerp") or "Reactie op uw bezwaar").strip(),
        brief=brief,
        gebruikte_bron_keys=list(data.get("gebruikte_bron_keys") or []),
        openstaande_punten=list(data.get("openstaande_punten") or []),
        rapport=rapport,
        model=antwoord.model,
        methode="model",
    )
