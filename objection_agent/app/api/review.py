"""Server-rendered review-UI voor de medewerker."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agent.pipeline import verwerk_bezwaar
from ..db import get_session
from ..ingest.intake import uit_tekst
from ..models import AuditEvent, CaseStatus, Draft, Objection, Source, Verification

router = APIRouter(tags=["ui"], include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def werkvoorraad(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    bezwaren = list(
        session.scalars(select(Objection).order_by(Objection.ontvangen_op.desc()).limit(100))
    )
    return templates.TemplateResponse(
        request=request, name="werkvoorraad.html", context={"bezwaren": bezwaren}
    )


@router.get("/bezwaar/{bezwaar_id}", response_class=HTMLResponse)
def bezwaar(bezwaar_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    objection = session.get(Objection, bezwaar_id)
    if objection is None:
        raise HTTPException(status_code=404, detail="Bezwaar niet gevonden")
    concept = objection.concepten[-1] if objection.concepten else None
    return templates.TemplateResponse(
        request=request, name="bezwaar.html", context={"b": objection, "concept": concept}
    )


@router.get("/kennisbank", response_class=HTMLResponse)
def kennisbank(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    bronnen = list(session.scalars(select(Source).order_by(Source.soort, Source.key)))
    citeerbaar = sum(1 for b in bronnen if b.citeerbaar)
    auto_gemapt = sum(1 for b in bronnen if "auto-gemapt" in (b.tags or []) and not b.citeerbaar)
    return templates.TemplateResponse(
        request=request,
        name="kennisbank.html",
        context={"bronnen": bronnen, "citeerbaar": citeerbaar, "auto_gemapt": auto_gemapt},
    )


def _bron(session: Session, key: str) -> Source:
    bron = session.scalar(select(Source).where(Source.key == key))
    if bron is None:
        raise HTTPException(status_code=404, detail="Bron niet gevonden")
    return bron


@router.post("/ui/kennisbank/{key}/accorderen")
def ui_accorderen(
    key: str, beoordelaar: str = Form(...), session: Session = Depends(get_session)
) -> RedirectResponse:
    bron = _bron(session, key)
    if bron.verificatie == Verification.NIET_GEVONDEN:
        raise HTTPException(
            status_code=409,
            detail="Deze vindplaats bestaat niet bij de officiele bron en kan niet geaccordeerd worden.",
        )
    bron.verificatie = Verification.HANDMATIG
    bron.verificatie_toelichting = f"Geaccordeerd door {beoordelaar}"
    bron.laatst_gecontroleerd = datetime.now(timezone.utc)
    session.add(AuditEvent(actor=beoordelaar, actie="bron_geaccordeerd", detail={"key": key}))
    session.commit()
    return RedirectResponse(url="/kennisbank", status_code=303)


@router.post("/ui/kennisbank/{key}/intrekken")
def ui_intrekken(
    key: str, beoordelaar: str = Form(default="onbekend"), session: Session = Depends(get_session)
) -> RedirectResponse:
    bron = _bron(session, key)
    bron.verificatie = Verification.ONGEVERIFIEERD
    bron.verificatie_toelichting = f"Accordering ingetrokken door {beoordelaar}"
    session.add(AuditEvent(actor=beoordelaar, actie="bron_accordering_ingetrokken", detail={"key": key}))
    session.commit()
    return RedirectResponse(url="/kennisbank", status_code=303)


@router.post("/ui/tekst")
def ui_tekst(tekst: str = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    objection = uit_tekst(session, tekst)
    if objection.status == CaseStatus.NIEUW:
        try:
            verwerk_bezwaar(session, objection)
        except ValueError:
            pass
    return RedirectResponse(url=f"/bezwaar/{objection.id}", status_code=303)


@router.post("/ui/bezwaar/{bezwaar_id}/verwerk")
def ui_verwerk(bezwaar_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    objection = session.get(Objection, bezwaar_id)
    if objection is None:
        raise HTTPException(status_code=404, detail="Bezwaar niet gevonden")
    try:
        verwerk_bezwaar(session, objection)
    except ValueError:
        pass
    return RedirectResponse(url=f"/bezwaar/{bezwaar_id}", status_code=303)


@router.post("/ui/bezwaar/{bezwaar_id}/concept/{concept_id}/goedkeuren")
def ui_goedkeuren(
    bezwaar_id: int,
    concept_id: int,
    beoordelaar: str = Form(...),
    tekst: str = Form(...),
    notitie: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    objection = session.get(Objection, bezwaar_id)
    draft = session.get(Draft, concept_id)
    if objection is None or draft is None or draft.objection_id != bezwaar_id:
        raise HTTPException(status_code=404, detail="Niet gevonden")

    aangepast = tekst.strip() != (draft.tekst or "").strip()
    if draft.geblokkeerd and not aangepast:
        raise HTTPException(
            status_code=409,
            detail="Dit concept is tegengehouden door de controle. Pas de tekst aan voordat u goedkeurt.",
        )

    draft.tekst = tekst
    draft.geblokkeerd = False
    draft.beoordelaar = beoordelaar
    draft.beoordeling_notitie = notitie or None
    draft.goedgekeurd_op = datetime.now(timezone.utc)
    objection.status = CaseStatus.GOEDGEKEURD
    session.add(
        AuditEvent(
            objection_id=bezwaar_id,
            actor=beoordelaar,
            actie="goedkeuring",
            detail={"concept_id": concept_id, "tekst_aangepast": aangepast},
        )
    )
    session.commit()
    return RedirectResponse(url=f"/bezwaar/{bezwaar_id}", status_code=303)


