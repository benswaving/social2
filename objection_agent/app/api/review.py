"""Server-rendered review-UI voor de medewerker."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..agent.pipeline import verwerk_bezwaar
from ..config import get_settings
from ..db import get_session
from ..ingest.intake import uit_tekst
from ..dossier import zoek_gerelateerd
from ..models import (
    Afloop,
    AuditEvent,
    CaseStatus,
    Draft,
    Job,
    JobStatus,
    Merit,
    Objection,
    Source,
    Verification,
)
from ..worker import meld_aan, wachtrij_standen

router = APIRouter(tags=["ui"], include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
def werkvoorraad(
    request: Request,
    status: str = "",
    kans: str = "",
    escalatie: str = "",
    termijn: str = "",
    zoek: str = "",
    session: Session = Depends(get_session),
) -> HTMLResponse:
    stmt = select(Objection).order_by(Objection.ontvangen_op.desc())

    if status:
        try:
            stmt = stmt.where(Objection.status == CaseStatus(status))
        except ValueError:
            pass
    if kans:
        try:
            stmt = stmt.where(Objection.globale_kans == Merit(kans))
        except ValueError:
            pass
    if escalatie == "ja":
        stmt = stmt.where(Objection.escalatie.is_(True))
    elif escalatie == "nee":
        stmt = stmt.where(Objection.escalatie.is_(False))
    if termijn == "te_laat":
        stmt = stmt.where(Objection.reactie_uiterlijk < date.today()).where(
            Objection.status.notin_([CaseStatus.GOEDGEKEURD, CaseStatus.VERZONDEN])
        )
    elif termijn == "deze_week":
        stmt = stmt.where(Objection.reactie_uiterlijk <= date.today() + timedelta(days=7)).where(
            Objection.status.notin_([CaseStatus.GOEDGEKEURD, CaseStatus.VERZONDEN])
        )
    if zoek:
        naald = f"%{zoek.strip()}%"
        stmt = stmt.where(
            or_(
                Objection.dossier_ref.ilike(naald),
                Objection.ean.ilike(naald),
                Objection.afzender_naam.ilike(naald),
                Objection.afzender_email.ilike(naald),
            )
        )

    bezwaren = list(session.scalars(stmt.limit(200)))

    # Tellingen over de hele voorraad, niet over de filterselectie: een medewerker
    # wil zien hoeveel er nog open staat, niet hoeveel er in beeld is.
    tellingen = {
        "totaal": session.scalar(select(func.count()).select_from(Objection)) or 0,
        "escalatie": session.scalar(
            select(func.count()).select_from(Objection).where(Objection.escalatie.is_(True))
        )
        or 0,
        "open": session.scalar(
            select(func.count())
            .select_from(Objection)
            .where(Objection.status.notin_([CaseStatus.GOEDGEKEURD, CaseStatus.VERZONDEN]))
        )
        or 0,
        "mislukt": session.scalar(
            select(func.count()).select_from(Objection).where(Objection.status == CaseStatus.MISLUKT)
        )
        or 0,
        "te_laat": session.scalar(
            select(func.count())
            .select_from(Objection)
            .where(Objection.reactie_uiterlijk < date.today())
            .where(Objection.status.notin_([CaseStatus.GOEDGEKEURD, CaseStatus.VERZONDEN]))
        )
        or 0,
    }
    wachtrij = wachtrij_standen(session)

    return templates.TemplateResponse(
        request=request,
        name="werkvoorraad.html",
        context={
            "bezwaren": bezwaren,
            "tellingen": tellingen,
            "wachtrij": wachtrij,
            "filters": {
                "status": status,
                "kans": kans,
                "escalatie": escalatie,
                "termijn": termijn,
                "zoek": zoek,
            },
            "statussen": [s.value for s in CaseStatus],
            "kansen": [m.value for m in Merit],
        },
    )


@router.get("/bezwaar/{bezwaar_id}", response_class=HTMLResponse)
def bezwaar(bezwaar_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    objection = session.get(Objection, bezwaar_id)
    if objection is None:
        raise HTTPException(status_code=404, detail="Bezwaar niet gevonden")
    concept = objection.concepten[-1] if objection.concepten else None
    wacht = session.scalar(
        select(Job)
        .where(Job.objection_id == objection.id)
        .where(Job.status.in_([JobStatus.WACHTEND, JobStatus.BEZIG]))
    )
    return templates.TemplateResponse(
        request=request,
        name="bezwaar.html",
        context={
            "b": objection,
            "concept": concept,
            "gerelateerd": zoek_gerelateerd(session, objection),
            "wacht": wacht,
            "afloopwaarden": [a.value for a in Afloop],
        },
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
        if get_settings().wachtrij_actief:
            meld_aan(session, objection.id)
        else:
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
    if get_settings().wachtrij_actief:
        meld_aan(session, objection.id)
    else:
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




@router.post("/ui/bezwaar/{bezwaar_id}/afloop")
def ui_afloop(
    bezwaar_id: int,
    afloop: str = Form(...),
    vastgelegd_door: str = Form(...),
    notitie: str = Form(default=""),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    objection = session.get(Objection, bezwaar_id)
    if objection is None:
        raise HTTPException(status_code=404, detail="Bezwaar niet gevonden")
    try:
        objection.afloop = Afloop(afloop)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Onbekende afloop: {afloop}") from exc
    objection.afloop_notitie = notitie or None
    objection.afloop_vastgelegd_op = datetime.now(timezone.utc)
    session.add(
        AuditEvent(
            objection_id=bezwaar_id,
            actor=vastgelegd_door,
            actie="afloop_vastgelegd",
            detail={"afloop": afloop},
        )
    )
    session.commit()
    return RedirectResponse(url=f"/bezwaar/{bezwaar_id}", status_code=303)
