"""API voor de werkvoorraad: bezwaren inlezen, bekijken, verwerken en goedkeuren."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.pipeline import verwerk_bezwaar
from ..config import get_settings
from ..worker import meld_aan
from ..db import get_session
from ..ingest.intake import uit_bestand, uit_tekst
from ..models import Afloop, AuditEvent, CaseStatus, Draft, Objection
from ..schemas import AfloopIn, BezwaarDetail, BezwaarKort, ConceptUit, GoedkeuringIn, TekstIn
from ..dossier import zoek_gerelateerd

router = APIRouter(prefix="/api/bezwaren", tags=["bezwaren"])

TOEGESTANE_TYPES = {".pdf", ".txt", ".eml", ".md"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def _verwerk_of_meld_aan(session: Session, objection: Objection, response: Response) -> None:
    """Verwerkt meteen, of zet het dossier in de wachtrij.

    Met een taalmodel duurt analyseren te lang voor een HTTP-verzoek. Staat de
    wachtrij aan, dan antwoordt deze route met 202: het dossier is aangenomen en
    een werker pakt het op.
    """
    if get_settings().wachtrij_actief:
        meld_aan(session, objection.id)
        response.status_code = 202
        return
    try:
        verwerk_bezwaar(session, objection)
    except ValueError:
        pass  # de fout staat al op het dossier
    session.refresh(objection)


def _haal(session: Session, bezwaar_id: int) -> Objection:
    objection = session.get(Objection, bezwaar_id)
    if objection is None:
        raise HTTPException(status_code=404, detail="Bezwaar niet gevonden")
    return objection


@router.get("", response_model=list[BezwaarKort])
def lijst(
    session: Session = Depends(get_session),
    status: str | None = Query(default=None),
    alleen_escalatie: bool = Query(default=False),
    limiet: int = Query(default=50, le=200),
) -> list[Objection]:
    stmt = select(Objection).order_by(Objection.ontvangen_op.desc()).limit(limiet)
    if status:
        stmt = stmt.where(Objection.status == CaseStatus(status))
    if alleen_escalatie:
        stmt = stmt.where(Objection.escalatie.is_(True))
    return list(session.scalars(stmt))


@router.get("/{bezwaar_id}", response_model=BezwaarDetail)
def detail(bezwaar_id: int, session: Session = Depends(get_session)) -> Objection:
    return _haal(session, bezwaar_id)


@router.post("/tekst", response_model=BezwaarDetail, status_code=201)
def via_tekst(
    payload: TekstIn, response: Response, session: Session = Depends(get_session)
) -> Objection:
    objection = uit_tekst(session, payload.tekst, afzender_naam=payload.afzender_naam)
    if objection.concepten:
        # Deze brief was al bekend; geen nieuw dossier en dus geen 201.
        response.status_code = 200
        return objection
    if payload.direct_verwerken:
        _verwerk_of_meld_aan(session, objection, response)
    return objection


@router.post("/upload", response_model=BezwaarDetail, status_code=201)
async def via_upload(
    response: Response,
    bestand: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> Objection:
    settings = get_settings()
    naam = bestand.filename or "bezwaar"
    suffix = ("." + naam.rsplit(".", 1)[-1].lower()) if "." in naam else ""
    if suffix not in TOEGESTANE_TYPES:
        raise HTTPException(
            status_code=415, detail=f"Bestandstype {suffix or 'onbekend'} wordt niet ondersteund"
        )

    inhoud = await bestand.read()
    if len(inhoud) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Bestand is groter dan 25 MB")

    digest = hashlib.sha256(inhoud).hexdigest()
    doel = settings.upload_dir / f"{digest[:16]}{suffix}"
    doel.write_bytes(inhoud)

    objection = uit_bestand(session, doel, kanaal="upload", bron_id=f"bestand:{digest}")
    if objection.concepten:
        response.status_code = 200  # al eerder ingelezen
        return objection
    if objection.status == CaseStatus.NIEUW:
        _verwerk_of_meld_aan(session, objection, response)
    return objection


@router.post("/{bezwaar_id}/verwerk", response_model=ConceptUit)
def opnieuw_verwerken(
    bezwaar_id: int,
    online: bool = Query(default=True, description="Bronnen live controleren bij de Rechtspraak"),
    session: Session = Depends(get_session),
) -> Draft:
    objection = _haal(session, bezwaar_id)
    try:
        return verwerk_bezwaar(session, objection, online=online)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{bezwaar_id}/concepten/{concept_id}/goedkeuren", response_model=ConceptUit)
def goedkeuren(
    bezwaar_id: int,
    concept_id: int,
    payload: GoedkeuringIn,
    session: Session = Depends(get_session),
) -> Draft:
    """Menselijke goedkeuring. Zonder deze stap verlaat een concept het systeem niet."""
    objection = _haal(session, bezwaar_id)
    draft = session.get(Draft, concept_id)
    if draft is None or draft.objection_id != objection.id:
        raise HTTPException(status_code=404, detail="Concept niet gevonden")

    if draft.geblokkeerd and not payload.aangepaste_tekst:
        raise HTTPException(
            status_code=409,
            detail=(
                "Dit concept is tegengehouden door de controle. Pas de tekst aan en lever "
                "die mee als `aangepaste_tekst`, of los de bevindingen op en verwerk opnieuw."
            ),
        )

    if payload.aangepaste_tekst:
        draft.tekst = payload.aangepaste_tekst
        draft.geblokkeerd = False

    draft.beoordelaar = payload.beoordelaar
    draft.beoordeling_notitie = payload.notitie
    draft.goedgekeurd_op = datetime.now(timezone.utc)
    objection.status = CaseStatus.GOEDGEKEURD

    session.add(
        AuditEvent(
            objection_id=objection.id,
            actor=payload.beoordelaar,
            actie="goedkeuring",
            detail={
                "concept_id": draft.id,
                "versie": draft.versie,
                "tekst_aangepast": bool(payload.aangepaste_tekst),
            },
        )
    )
    session.commit()
    session.refresh(draft)
    return draft


@router.get("/{bezwaar_id}/concepten/{concept_id}/brief.txt", response_class=PlainTextResponse)
def brief_uitvoeren(
    bezwaar_id: int, concept_id: int, session: Session = Depends(get_session)
) -> PlainTextResponse:
    """De brieftekst als bestand, om in het zaaksysteem of de post te zetten.

    Alleen na goedkeuring: een concept dat nog niemand heeft gezien hoort niet
    per ongeluk in een uitgaande map te belanden.
    """
    objection = _haal(session, bezwaar_id)
    draft = session.get(Draft, concept_id)
    if draft is None or draft.objection_id != objection.id:
        raise HTTPException(status_code=404, detail="Concept niet gevonden")
    if draft.goedgekeurd_op is None:
        raise HTTPException(
            status_code=409,
            detail="Dit concept is nog niet goedgekeurd en kan niet worden uitgevoerd.",
        )

    kenmerk = objection.dossier_ref or objection.ean or f"dossier-{objection.id}"
    return PlainTextResponse(
        draft.tekst,
        headers={
            "Content-Disposition": f'attachment; filename="antwoord-{kenmerk}.txt"',
        },
    )


@router.delete("/{bezwaar_id}", status_code=204)
def verwijderen(
    bezwaar_id: int,
    actor: str = Query(..., description="wie verwijdert dit, voor het audittrail"),
    reden: str = Query(default="verzoek betrokkene"),
    session: Session = Depends(get_session),
) -> Response:
    """Verwijdert een dossier met alles eraan vast.

    Nodig voor een verwijderingsverzoek onder de AVG. Er blijft een spoor achter
    dat er is verwijderd, zonder de inhoud te bewaren.
    """
    objection = _haal(session, bezwaar_id)
    spoor = {
        "dossier_ref": objection.dossier_ref,
        "ontvangen_op": objection.ontvangen_op.isoformat(),
        "status": objection.status.value,
        "reden": reden,
    }
    session.delete(objection)
    session.add(AuditEvent(objection_id=None, actor=actor, actie="dossier_verwijderd", detail=spoor))
    session.commit()
    return Response(status_code=204)


@router.post("/{bezwaar_id}/afloop", response_model=BezwaarDetail)
def afloop_vastleggen(
    bezwaar_id: int,
    payload: AfloopIn,
    session: Session = Depends(get_session),
) -> Objection:
    """Legt vast hoe het dossier werkelijk is afgelopen.

    Zonder deze stap blijft de kansinschatting een aanname: er is dan niets om
    haar aan te toetsen. `python -m app.kalibratie` zet de inschattingen naast
    de werkelijke afloop per categorie.
    """
    objection = _haal(session, bezwaar_id)
    try:
        objection.afloop = Afloop(payload.afloop)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Onbekende afloop: {payload.afloop}") from exc

    objection.afloop_notitie = payload.notitie
    objection.afloop_vastgelegd_op = datetime.now(timezone.utc)
    session.add(
        AuditEvent(
            objection_id=objection.id,
            actor=payload.vastgelegd_door,
            actie="afloop_vastgelegd",
            detail={"afloop": objection.afloop.value},
        )
    )
    session.commit()
    session.refresh(objection)
    return objection


@router.get("/{bezwaar_id}/gerelateerd", response_model=list[BezwaarKort])
def gerelateerd(bezwaar_id: int, session: Session = Depends(get_session)) -> list[Objection]:
    """Eerdere brieven van dezelfde klant of over dezelfde aansluiting."""
    objection = _haal(session, bezwaar_id)
    return zoek_gerelateerd(session, objection)
