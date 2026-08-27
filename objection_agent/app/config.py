"""Configuratie voor de bezwaren-beantwoordingsagent (afdeling Aansluiting Zonder Contract)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="OA_", extra="ignore", env_file_encoding="utf-8"
    )

    # --- Algemeen -------------------------------------------------------
    app_name: str = "Bezwaren-agent Aansluiting Zonder Contract"
    debug: bool = False
    database_url: str = f"sqlite:///{DATA_DIR / 'objections.db'}"
    upload_dir: Path = DATA_DIR / "uploads"

    # --- LLM ------------------------------------------------------------
    # Provider volgt de sleutel die gezet is; expliciet zetten kan met OA_LLM_PROVIDER.
    llm_provider: str = "auto"  # auto | openai | anthropic | offline
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    llm_timeout_seconds: int = 120
    llm_max_output_tokens: int = 4000

    # --- Kennisbank -----------------------------------------------------
    # Officiele open data (geen scraping): KOOP-repository en Rechtspraak Open Data.
    wetten_base_url: str = "https://repository.overheid.nl/frbr/bwb"
    rechtspraak_search_url: str = "https://data.rechtspraak.nl/uitspraken/zoeken"
    rechtspraak_content_url: str = "https://data.rechtspraak.nl/uitspraken/content"
    knowledge_http_timeout: int = 60
    # Alleen geverifieerde bronnen mogen in een conceptbrief geciteerd worden.
    require_verified_sources: bool = True

    # --- Postbus (IMAP) -------------------------------------------------
    imap_host: str | None = None
    imap_port: int = 993
    imap_user: str | None = None
    imap_password: str | None = None
    imap_folder: str = "INBOX"
    imap_processed_folder: str = "Verwerkt"
    imap_max_per_run: int = 50

    # --- Toegang --------------------------------------------------------
    # De applicatie start niet zonder een van beide, tenzij require_auth uit staat.
    require_auth: bool = True
    ui_user: str | None = None
    ui_password: str | None = None
    auth_token: str | None = None

    # --- Bewaartermijn --------------------------------------------------
    # Na deze termijn mag een afgehandeld dossier worden opgeruimd. Stem af met
    # de functionaris gegevensbescherming; nul betekent: niet automatisch opruimen.
    bewaartermijn_dagen: int = 730

    # --- Beleid / veiligheidskleppen ------------------------------------
    # De agent verstuurt nooit zelf. Deze vlag bestaat om dat expliciet te maken.
    autosend_enabled: bool = False
    # Bezwaren met deze uitkomst gaan altijd naar een mens met juridische kennis.
    escalation_threshold: float = 0.35

    @property
    def data_dir(self) -> Path:
        return DATA_DIR


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
