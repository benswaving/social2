"""Achtergrondverwerking.

Analyseren duurt met een taalmodel al gauw een halve minuut. Dat binnen een
HTTP-verzoek doen betekent dat een medewerker naar een laadscherm kijkt en dat
een postbusronde van vijftig berichten tegen een timeout loopt. Daarom gaat het
zware werk naar een wachtrij.

Twee manieren om de werker te draaien:

    python -m app.worker                 # los proces, aan te raden in productie
    OA_WERKER_IN_PROCES=true uvicorn ... # meelopende thread, genoeg om te beginnen

De wachtrij is een tabel in dezelfde database. Geen extra dienst om te beheren,
werkt met SQLite en Postgres, en overleeft een herstart: een taak die tijdens het
werk afbreekt blijft op `bezig` staan en wordt na de vastloper-termijn opnieuw
opgepakt.
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .config import get_settings
from .db import init_db, session_scope
from .models import AuditEvent, CaseStatus, Job, JobStatus, Objection

logger = logging.getLogger(__name__)

VERWERK_BEZWAAR = "verwerk_bezwaar"


def _nu() -> datetime:
    return datetime.now(timezone.utc)


# --- taken aanmelden ------------------------------------------------------


def meld_aan(session: Session, objection_id: int, soort: str = VERWERK_BEZWAAR) -> Job:
    """Zet een dossier in de wachtrij; dubbel aanmelden doet niets."""
    bestaand = session.scalar(
        select(Job)
        .where(Job.objection_id == objection_id)
        .where(Job.soort == soort)
        .where(Job.status.in_([JobStatus.WACHTEND, JobStatus.BEZIG]))
    )
    if bestaand is not None:
        return bestaand

    job = Job(soort=soort, objection_id=objection_id)
    session.add(job)
    session.commit()
    return job


def wachtrij_standen(session: Session) -> dict[str, int]:
    tellingen = {status.value: 0 for status in JobStatus}
    for status, aantal in session.execute(select(Job.status, func.count()).group_by(Job.status)):
        tellingen[status.value] = aantal
    return tellingen


# --- taken uitvoeren ------------------------------------------------------


def _claim(session: Session) -> Job | None:
    """Pakt één wachtende taak, zo dat twee werkers hem niet allebei krijgen.

    De UPDATE gebeurt in één opdracht met een voorwaarde op de huidige status;
    wie als tweede komt raakt nul rijen en pakt de volgende.
    """
    kandidaat = session.scalar(
        select(Job).where(Job.status == JobStatus.WACHTEND).order_by(Job.aangemaakt_op).limit(1)
    )
    if kandidaat is None:
        return None

    resultaat = session.execute(
        update(Job)
        .where(Job.id == kandidaat.id)
        .where(Job.status == JobStatus.WACHTEND)
        .values(status=JobStatus.BEZIG, gestart_op=_nu(), pogingen=Job.pogingen + 1)
    )
    session.commit()
    if resultaat.rowcount != 1:
        return None
    session.refresh(kandidaat)
    return kandidaat


def _herstel_vastlopers(session: Session, na_minuten: int) -> int:
    """Taken die op `bezig` bleven staan doordat het proces omviel."""
    grens = _nu() - timedelta(minutes=na_minuten)
    resultaat = session.execute(
        update(Job)
        .where(Job.status == JobStatus.BEZIG)
        .where(Job.gestart_op < grens)
        .values(status=JobStatus.WACHTEND, fout="Vastgelopen of afgebroken; opnieuw in de wachtrij")
    )
    session.commit()
    return resultaat.rowcount


def _voer_uit(session: Session, job: Job) -> None:
    # Late import: de pijplijn trekt het hele agentpakket mee.
    from .agent.pipeline import verwerk_bezwaar

    if job.soort != VERWERK_BEZWAAR:
        raise ValueError(f"Onbekende taaksoort: {job.soort}")

    objection = session.get(Objection, job.objection_id)
    if objection is None:
        raise ValueError(f"Dossier {job.objection_id} bestaat niet meer")

    verwerk_bezwaar(session, objection)


def draai_ronde(session: Session, *, maximum: int = 10) -> int:
    """Werkt tot `maximum` taken af. Geeft terug hoeveel er zijn opgepakt."""
    settings = get_settings()
    _herstel_vastlopers(session, settings.werker_vastloper_minuten)

    gedaan = 0
    while gedaan < maximum:
        job = _claim(session)
        if job is None:
            break
        gedaan += 1
        try:
            _voer_uit(session, job)
        except Exception as exc:  # één kapot dossier mag de rij niet stoppen
            logger.exception("Taak %s mislukt", job.id)
            session.rollback()
            job.fout = f"{exc.__class__.__name__}: {exc}"[:2000]
            if job.opnieuw_proberen:
                job.status = JobStatus.WACHTEND
            else:
                job.status = JobStatus.MISLUKT
                job.geeindigd_op = _nu()
                objection = session.get(Objection, job.objection_id)
                if objection is not None:
                    objection.status = CaseStatus.MISLUKT
                    objection.analyse_fout = job.fout
                session.add(
                    AuditEvent(
                        objection_id=job.objection_id,
                        actor="werker",
                        actie="verwerking_mislukt",
                        detail={"job": job.id, "pogingen": job.pogingen, "fout": job.fout},
                    )
                )
            session.commit()
        else:
            job.status = JobStatus.KLAAR
            job.geeindigd_op = _nu()
            job.fout = None
            session.commit()
    return gedaan


def verwerk_alles(session: Session, *, rondes: int = 20) -> int:
    """Werkt de rij leeg. Voor scripts en tests."""
    totaal = 0
    for _ in range(rondes):
        gedaan = draai_ronde(session)
        totaal += gedaan
        if gedaan == 0:
            break
    return totaal


# --- draaivormen ----------------------------------------------------------


class AchtergrondWerker:
    """Meelopende werker in het proces van de webapplicatie."""

    def __init__(self, interval: float = 2.0) -> None:
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="bezwaren-werker", daemon=True)
        self._thread.start()
        logger.info("Achtergrondwerker gestart (interval %.1fs)", self._interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                with session_scope() as session:
                    draai_ronde(session)
            except Exception:  # de werker mag nooit stilvallen op een fout
                logger.exception("Fout in de achtergrondwerker")
            self._stop.wait(self._interval)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(prog="app.worker", description=__doc__)
    parser.add_argument("--interval", type=float, default=2.0, help="seconden tussen rondes")
    parser.add_argument("--eenmalig", action="store_true", help="rij leegwerken en stoppen")
    args = parser.parse_args(argv)

    init_db()

    if args.eenmalig:
        with session_scope() as session:
            gedaan = verwerk_alles(session)
        print(f"{gedaan} taak(en) verwerkt.")
        return 0

    stoppen = threading.Event()
    for sein in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sein, lambda *_: stoppen.set())

    logger.info("Werker gestart. Ctrl-C om te stoppen.")
    while not stoppen.is_set():
        try:
            with session_scope() as session:
                gedaan = draai_ronde(session)
        except Exception:
            logger.exception("Fout in de werker")
            gedaan = 0
        if gedaan == 0:
            stoppen.wait(args.interval)
    logger.info("Werker gestopt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
