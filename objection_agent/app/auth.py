"""Toegangsbeveiliging.

Een bezwaardossier bevat naam, adres, EAN en vaak een financiele situatie. Zonder
enige drempel is dat voor iedereen leesbaar die bij de poort kan. Deze module is
geen vervanging van jullie SSO, maar zorgt dat de tool niet per ongeluk open
draait: zonder ingestelde toegang start hij niet.

Twee vormen naast elkaar:
  - HTTP Basic voor de schermen (OA_UI_USER / OA_UI_PASSWORD)
  - een token voor machines (OA_AUTH_TOKEN), als `Authorization: Bearer ...`
    of als `X-API-Token`
"""

from __future__ import annotations

import base64
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .config import Settings

# Deze paden blijven open: een gezondheidscheck mag geen inloggegevens nodig hebben.
OPEN_PADEN = {"/gezondheid"}


class ToegangOntbreekt(RuntimeError):
    pass


def controleer_configuratie(settings: Settings) -> None:
    """Weigert te starten zonder toegangsbeveiliging.

    Bewust een harde stop en geen waarschuwing: een waarschuwing in een logbestand
    wordt gemist, en dan draait er een maand lang een open dossierbak.
    """
    if not settings.require_auth:
        return
    if settings.auth_token or (settings.ui_user and settings.ui_password):
        return
    raise ToegangOntbreekt(
        "Geen toegangsbeveiliging ingesteld. Zet OA_UI_USER en OA_UI_PASSWORD voor de "
        "schermen, en/of OA_AUTH_TOKEN voor de API. Draait u lokaal een demo, zet dan "
        "expliciet OA_REQUIRE_AUTH=false."
    )


def _basic_klopt(header: str, settings: Settings) -> bool:
    if not (settings.ui_user and settings.ui_password):
        return False
    try:
        ontcijferd = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        gebruiker, _, wachtwoord = ontcijferd.partition(":")
    except (IndexError, ValueError, UnicodeDecodeError):
        return False
    # compare_digest voorkomt dat de responstijd verraadt hoeveel tekens kloppen.
    return secrets.compare_digest(gebruiker, settings.ui_user) and secrets.compare_digest(
        wachtwoord, settings.ui_password
    )


def _token_klopt(waarde: str, settings: Settings) -> bool:
    return bool(settings.auth_token) and secrets.compare_digest(waarde, settings.auth_token)


class ToegangMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        settings = self._settings
        if not settings.require_auth or request.url.path in OPEN_PADEN:
            return await call_next(request)

        autorisatie = request.headers.get("authorization", "")
        token_header = request.headers.get("x-api-token", "")

        if autorisatie.lower().startswith("basic ") and _basic_klopt(autorisatie, settings):
            return await call_next(request)
        if autorisatie.lower().startswith("bearer ") and _token_klopt(
            autorisatie.split(" ", 1)[1], settings
        ):
            return await call_next(request)
        if token_header and _token_klopt(token_header, settings):
            return await call_next(request)

        # Een browser krijgt een inlogvenster, een API-aanroep een nette 401.
        if "text/html" in request.headers.get("accept", ""):
            return Response(
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="Bezwaren ASC"'},
            )
        return JSONResponse(status_code=401, content={"detail": "Niet geautoriseerd"})
