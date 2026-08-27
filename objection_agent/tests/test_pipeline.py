"""Volledige verwerking van een bezwaar, zonder taalmodel (regels en sjabloon)."""

from datetime import date

from app.agent.pipeline import verwerk_bezwaar
from app.agent.verify import BESTAAT_NIET, NIET_VAN_TOEPASSING, controleer_verwijzingen
from app.ingest.intake import uit_tekst
from app.models import CaseStatus, Merit, Source, SourceKind, Verification


def _verwerk(session, tekst):
    objection = uit_tekst(session, tekst)
    draft = verwerk_bezwaar(session, objection, online=False)
    session.refresh(objection)
    return objection, draft


def test_pseudojuridische_brief_wordt_ingedeeld_en_geescaleerd(session, fixtures_dir):
    tekst = (fixtures_dir / "pseudojuridisch.txt").read_text(encoding="utf-8")
    objection, draft = _verwerk(session, tekst)

    categorieen = {a.categorie for a in objection.argumenten}
    assert "geen_ondertekend_contract" in categorieen
    assert "pseudojuridisch" in categorieen
    assert "awb_verwarring" in categorieen
    assert "leegstand_of_sloop" in categorieen

    # De brief noemt de Awb: dat is hier geen toepasselijk recht.
    uitkomsten = {c.ruwe_verwijzing: c.uitkomst for c in objection.aangehaalde_bronnen}
    assert any(u == NIET_VAN_TOEPASSING for u in uitkomsten.values())

    assert draft.tekst.strip()
    assert objection.status in (CaseStatus.CONCEPT_GEREED, CaseStatus.GEESCALEERD)


def test_terecht_bezwaar_wordt_als_kansrijk_gemarkeerd(session, fixtures_dir):
    tekst = (fixtures_dir / "terecht_bezwaar.txt").read_text(encoding="utf-8")
    objection, draft = _verwerk(session, tekst)

    assert "verkeerde_partij" in {a.categorie for a in objection.argumenten}
    assert objection.globale_kans == Merit.KANSRIJK
    assert objection.escalatie is True
    # Bij een kansrijk bezwaar mag de brief geen afwijzing bevatten maar een toezegging.
    assert "onderzoeken" in draft.tekst.lower()


def test_verzonnen_ecli_verhoogt_het_ai_signaal(session):
    # Zo staat een gecontroleerde, niet-bestaande uitspraak in de kennisbank nadat
    # `sync ecli` hem heeft opgezocht.
    session.add(
        Source(
            key="ecli-nl-hr-2019-1423",
            soort=SourceKind.JURISPRUDENTIE,
            titel="Niet gevonden",
            vindplaats="ECLI:NL:HR:2019:1423",
            verificatie=Verification.NIET_GEVONDEN,
        )
    )
    session.commit()

    oordelen = controleer_verwijzingen(
        session, "Zie ECLI:NL:HR:2019:1423 waaruit blijkt dat ik gelijk heb.", online=False
    )
    assert oordelen[0].uitkomst == BESTAAT_NIET

    objection, _ = _verwerk(
        session, "Ik heb nooit een contract getekend. Zie ECLI:NL:HR:2019:1423 en verder niets."
    )
    assert objection.ai_gegenereerd_signaal >= 0.45
    assert "bestaan niet" in (objection.ai_signaal_toelichting or "")


def test_ongecontroleerde_verwijzing_blijft_onbekend(session):
    """Zonder controle bij de bron beweren we nooit dat iets niet bestaat."""
    oordelen = controleer_verwijzingen(session, "Zie ECLI:NL:HR:2099:1.", online=False)
    assert oordelen[0].uitkomst == "onbekend"


def test_concept_citeert_alleen_geverifieerde_bronnen(session, fixtures_dir):
    tekst = (fixtures_dir / "pseudojuridisch.txt").read_text(encoding="utf-8")
    _, draft = _verwerk(session, tekst)

    # De seed staat op `ongeverifieerd`, dus er is niets citeerbaars: het concept
    # mag dan geen enkele vindplaats noemen.
    rapport = draft.guardrail_rapport or {}
    codes = {b["code"] for b in rapport.get("bevindingen", [])}
    assert "vindplaats_buiten_kennisbank" not in codes


def test_geverifieerde_bron_komt_wel_beschikbaar(session):
    bron = session.query(Source).filter_by(key="bw6-217").one()
    bron.verificatie = Verification.BEVESTIGD
    bron.tekst = "Een overeenkomst komt tot stand door een aanbod en de aanvaarding daarvan."
    session.commit()

    _, draft = _verwerk(session, "Ik heb nooit een contract getekend met u.")
    assert "bw6-217" in (draft.gebruikte_bron_keys or [])


def test_lege_brief_levert_een_nette_fout(session):
    from app.models import Objection

    objection = Objection(kanaal="api", bron_id="leeg", ruwe_tekst="   ")
    session.add(objection)
    session.commit()

    try:
        verwerk_bezwaar(session, objection, online=False)
    except ValueError as exc:
        assert "Geen tekst" in str(exc)
    else:
        raise AssertionError("verwachtte een ValueError")

    session.refresh(objection)
    assert objection.status == CaseStatus.MISLUKT


def test_peildatum_bepaalt_welk_recht_geldt(session):
    from app.agent.analyse import analyseer_met_regels

    analyse = analyseer_met_regels("De vordering ziet op de periode vanaf 12-03-2022.")
    assert analyse.peildatum == date(2022, 3, 12)


def test_automatisch_gemapt_artikel_is_nog_niet_citeerbaar(session):
    """Een opgehaalde wettekst is echt; de koppeling aan een categorie is een oordeel."""
    from app.knowledge.store import haal_bronnen

    session.add(
        Source(
            key="ew-aansluittaak-3.10",
            soort=SourceKind.WET,
            titel="Taak netbeheerder",
            vindplaats="art. 3.10 Energiewet",
            tekst="De netbeheerder heeft tot taak ...",
            categorieen=["geen_ondertekend_contract"],
            verificatie=Verification.BEVESTIGD,
            tags=["auto-gemapt", "ew-aansluittaak"],
        )
    )
    session.commit()

    bron = session.query(Source).filter_by(key="ew-aansluittaak-3.10").one()
    assert bron.citeerbaar is False
    assert haal_bronnen(session, ["geen_ondertekend_contract"]) == []

    # Na accordering door een jurist wel.
    bron.verificatie = Verification.HANDMATIG
    session.commit()
    assert bron.citeerbaar is True
    assert [b.key for b in haal_bronnen(session, ["geen_ondertekend_contract"])] == [
        "ew-aansluittaak-3.10"
    ]


def test_energiewet_geldt_niet_voor_een_oude_vordering(session):
    """Een vordering uit 2023 valt nog onder de Elektriciteitswet 1998."""
    from datetime import date as _date

    from app.knowledge.store import geldig_op

    energiewet = Source(
        key="ew-x", soort=SourceKind.WET, titel="t", vindplaats="art. 3.10 Energiewet",
        geldig_vanaf=_date(2026, 1, 1), verificatie=Verification.HANDMATIG,
    )
    ewet1998 = Source(
        key="ewet-x", soort=SourceKind.WET, titel="t", vindplaats="art. 23 Elektriciteitswet 1998",
        geldig_tot=_date(2025, 12, 31), vervangen_door="Ew", verificatie=Verification.HANDMATIG,
    )

    assert geldig_op(energiewet, _date(2023, 5, 1)) is False
    assert geldig_op(ewet1998, _date(2023, 5, 1)) is True
    assert geldig_op(energiewet, _date(2026, 3, 1)) is True
    assert geldig_op(ewet1998, _date(2026, 3, 1)) is False


def test_kenmerk_wordt_ook_uit_een_betreft_regel_gehaald(session):
    """Zonder kenmerk is een dossier niet op te zoeken en niet te koppelen."""
    from app.agent.analyse import _velden_uit_tekst

    varianten = {
        "Betreft ASC-2026-55010": "ASC-2026-55010",
        "Betreft: uw aanmaning, kenmerk ASC-2019-41207": "ASC-2019-41207",
        "kenmerk: ASC-2024-88123": "ASC-2024-88123",
        "Onderwerp: uw factuurnummer 2024/887766": "2024/887766",
    }
    for tekst, verwacht in varianten.items():
        assert _velden_uit_tekst(tekst)["dossier_ref"] == verwacht, tekst


def test_eigen_kenmerkpatroon_gaat_voor(session, monkeypatch):
    from app.agent import analyse as analyse_module
    from app.config import get_settings

    instellingen = get_settings().model_copy(update={"kenmerk_patroon": r"(ZAAK\d{6})"})
    monkeypatch.setattr(analyse_module, "get_settings", lambda: instellingen)

    velden = analyse_module._velden_uit_tekst("Betreft ASC-2026-55010, intern ZAAK998877.")
    assert velden["dossier_ref"] == "ZAAK998877"
