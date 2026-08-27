"""API voor de kennisbank: eigen bronnen aanleveren en kandidaten accorderen."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_session
from ..knowledge.loader import load_taxonomie
from ..models import AuditEvent, Source, SourceKind, Verification
from ..schemas import BronIn, BronUit

router = APIRouter(prefix="/api/kennisbank", tags=["kennisbank"])


@router.get("/taxonomie")
def taxonomie() -> dict:
    tax = load_taxonomie()
    return {
        "versie": tax.versie,
        "categorieen": [
            {
                "sleutel": c.sleutel,
                "label": c.label,
                "prior": c.prior,
                "altijd_naar_mens": c.escalatie,
                "standpunt": c.kern,
                "interne_aanwijzing": c.instructie,
                "feitencheck": list(c.feitencheck),
            }
            for c in tax.categorieen.values()
        ],
    }


@router.get("/bronnen", response_model=list[BronUit])
def bronnen(
    session: Session = Depends(get_session),
    categorie: str | None = Query(default=None),
    alleen_citeerbaar: bool = Query(default=False),
    limiet: int = Query(default=200, le=1000),
) -> list[Source]:
    stmt = select(Source).order_by(Source.soort, Source.key).limit(limiet)
    if alleen_citeerbaar:
        stmt = stmt.where(Source.verificatie.in_([Verification.BEVESTIGD, Verification.HANDMATIG]))
    resultaat = list(session.scalars(stmt))
    if categorie:
        resultaat = [b for b in resultaat if categorie in (b.categorieen or [])]
    return resultaat


@router.post("/bronnen", response_model=BronUit, status_code=201)
def bron_toevoegen(payload: BronIn, session: Session = Depends(get_session)) -> Source:
    """Eigen materiaal: werkinstructies, standaardparagrafen, ACM-voorwaarden.

    `geaccordeerd` betekent dat een medewerker de inhoud heeft nagekeken. Alleen
    dan mag de agent ernaar verwijzen in een uitgaande brief.
    """
    if session.scalar(select(Source).where(Source.key == payload.key)):
        raise HTTPException(status_code=409, detail=f"Bron met key '{payload.key}' bestaat al")

    onbekend = set(payload.categorieen) - set(load_taxonomie().categorieen)
    if onbekend:
        raise HTTPException(status_code=422, detail=f"Onbekende categorieen: {sorted(onbekend)}")

    try:
        soort = SourceKind(payload.soort)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Onbekende soort: {payload.soort}") from exc

    bron = Source(
        key=payload.key,
        soort=soort,
        titel=payload.titel,
        vindplaats=payload.vindplaats,
        tekst=payload.tekst,
        samenvatting=payload.samenvatting,
        url=payload.url,
        categorieen=payload.categorieen,
        verificatie=Verification.HANDMATIG if payload.geaccordeerd else Verification.ONGEVERIFIEERD,
        verificatie_toelichting=(
            "Aangeleverd en geaccordeerd door de afdeling"
            if payload.geaccordeerd
            else "Aangeleverd; nog te accorderen"
        ),
        laatst_gecontroleerd=datetime.now(timezone.utc),
        tags=["eigen"],
        toegevoegd_door="afdeling",
    )
    session.add(bron)
    session.add(AuditEvent(actor="afdeling", actie="bron_toegevoegd", detail={"key": payload.key}))
    session.commit()
    session.refresh(bron)
    return bron


@router.post("/bronnen/{key}/accorderen", response_model=BronUit)
def accorderen(
    key: str,
    beoordelaar: str = Body(..., embed=True),
    toelichting: str | None = Body(default=None, embed=True),
    session: Session = Depends(get_session),
) -> Source:
    """Een jurist zet een kandidaat op geaccordeerd; pas dan is hij citeerbaar."""
    bron = session.scalar(select(Source).where(Source.key == key))
    if bron is None:
        raise HTTPException(status_code=404, detail="Bron niet gevonden")
    if bron.verificatie == Verification.NIET_GEVONDEN:
        raise HTTPException(
            status_code=409,
            detail="Deze vindplaats bestaat niet bij de officiele bron en kan niet geaccordeerd worden.",
        )

    bron.verificatie = Verification.HANDMATIG
    bron.verificatie_toelichting = toelichting or f"Geaccordeerd door {beoordelaar}"
    bron.laatst_gecontroleerd = datetime.now(timezone.utc)
    session.add(
        AuditEvent(actor=beoordelaar, actie="bron_geaccordeerd", detail={"key": key})
    )
    session.commit()
    session.refresh(bron)
    return bron


@router.delete("/bronnen/{key}/accordering", response_model=BronUit)
def accordering_intrekken(
    key: str,
    beoordelaar: str = Body(..., embed=True),
    session: Session = Depends(get_session),
) -> Source:
    bron = session.scalar(select(Source).where(Source.key == key))
    if bron is None:
        raise HTTPException(status_code=404, detail="Bron niet gevonden")
    bron.verificatie = Verification.ONGEVERIFIEERD
    bron.verificatie_toelichting = f"Accordering ingetrokken door {beoordelaar}"
    session.add(AuditEvent(actor=beoordelaar, actie="bron_accordering_ingetrokken", detail={"key": key}))
    session.commit()
    session.refresh(bron)
    return bron
