"""Samenhang tussen dossiers, en het toetsen van de inschattingen."""

from __future__ import annotations

from app.agent.pipeline import verwerk_bezwaar
from app.dossier import zoek_gerelateerd
from app.ingest.intake import uit_tekst
from app.kalibratie import verzamel
from app.models import Afloop


def _dossier(session, tekst, **velden):
    objection = uit_tekst(session, tekst)
    for naam, waarde in velden.items():
        setattr(objection, naam, waarde)
    session.commit()
    return objection


def test_dossiers_met_dezelfde_ean_worden_gevonden(session):
    eerste = _dossier(session, "Eerste brief over deze aansluiting.", ean="871685920000123456")
    tweede = _dossier(session, "Tweede brief over dezelfde aansluiting.", ean="871685920000123456")
    ander = _dossier(session, "Brief over een heel andere aansluiting.", ean="871685920000999999")

    gerelateerd = zoek_gerelateerd(session, tweede)
    assert [g.id for g in gerelateerd] == [eerste.id]
    assert ander.id not in [g.id for g in gerelateerd]


def test_ook_op_e_mailadres(session):
    eerste = _dossier(session, "Eerste brief van deze klant.", afzender_email="p@example.nl")
    tweede = _dossier(session, "Tweede brief van deze klant.", afzender_email="p@example.nl")
    assert [g.id for g in zoek_gerelateerd(session, tweede)] == [eerste.id]


def test_zonder_kenmerken_geen_verband(session):
    los = _dossier(session, "Een brief zonder kenmerk, EAN of afzender.")
    assert zoek_gerelateerd(session, los) == []


def test_dossier_verwijst_niet_naar_zichzelf(session):
    alleen = _dossier(session, "Enige brief over deze aansluiting.", ean="871685920000123456")
    assert zoek_gerelateerd(session, alleen) == []


def test_kalibratie_negeert_dossiers_zonder_vastgelegde_afloop(session):
    objection = uit_tekst(session, "Ik heb nooit een contract getekend met u.")
    verwerk_bezwaar(session, objection, online=False)
    assert verzamel(session) == {}


def test_kalibratie_zet_inschatting_naast_afloop(session):
    objection = uit_tekst(session, "Ik heb nooit een contract getekend met u.")
    verwerk_bezwaar(session, objection, online=False)
    objection.afloop = Afloop.VORDERING_INGETROKKEN
    session.commit()

    gegevens = verzamel(session)
    regel = gegevens["geen_ondertekend_contract"]
    assert regel["aantal"] == 1
    # Ingeschat als kansarm, in werkelijkheid ingetrokken: precies het signaal
    # waar dit rapport voor bedoeld is.
    assert regel["som_inschatting"] < 0.3
    assert regel["som_afloop"] == 1.0


def test_deels_gecorrigeerd_telt_half_mee(session):
    objection = uit_tekst(session, "Ik heb nooit een contract getekend met u.")
    verwerk_bezwaar(session, objection, online=False)
    objection.afloop = Afloop.DEELS_GECORRIGEERD
    session.commit()
    assert verzamel(session)["geen_ondertekend_contract"]["som_afloop"] == 0.5
