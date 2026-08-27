"""Testopstelling: elke run krijgt een eigen database in een tijdelijke map."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="asc-agent-tests-"))
# Moet gezet zijn vóór app.config voor het eerst geimporteerd wordt.
os.environ["OA_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["OA_LLM_PROVIDER"] = "offline"
os.environ["OA_REQUIRE_AUTH"] = "false"
os.environ["OA_WACHTRIJ_ACTIEF"] = "false"
os.environ["OA_WERKER_IN_PROCES"] = "false"
os.environ.pop("OA_OPENAI_API_KEY", None)

import pytest  # noqa: E402

from app.db import SessionLocal, init_db  # noqa: E402
from app.knowledge.loader import seed_sources  # noqa: E402
from app.models import Base  # noqa: E402
from app.db import engine  # noqa: E402


@pytest.fixture()
def session():
    Base.metadata.drop_all(engine)
    init_db()
    s = SessionLocal()
    seed_sources(s)
    try:
        yield s
    finally:
        s.close()


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"
