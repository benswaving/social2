"""Binnenkomst: van bestand of e-mail naar een dossier in de database."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import AuditEvent, CaseStatus, Objection
from .imap_client import Bericht, haal_berichten
from .pdf_text import extraheer

logger = logging.getLogger(__name__)


def _bestandshash(pad: Path) -> str:
    return hashlib.sha256(pad.read_bytes()).hexdigest()


def bestaat_al(session: Session, bron_id: str) -> Objection | None:
    return session.scalar(select(Objection).where(Objection.bron_id == bron_id))


def uit_bestand(
    session: Session,
    pad: str | Path,
    *,
    kanaal: str = "upload",
    bron_id: str | None = None,
    afzender_naam: str | None = None,
    afzender_email: str | None = None,
    extra_tekst: str = "",
) -> Objection:
    pad = Path(pad)
    bron_id = bron_id or f"bestand:{_bestandshash(pad)}"

    bestaand = bestaat_al(session, bron_id)
    if bestaand is not None:
        logger.info("Bestand al eerder ingelezen (%s); dossier %s", pad.name, bestaand.id)
        return bestaand

    extractie = extraheer(pad)
    tekst = "\n\n".join(deel for deel in (extra_tekst.strip(), extractie.tekst.strip()) if deel)

    objection = Objection(
        kanaal=kanaal,
        bron_id=bron_id,
        bestandspad=str(pad),
        ruwe_tekst=tekst,
        tekst_kwaliteit=extractie.kwaliteit,
        afzender_naam=afzender_naam,
        afzender_email=afzender_email,
        status=CaseStatus.NIEUW if tekst.strip() else CaseStatus.MISLUKT,
        analyse_fout=None if tekst.strip() else (extractie.toelichting or "Geen tekst gevonden."),
    )
    session.add(objection)
    session.flush()
    session.add(
        AuditEvent(
            objection_id=objection.id,
            actor="systeem",
            actie="intake",
            detail={"kanaal": kanaal, "bestand": pad.name, "kwaliteit": extractie.kwaliteit},
        )
    )
    session.commit()
    return objection


def uit_tekst(session: Session, tekst: str, *, afzender_naam: str | None = None) -> Objection:
    bron_id = f"tekst:{hashlib.sha256(tekst.encode()).hexdigest()}"
    bestaand = bestaat_al(session, bron_id)
    if bestaand is not None:
        return bestaand

    objection = Objection(
        kanaal="api",
        bron_id=bron_id,
        ruwe_tekst=tekst,
        tekst_kwaliteit="goed",
        afzender_naam=afzender_naam,
        status=CaseStatus.NIEUW,
    )
    session.add(objection)
    session.flush()
    session.add(AuditEvent(objection_id=objection.id, actor="systeem", actie="intake", detail={"kanaal": "api"}))
    session.commit()
    return objection


def uit_bericht(session: Session, bericht: Bericht) -> Objection:
    bestaand = bestaat_al(session, bericht.message_id)
    if bestaand is not None:
        return bestaand

    # Een bijlage bevat meestal de eigenlijke brief; de mailtekst is dan begeleidend.
    if bericht.bijlagen:
        objection = uit_bestand(
            session,
            bericht.bijlagen[0],
            kanaal="imap",
            bron_id=bericht.message_id,
            afzender_naam=bericht.afzender_naam,
            afzender_email=bericht.afzender_email,
            extra_tekst=f"Onderwerp: {bericht.onderwerp}\n\n{bericht.tekst}",
        )
        return objection

    objection = Objection(
        kanaal="imap",
        bron_id=bericht.message_id,
        ruwe_tekst=f"Onderwerp: {bericht.onderwerp}\n\n{bericht.tekst}".strip(),
        tekst_kwaliteit="goed",
        afzender_naam=bericht.afzender_naam,
        afzender_email=bericht.afzender_email,
        status=CaseStatus.NIEUW,
    )
    session.add(objection)
    session.flush()
    session.add(
        AuditEvent(
            objection_id=objection.id,
            actor="systeem",
            actie="intake",
            detail={"kanaal": "imap", "onderwerp": bericht.onderwerp},
        )
    )
    session.commit()
    return objection


def haal_postbus_op(session: Session, maximum: int | None = None) -> list[Objection]:
    settings = get_settings()
    berichten = haal_berichten(maximum or settings.imap_max_per_run)
    return [uit_bericht(session, bericht) for bericht in berichten]
