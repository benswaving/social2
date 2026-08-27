"""API voor het ophalen uit de gedeelde postbus."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..agent.pipeline import verwerk_bezwaar
from ..db import get_session
from ..ingest.intake import haal_postbus_op
from ..models import CaseStatus

router = APIRouter(prefix="/api/postbus", tags=["postbus"])


@router.post("/ophalen")
def ophalen(
    maximum: int | None = Query(default=None, le=200),
    direct_verwerken: bool = Query(default=True),
    session: Session = Depends(get_session),
) -> dict:
    """Haalt ongelezen berichten op en zet ze in de werkvoorraad.

    Deze route verstuurt niets en verwijdert niets; berichten worden alleen
    gelezen, gemarkeerd en gekopieerd naar de verwerkt-map.
    """
    try:
        bezwaren = haal_postbus_op(session, maximum)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    verwerkt = 0
    mislukt: list[dict] = []
    if direct_verwerken:
        for bezwaar in bezwaren:
            if bezwaar.status != CaseStatus.NIEUW:
                continue
            try:
                verwerk_bezwaar(session, bezwaar)
                verwerkt += 1
            except Exception as exc:  # verwerking van een dossier mag de run niet stoppen
                mislukt.append({"bezwaar_id": bezwaar.id, "fout": str(exc)})

    return {
        "opgehaald": len(bezwaren),
        "verwerkt": verwerkt,
        "mislukt": mislukt,
        "bezwaar_ids": [b.id for b in bezwaren],
    }
