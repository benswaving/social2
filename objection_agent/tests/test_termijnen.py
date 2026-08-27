"""Termijnbewaking."""

from __future__ import annotations

from datetime import date, timedelta

from app.agent.pipeline import verwerk_bezwaar
from app.ingest.intake import uit_tekst
from app.models import CaseStatus
from app.termijnen import bepaal_termijn


def test_avg_termijn_bindt_als_de_afdeling_ruimer_werkt(monkeypatch):
    """De wettelijke termijn is een bovengrens waar de afdeling niet overheen mag."""
    from app import termijnen
    from app.config import get_settings

    ruim = get_settings().model_copy(update={"termijn_standaard_dagen": 45})
    monkeypatch.setattr(termijnen, "get_settings", lambda: ruim)

    vandaag = date(2026, 8, 1)
    termijn = termijnen.bepaal_termijn(ontvangen_op=vandaag, categorieen=["avg_privacy"])
    assert termijn.uiterlijk == vandaag + timedelta(days=28)
    assert "AVG" in termijn.grond


def test_escalatie_krijgt_een_kortere_termijn_dan_standaard():
    vandaag = date(2026, 8, 1)
    escalatie = bepaal_termijn(ontvangen_op=vandaag, escalatie=True)
    standaard = bepaal_termijn(ontvangen_op=vandaag)
    assert escalatie.uiterlijk < standaard.uiterlijk


def test_intake_zet_meteen_een_termijn(session):
    objection = uit_tekst(session, "Ik maak bezwaar tegen uw factuur, ik heb niets getekend.")
    assert objection.reactie_uiterlijk is not None
    assert objection.termijn_grond


def test_avg_bezwaar_verkort_de_termijn_na_analyse(session):
    objection = uit_tekst(
        session,
        "Ik maak bezwaar. Tevens verzoek ik u op grond van de AVG om inzage in mijn "
        "persoonsgegevens en verwijdering daarvan.",
    )
    voor = objection.reactie_uiterlijk
    verwerk_bezwaar(session, objection, online=False)
    session.refresh(objection)

    assert "avg_privacy" in {a.categorie for a in objection.argumenten}
    assert objection.reactie_uiterlijk <= voor


def test_termijn_wordt_nooit_opgerekt(session):
    """Uitstel dat niemand heeft besloten mag niet vanzelf ontstaan."""
    objection = uit_tekst(session, "Ik heb nooit een contract getekend met u.")
    objection.reactie_uiterlijk = date.today() + timedelta(days=2)
    session.commit()

    verwerk_bezwaar(session, objection, online=False)
    session.refresh(objection)
    assert objection.reactie_uiterlijk <= date.today() + timedelta(days=2)


def test_te_laat_telt_niet_meer_na_goedkeuring(session):
    objection = uit_tekst(session, "Ik heb nooit een contract getekend met u.")
    objection.reactie_uiterlijk = date.today() - timedelta(days=5)
    session.commit()
    assert objection.te_laat is True

    objection.status = CaseStatus.GOEDGEKEURD
    session.commit()
    assert objection.te_laat is False


def test_avg_en_escalatie_samen_leveren_de_kortste_termijn():
    """De AVG-termijn is een wettelijk maximum, geen streefdatum."""
    vandaag = date(2026, 8, 1)
    beide = bepaal_termijn(ontvangen_op=vandaag, categorieen=["avg_privacy"], escalatie=True)
    alleen_escalatie = bepaal_termijn(ontvangen_op=vandaag, escalatie=True)

    assert beide.uiterlijk == alleen_escalatie.uiterlijk
    assert beide.grond == "geescaleerd dossier"


def test_avg_maakt_de_standaardtermijn_nooit_langer():
    vandaag = date(2026, 8, 1)
    termijn = bepaal_termijn(ontvangen_op=vandaag, categorieen=["avg_privacy"])
    standaard = bepaal_termijn(ontvangen_op=vandaag)
    assert termijn.uiterlijk <= standaard.uiterlijk
