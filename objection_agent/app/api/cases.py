"""API voor de werkvoorraad: bezwaren inlezen, bekijken, verwerken en goedkeuren."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.pipeline import verwerk_bezwaar
from ..config import get_settings
from ..db import get_session
from ..ingest.intake import uit_bestand, uit_tekst
from ..models import AuditEvent, CaseStatus, Draft, Objection
from ..schemas import BezwaarDetail, BezwaarKort, ConceptUit, GoedkeuringIn, TekstIn

router = APIRouter(prefix="/api/bezwaren", tags=["bezwaren"])

TOEGESTANE_TYPES = {".pdf", ".txt", ".eml", ".md"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


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
def via_tekst(payload: TekstIn, session: Session = Depends(get_session)) -> Objection:
    objection = uit_tekst(session, payload.tekst, afzender_naam=payload.afzender_naam)
    if payload.direct_verwerken:
        verwerk_bezwaar(session, objection)
        session.refresh(objection)
    return objection


@router.post("/upload", response_model=BezwaarDetail, status_code=201)
async def via_upload(
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
    if objection.status == CaseStatus.NIEUW:
        verwerk_bezwaar(session, objection)
        session.refresh(objection)
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
