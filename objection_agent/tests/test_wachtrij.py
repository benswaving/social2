"""De wachtrij: zwaar werk buiten het HTTP-verzoek."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.ingest.intake import uit_tekst
from app.models import CaseStatus, Job, JobStatus
from app.worker import draai_ronde, meld_aan, verwerk_alles, wachtrij_standen

BRIEF = "Ik heb nooit een contract getekend en verbruik geen energie op dit adres."


def test_aanmelden_zet_een_taak_klaar(session):
    objection = uit_tekst(session, BRIEF)
    job = meld_aan(session, objection.id)

    assert job.status == JobStatus.WACHTEND
    assert wachtrij_standen(session)["wachtend"] == 1
    assert objection.status == CaseStatus.NIEUW  # nog niets verwerkt


def test_dubbel_aanmelden_levert_geen_tweede_taak(session):
    objection = uit_tekst(session, BRIEF)
    eerste = meld_aan(session, objection.id)
    tweede = meld_aan(session, objection.id)

    assert eerste.id == tweede.id
    assert session.query(Job).count() == 1


def test_werker_verwerkt_de_rij(session):
    objection = uit_tekst(session, BRIEF)
    meld_aan(session, objection.id)

    assert draai_ronde(session) == 1

    session.refresh(objection)
    assert objection.concepten, "verwachtte een conceptbrief"
    assert objection.status in (CaseStatus.CONCEPT_GEREED, CaseStatus.GEESCALEERD)
    assert wachtrij_standen(session)["klaar"] == 1


def test_lege_rij_doet_niets(session):
    assert draai_ronde(session) == 0


def test_een_kapot_dossier_stopt_de_rij_niet(session):
    goed = uit_tekst(session, BRIEF)
    kapot = uit_tekst(session, "Dit is een tweede brief met genoeg tekst erin om te bewaren.")
    kapot.ruwe_tekst = "   "  # lege tekst laat de verwerking struikelen
    session.commit()

    meld_aan(session, kapot.id)
    meld_aan(session, goed.id)

    verwerk_alles(session)

    session.refresh(goed)
    assert goed.concepten, "het goede dossier moet gewoon verwerkt zijn"

    mislukt = session.query(Job).filter_by(objection_id=kapot.id).one()
    assert mislukt.status == JobStatus.MISLUKT
    assert mislukt.pogingen == mislukt.max_pogingen
    assert "Geen tekst" in (mislukt.fout or "")

    session.refresh(kapot)
    assert kapot.status == CaseStatus.MISLUKT


def test_taak_wordt_opnieuw_geprobeerd_voor_hij_opgeeft(session):
    objection = uit_tekst(session, BRIEF)
    objection.ruwe_tekst = ""
    session.commit()
    meld_aan(session, objection.id)

    draai_ronde(session, maximum=1)
    job = session.query(Job).one()
    assert job.status == JobStatus.WACHTEND  # nog pogingen over
    assert job.pogingen == 1


def test_vastgelopen_taak_wordt_teruggezet(session):
    objection = uit_tekst(session, BRIEF)
    job = meld_aan(session, objection.id)
    # Zoals het eruitziet nadat het proces tijdens de verwerking omviel.
    job.status = JobStatus.BEZIG
    job.gestart_op = datetime.now(timezone.utc) - timedelta(hours=2)
    session.commit()

    draai_ronde(session)

    session.refresh(job)
    assert job.status == JobStatus.KLAAR


@pytest.mark.parametrize("aantal", [3])
def test_meerdere_dossiers_in_een_ronde(session, aantal):
    for nummer in range(aantal):
        objection = uit_tekst(session, f"{BRIEF} Kenmerk ASC-2026-{nummer:04d}.")
        meld_aan(session, objection.id)

    assert draai_ronde(session, maximum=10) == aantal
    assert wachtrij_standen(session)["wachtend"] == 0
