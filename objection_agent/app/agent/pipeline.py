"""De volledige verwerking van een bezwaar, van ruwe tekst tot conceptbrief."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..knowledge.store import haal_bronnen
from ..termijnen import bepaal_termijn
from ..models import Argument, AuditEvent, CaseStatus, ClaimedCitation, Draft, Merit, Objection
from .analyse import analyseer
from .assess import bepaal_beoordeling
from .draft import PROMPT_VERSIE, schrijf_concept
from .llm import LLMClient
from .verify import controleer_verwijzingen

logger = logging.getLogger(__name__)


def _log(session: Session, objection: Objection, actie: str, detail: dict | None = None) -> None:
    session.add(AuditEvent(objection_id=objection.id, actor="agent", actie=actie, detail=detail))


def verwerk_bezwaar(
    session: Session,
    objection: Objection,
    *,
    online: bool = True,
    client: LLMClient | None = None,
) -> Draft:
    """Analyseert, controleert, beoordeelt en schrijft een concept.

    Alles wordt opgeslagen, ook als het concept geblokkeerd wordt: de medewerker
    moet kunnen zien wat de agent dacht en waarom het is tegengehouden.
    """
    client = client or LLMClient()
    tekst = objection.ruwe_tekst or ""

    if not tekst.strip():
        objection.status = CaseStatus.MISLUKT
        objection.analyse_fout = "Geen tekst beschikbaar (mislukte extractie of leeg bestand)."
        session.commit()
        raise ValueError(objection.analyse_fout)

    # 1. Ontleden
    analyse = analyseer(tekst, client=client)
    _log(session, objection, "analyse", {"methode": analyse.methode, "argumenten": len(analyse.argumenten)})

    # 2. Bronnencontrole
    oordelen = controleer_verwijzingen(session, tekst, peildatum=analyse.peildatum, online=online)
    _log(
        session,
        objection,
        "bronnencontrole",
        {"aantal": len(oordelen), "problemen": sum(1 for o in oordelen if o.is_probleem)},
    )

    # 3. Beleid
    beoordeling = bepaal_beoordeling(tekst, analyse, oordelen)
    categorieen = sorted({a.categorie for a in analyse.argumenten})

    # 4. Bronnen ophalen voor de categorieen die in deze brief spelen
    bronnen = haal_bronnen(session, categorieen, peildatum=analyse.peildatum, alleen_citeerbaar=True)

    # 5. Concept
    concept = schrijf_concept(analyse, bronnen, oordelen, brontekst=tekst, client=client)

    # --- opslaan ---------------------------------------------------------
    objection.dossier_ref = objection.dossier_ref or analyse.dossier_ref
    objection.ean = objection.ean or analyse.ean
    objection.afzender_naam = objection.afzender_naam or analyse.afzender_naam
    objection.adres = objection.adres or analyse.adres
    objection.samenvatting = analyse.samenvatting
    objection.ai_gegenereerd_signaal = beoordeling.ai_signaal
    objection.ai_signaal_toelichting = beoordeling.ai_signaal_toelichting
    objection.globale_kans = beoordeling.globale_kans
    objection.escalatie = beoordeling.escalatie
    objection.escalatie_reden = beoordeling.escalatie_reden

    # De termijn kan korter worden zodra duidelijk is waar de brief over gaat:
    # een AVG-verzoek kent een wettelijke reactietermijn. Nooit langer maken dan
    # wat er al stond - dat zou uitstel opleveren dat niemand heeft besloten.
    termijn = bepaal_termijn(
        ontvangen_op=objection.ontvangen_op.date(),
        categorieen=categorieen,
        escalatie=beoordeling.escalatie,
    )
    if objection.reactie_uiterlijk is None or termijn.uiterlijk < objection.reactie_uiterlijk:
        objection.reactie_uiterlijk = termijn.uiterlijk
        objection.termijn_grond = termijn.grond

    objection.argumenten.clear()
    for index, argument in enumerate(analyse.argumenten, start=1):
        objection.argumenten.append(
            Argument(
                volgnummer=index,
                categorie=argument.categorie,
                stelling=argument.stelling,
                citaat=argument.citaat,
                merit=Merit(argument.merit) if argument.merit in Merit._value2member_map_ else Merit.ONBEPAALD,
                merit_score=argument.merit_score,
                onderbouwing=argument.onderbouwing,
                benodigde_feitencheck=argument.benodigde_feitencheck,
                bron_keys=[
                    b.key for b in bronnen if argument.categorie in (b.categorieen or [])
                ],
            )
        )

    objection.aangehaalde_bronnen.clear()
    for oordeel in oordelen:
        objection.aangehaalde_bronnen.append(
            ClaimedCitation(
                ruwe_verwijzing=oordeel.verwijzing.ruw[:512],
                soort=oordeel.verwijzing.soort,
                genormaliseerd=oordeel.verwijzing.genormaliseerd,
                context=oordeel.verwijzing.context,
                uitkomst=oordeel.uitkomst,
                toelichting=oordeel.toelichting,
                gecontroleerd_op=datetime.now(timezone.utc),
            )
        )

    versie = (max((d.versie for d in objection.concepten), default=0)) + 1
    rapport = concept.rapport.as_dict()
    rapport["openstaande_punten"] = concept.openstaande_punten
    rapport["methode"] = concept.methode

    draft = Draft(
        objection_id=objection.id,
        versie=versie,
        onderwerp=concept.onderwerp,
        tekst=concept.brief,
        gebruikte_bron_keys=concept.gebruikte_bron_keys,
        guardrail_rapport=rapport,
        geblokkeerd=concept.rapport.geblokkeerd,
        model=concept.model,
        prompt_versie=PROMPT_VERSIE,
    )
    session.add(draft)

    objection.status = CaseStatus.GEESCALEERD if beoordeling.escalatie else CaseStatus.CONCEPT_GEREED
    _log(
        session,
        objection,
        "concept",
        {
            "versie": versie,
            "geblokkeerd": draft.geblokkeerd,
            "escalatie": beoordeling.escalatie,
            "methode": concept.methode,
        },
    )
    session.commit()
    return draft
