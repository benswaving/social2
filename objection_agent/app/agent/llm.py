"""LLM-laag: een dunne wrapper met JSON-uitvoer en een offline modus.

Providerkeuze volgt de sleutel die gezet is. Er is bewust ook een `offline`
modus: daarmee draait de hele pijplijn op regels en trefwoorden, zonder
externe aanroep. Dat is nodig om de guardrails te kunnen testen en om een
dossier te kunnen blijven behandelen als de API onbereikbaar is.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)


class LLMOnbeschikbaar(RuntimeError):
    """De gekozen provider kan nu niet gebruikt worden."""


@dataclass
class LLMAntwoord:
    data: dict[str, Any]
    model: str
    ruw: str


def _knip_json(tekst: str) -> dict[str, Any]:
    """Haalt het JSON-object uit een antwoord dat er omheen kan kletsen."""
    tekst = tekst.strip()
    if tekst.startswith("```"):
        tekst = re.sub(r"^```[a-zA-Z]*\n?", "", tekst)
        tekst = re.sub(r"\n?```$", "", tekst.strip())
    try:
        return json.loads(tekst)
    except json.JSONDecodeError:
        pass
    start, eind = tekst.find("{"), tekst.rfind("}")
    if start != -1 and eind > start:
        return json.loads(tekst[start : eind + 1])
    raise ValueError("Geen bruikbaar JSON-object in het modelantwoord")


class LLMClient:
    def __init__(self, provider: str | None = None) -> None:
        settings = get_settings()
        self._settings = settings
        self.provider = provider or self._kies_provider(settings)

    @staticmethod
    def _kies_provider(settings: Any) -> str:
        if settings.llm_provider != "auto":
            return settings.llm_provider
        if settings.openai_api_key:
            return "openai"
        if settings.anthropic_api_key:
            return "anthropic"
        return "offline"

    @property
    def model(self) -> str:
        if self.provider == "openai":
            return self._settings.openai_model
        if self.provider == "anthropic":
            return self._settings.anthropic_model
        return "offline-regels"

    @property
    def beschikbaar(self) -> bool:
        return self.provider != "offline"

    def json_completion(
        self, *, systeem: str, gebruiker: str, max_tokens: int | None = None
    ) -> LLMAntwoord:
        if self.provider == "offline":
            raise LLMOnbeschikbaar("Geen LLM-provider geconfigureerd (OA_OPENAI_API_KEY ontbreekt)")
        max_tokens = max_tokens or self._settings.llm_max_output_tokens
        if self.provider == "openai":
            return self._openai(systeem, gebruiker, max_tokens)
        if self.provider == "anthropic":
            return self._anthropic(systeem, gebruiker, max_tokens)
        raise LLMOnbeschikbaar(f"Onbekende provider: {self.provider}")

    def _openai(self, systeem: str, gebruiker: str, max_tokens: int) -> LLMAntwoord:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise LLMOnbeschikbaar("pakket `openai` niet geinstalleerd") from exc

        client = OpenAI(
            api_key=self._settings.openai_api_key, timeout=self._settings.llm_timeout_seconds
        )
        response = client.chat.completions.create(
            model=self._settings.openai_model,
            messages=[
                {"role": "system", "content": systeem},
                {"role": "user", "content": gebruiker},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
            temperature=0.1,
        )
        ruw = response.choices[0].message.content or ""
        return LLMAntwoord(data=_knip_json(ruw), model=self._settings.openai_model, ruw=ruw)

    def _anthropic(self, systeem: str, gebruiker: str, max_tokens: int) -> LLMAntwoord:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise LLMOnbeschikbaar("pakket `anthropic` niet geinstalleerd") from exc

        client = anthropic.Anthropic(
            api_key=self._settings.anthropic_api_key, timeout=self._settings.llm_timeout_seconds
        )
        response = client.messages.create(
            model=self._settings.anthropic_model,
            system=systeem,
            messages=[{"role": "user", "content": gebruiker}],
            max_tokens=max_tokens,
            temperature=0.1,
        )
        ruw = "".join(blok.text for blok in response.content if blok.type == "text")
        return LLMAntwoord(data=_knip_json(ruw), model=self._settings.anthropic_model, ruw=ruw)
