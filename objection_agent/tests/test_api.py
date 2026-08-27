"""API- en UI-rooktest, volledig offline."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.db import engine
from app.main import app
from app.models import Base

BRIEF = (
    "Betreft kenmerk ASC-2024-88123. Ik heb nooit een contract getekend en ik verbruik "
    "geen energie op dit adres. Volgens artikel 47 Awb had u mij moeten horen. "
    "Zie ook ECLI:NL:HR:2019:1423."
)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    with TestClient(app) as testclient:  # draait de lifespan, dus ook de seed
        yield testclient


def test_gezondheid_meldt_dat_er_niets_verstuurd_wordt(client):
    body = client.get("/gezondheid").json()
    assert body["status"] == "ok"
    assert body["verzendt_zelf"] is False


def test_bezwaar_via_tekst_wordt_direct_verwerkt(client):
    response = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF})
    assert response.status_code == 201
    body = response.json()

    assert body["dossier_ref"] == "ASC-2024-88123"
    assert body["status"] in ("concept_gereed", "geescaleerd")
    assert body["argumenten"], "verwachtte ingedeelde argumenten"
    assert body["concepten"], "verwachtte een conceptbrief"
    # De Awb-verwijzing moet als niet van toepassing zijn aangemerkt.
    assert any(c["uitkomst"] == "niet_van_toepassing" for c in body["aangehaalde_bronnen"])


def test_werkvoorraad_en_detailpagina_renderen(client):
    bezwaar = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF}).json()

    lijst = client.get("/")
    assert lijst.status_code == 200
    assert "Werkvoorraad" in lijst.text

    detail = client.get(f"/bezwaar/{bezwaar['id']}")
    assert detail.status_code == 200
    assert "Conceptantwoord" in detail.text


def test_goedkeuring_legt_beoordelaar_en_tijdstip_vast(client):
    bezwaar = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF}).json()
    concept = bezwaar["concepten"][-1]

    response = client.post(
        f"/api/bezwaren/{bezwaar['id']}/concepten/{concept['id']}/goedkeuren",
        json={
            "beoordelaar": "medewerker-042",
            "notitie": "Alinea over leegstand aangepast",
            "aangepaste_tekst": "Geachte heer De Vries,\n\nWij hebben uw brief ontvangen.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["beoordelaar"] == "medewerker-042"
    assert body["goedgekeurd_op"]
    assert body["geblokkeerd"] is False

    assert client.get(f"/api/bezwaren/{bezwaar['id']}").json()["status"] == "goedgekeurd"


def test_geblokkeerd_concept_kan_niet_ongewijzigd_worden_goedgekeurd(client):
    bezwaar = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF}).json()
    concept_id = bezwaar["concepten"][-1]["id"]

    # Simuleer een concept dat door de controle is tegengehouden.
    from app.db import SessionLocal
    from app.models import Draft

    with SessionLocal() as s:
        draft = s.get(Draft, concept_id)
        draft.geblokkeerd = True
        s.commit()

    response = client.post(
        f"/api/bezwaren/{bezwaar['id']}/concepten/{concept_id}/goedkeuren",
        json={"beoordelaar": "medewerker-042"},
    )
    assert response.status_code == 409
    assert "tegengehouden" in response.json()["detail"]


def test_taxonomie_is_opvraagbaar(client):
    body = client.get("/api/kennisbank/taxonomie").json()
    sleutels = {c["sleutel"] for c in body["categorieen"]}
    assert {"verjaring", "pseudojuridisch", "verkeerde_partij"} <= sleutels
    assert next(c for c in body["categorieen"] if c["sleutel"] == "verjaring")["altijd_naar_mens"]


def test_eigen_bron_toevoegen_en_accorderen(client):
    payload = {
        "key": "werkinstructie-leegstand",
        "soort": "eigen",
        "titel": "Werkinstructie leegstand en verwijderverzoek",
        "vindplaats": "Werkinstructie ASC-07",
        "tekst": "Bij leegstand blijft de aansluitvergoeding verschuldigd tot verwijdering.",
        "categorieen": ["leegstand_of_sloop"],
    }
    aangemaakt = client.post("/api/kennisbank/bronnen", json=payload)
    assert aangemaakt.status_code == 201
    assert aangemaakt.json()["citeerbaar"] is False

    geaccordeerd = client.post(
        "/api/kennisbank/bronnen/werkinstructie-leegstand/accorderen",
        json={"beoordelaar": "jurist-01"},
    )
    assert geaccordeerd.status_code == 200
    assert geaccordeerd.json()["citeerbaar"] is True


def test_onbekende_categorie_wordt_geweigerd(client):
    response = client.post(
        "/api/kennisbank/bronnen",
        json={"key": "x", "titel": "t", "vindplaats": "v", "categorieen": ["bestaat_niet"]},
    )
    assert response.status_code == 422


def test_auto_gemapt_artikel_accorderen_via_de_ui(client):
    """De juristenroute: opgehaald artikel nalopen en vrijgeven voor gebruik."""
    from app.db import SessionLocal
    from app.models import Source, SourceKind, Verification

    with SessionLocal() as s:
        s.add(
            Source(
                key="ew-aansluittaak-3.10",
                soort=SourceKind.WET,
                titel="Taken van de netbeheerder",
                vindplaats="art. 3.10 Energiewet",
                tekst="De netbeheerder heeft tot taak ...",
                categorieen=["geen_ondertekend_contract"],
                verificatie=Verification.BEVESTIGD,
                tags=["auto-gemapt", "ew-aansluittaak"],
            )
        )
        s.commit()

    pagina = client.get("/kennisbank")
    assert "wachten op beoordeling" in pagina.text

    response = client.post(
        "/ui/kennisbank/ew-aansluittaak-3.10/accorderen",
        data={"beoordelaar": "jurist-01"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    bron = client.get("/api/kennisbank/bronnen").json()
    gemapt = next(b for b in bron if b["key"] == "ew-aansluittaak-3.10")
    assert gemapt["citeerbaar"] is True


def test_brief_kan_pas_worden_uitgevoerd_na_goedkeuring(client):
    bezwaar = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF}).json()
    concept = bezwaar["concepten"][-1]
    pad = f"/api/bezwaren/{bezwaar['id']}/concepten/{concept['id']}/brief.txt"

    assert client.get(pad).status_code == 409

    client.post(
        f"/api/bezwaren/{bezwaar['id']}/concepten/{concept['id']}/goedkeuren",
        json={"beoordelaar": "medewerker-042", "aangepaste_tekst": "Geachte heer,\n\nHierbij."},
    )
    uitvoer = client.get(pad)
    assert uitvoer.status_code == 200
    assert "Hierbij" in uitvoer.text
    assert "attachment" in uitvoer.headers["content-disposition"]


def test_dossier_verwijderen_laat_een_spoor_zonder_inhoud(client):
    bezwaar = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF}).json()

    weg = client.delete(f"/api/bezwaren/{bezwaar['id']}?actor=fg-01&reden=avg-verzoek")
    assert weg.status_code == 204
    assert client.get(f"/api/bezwaren/{bezwaar['id']}").status_code == 404

    from app.db import SessionLocal
    from app.models import AuditEvent

    with SessionLocal() as s:
        spoor = s.query(AuditEvent).filter_by(actie="dossier_verwijderd").one()
        assert spoor.actor == "fg-01"
        assert spoor.detail["reden"] == "avg-verzoek"
        assert "ruwe_tekst" not in spoor.detail
        assert "afzender_naam" not in spoor.detail


def test_dezelfde_brief_levert_geen_tweede_dossier(client):
    eerste = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF})
    tweede = client.post("/api/bezwaren/tekst", json={"tekst": BRIEF})
    assert eerste.status_code == 201
    assert tweede.status_code == 200
    assert tweede.json()["id"] == eerste.json()["id"]


def test_werkvoorraad_kan_gefilterd_worden(client):
    client.post("/api/bezwaren/tekst", json={"tekst": BRIEF})
    client.post(
        "/api/bezwaren/tekst",
        json={
            "tekst": "Ik heb het pand op 04-06-2021 verkocht bij de notaris en ben geen "
            "eigenaar meer. Kenmerk ASC-2021-777.",
        },
    )

    alles = client.get("/")
    assert alles.status_code == 200

    op_kenmerk = client.get("/?zoek=ASC-2021-777")
    assert "ASC-2021-777" in op_kenmerk.text
    assert "ASC-2024-88123" not in op_kenmerk.text

    op_kans = client.get("/?kans=kansrijk")
    assert op_kans.status_code == 200

    zonder_treffer = client.get("/?zoek=bestaat-niet-xyz")
    assert "Geen dossiers gevonden" in zonder_treffer.text
