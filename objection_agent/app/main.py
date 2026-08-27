"""FastAPI-applicatie voor de bezwaren-beantwoordingsagent."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .agent.llm import LLMClient
from .auth import ToegangMiddleware, controleer_configuratie
from .api import cases, ingest, knowledge, review
from .config import get_settings
from .db import init_db, session_scope
from .knowledge.loader import seed_sources

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    controleer_configuratie(settings)
    init_db()
    with session_scope() as session:
        resultaat = seed_sources(session)
    logger.info("Kennisbank-seed: %s", resultaat)

    client = LLMClient()
    if not client.beschikbaar:
        logger.warning(
            "Geen LLM-provider geconfigureerd. De agent draait op regels en sjablonen; "
            "zet OA_OPENAI_API_KEY of OA_ANTHROPIC_API_KEY voor volledige werking."
        )
    if not settings.require_auth:
        logger.warning(
            "Toegangsbeveiliging staat uit (OA_REQUIRE_AUTH=false). Alleen doen op een "
            "afgeschermde machine; dossiers bevatten persoonsgegevens."
        )
    if settings.autosend_enabled:
        logger.error(
            "OA_AUTOSEND_ENABLED staat aan, maar deze applicatie verstuurt niets. "
            "Goedkeuring door een medewerker blijft vereist."
        )
    yield


app = FastAPI(
    title="Bezwaren-agent Aansluiting Zonder Contract",
    description=(
        "Scant binnengekomen bezwaarbrieven, beoordeelt de argumenten tegen geverifieerde "
        "bronnen en stelt een conceptantwoord op. Een medewerker keurt elk concept goed "
        "voordat het de deur uitgaat; deze applicatie verstuurt zelf niets."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(ToegangMiddleware, settings=get_settings())

app.include_router(cases.router)
app.include_router(knowledge.router)
app.include_router(ingest.router)
app.include_router(review.router)


@app.get("/gezondheid", tags=["systeem"])
def gezondheid() -> dict:
    client = LLMClient()
    return {
        "status": "ok",
        "llm_provider": client.provider,
        "llm_model": client.model,
        "verzendt_zelf": False,
    }
