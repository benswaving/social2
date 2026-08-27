"""Toegangsbeveiliging: dossiers bevatten persoonsgegevens."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import ToegangOntbreekt, controleer_configuratie
from app.config import Settings


def _settings(**velden) -> Settings:
    basis = {"require_auth": True, "ui_user": None, "ui_password": None, "auth_token": None}
    return Settings(**{**basis, **velden})


def test_start_weigert_zonder_ingestelde_toegang():
    with pytest.raises(ToegangOntbreekt) as fout:
        controleer_configuratie(_settings())
    assert "OA_UI_USER" in str(fout.value)


def test_start_accepteert_basic_of_token():
    controleer_configuratie(_settings(ui_user="asc", ui_password="geheim"))
    controleer_configuratie(_settings(auth_token="t0ken"))
    controleer_configuratie(_settings(require_auth=False))


@pytest.fixture()
def beveiligde_app(monkeypatch):
    """Een app met toegangsbeveiliging aan, los van de testconfiguratie."""
    from app.auth import ToegangMiddleware

    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/api/bezwaren")
    def lijst():
        return []

    @app.get("/gezondheid")
    def gezondheid():
        return {"status": "ok"}

    app.add_middleware(
        ToegangMiddleware,
        settings=_settings(ui_user="asc", ui_password="geheim", auth_token="t0ken"),
    )
    return TestClient(app)


def test_zonder_inloggegevens_geen_toegang(beveiligde_app):
    assert beveiligde_app.get("/api/bezwaren").status_code == 401


def test_gezondheidscheck_blijft_open(beveiligde_app):
    assert beveiligde_app.get("/gezondheid").status_code == 200


def test_basic_en_token_geven_toegang(beveiligde_app):
    assert beveiligde_app.get("/api/bezwaren", auth=("asc", "geheim")).status_code == 200
    assert (
        beveiligde_app.get("/api/bezwaren", headers={"X-API-Token": "t0ken"}).status_code == 200
    )
    assert (
        beveiligde_app.get(
            "/api/bezwaren", headers={"Authorization": "Bearer t0ken"}
        ).status_code
        == 200
    )


def test_verkeerd_wachtwoord_wordt_geweigerd(beveiligde_app):
    assert beveiligde_app.get("/api/bezwaren", auth=("asc", "fout")).status_code == 401
    assert (
        beveiligde_app.get("/api/bezwaren", headers={"X-API-Token": "fout"}).status_code == 401
    )


def test_browser_krijgt_een_inlogvenster(beveiligde_app):
    antwoord = beveiligde_app.get("/api/bezwaren", headers={"Accept": "text/html"})
    assert antwoord.status_code == 401
    assert antwoord.headers["www-authenticate"].startswith("Basic")
