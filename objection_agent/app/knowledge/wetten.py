"""Ophalen van wetteksten bij het officiele KOOP-repository (open data, geen scraping).

De structuur van repository.overheid.nl is FRBR-achtig:

    {base}/{BWB-ID}/                                  -> overzicht van geldigheidsversies
    {base}/{BWB-ID}/{datum}/xml/{BWB-ID}_{datum}.xml  -> volledige wettekst op die datum

Omdat een artikel op verschillende peildata anders kan luiden - en de
Elektriciteitswet 1998 en de Gaswet inmiddels zijn vervangen door de Energiewet -
halen we de versie op die gold op de peildatum van de vordering.

Deze module is geschreven tegen de gedocumenteerde endpoints maar is niet
live getest in de bouwomgeving: daar blokkeerde het uitgaande netwerkbeleid
repository.overheid.nl. Draai `python -m app.knowledge.sync wetten --check` als
eerste stap op een omgeving met internettoegang.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import get_settings

DATUM_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


@dataclass(frozen=True)
class Wetsartikel:
    bwb_id: str
    artikel: str
    titel: str
    tekst: str
    versiedatum: str
    url: str


def _strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _tekst_van(element: ET.Element) -> str:
    delen = [t.strip() for t in element.itertext() if t and t.strip()]
    return "\n".join(delen)


def _normaliseer_nr(waarde: str) -> str:
    return waarde.strip().rstrip(".").replace(" ", "").lower()


class WettenClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self._base = settings.wetten_base_url.rstrip("/")
        self._timeout = settings.knowledge_http_timeout
        self._client = client or httpx.Client(
            timeout=self._timeout, headers={"User-Agent": "ASC-bezwarenagent/1.0"}
        )

    # -- versies ---------------------------------------------------------

    def beschikbare_versies(self, bwb_id: str) -> list[str]:
        """Geldigheidsdata waarvoor een expressie bestaat, oplopend gesorteerd."""
        response = self._client.get(f"{self._base}/{bwb_id}/")
        response.raise_for_status()
        # De index bevat de datums als mapnamen; de exacte opmaak (HTML of XML)
        # verschilt per omgeving, dus we lezen ze er tekstueel uit.
        return sorted({m.group(1) for m in DATUM_RE.finditer(response.text)})

    def versie_op(self, bwb_id: str, peildatum: date | None = None) -> str | None:
        versies = self.beschikbare_versies(bwb_id)
        if not versies:
            return None
        if peildatum is None:
            return versies[-1]
        geldig = [v for v in versies if v <= peildatum.isoformat()]
        return geldig[-1] if geldig else versies[0]

    # -- inhoud ----------------------------------------------------------

    def _document_url(self, bwb_id: str, versie: str) -> str:
        return f"{self._base}/{bwb_id}/{versie}/xml/{bwb_id}_{versie}.xml"

    def haal_document(self, bwb_id: str, versie: str) -> ET.Element:
        url = self._document_url(bwb_id, versie)
        response = self._client.get(url)
        response.raise_for_status()
        return ET.fromstring(response.content)

    def haal_artikel(
        self, bwb_id: str, artikel: str, *, peildatum: date | None = None
    ) -> Wetsartikel | None:
        versie = self.versie_op(bwb_id, peildatum)
        if versie is None:
            return None
        wortel = self.haal_document(bwb_id, versie)
        gezocht = _normaliseer_nr(artikel)

        for element in wortel.iter():
            if _strip_ns(element.tag) != "artikel":
                continue
            nummer = None
            titel = ""
            for kind in element:
                if _strip_ns(kind.tag) != "kop":
                    continue
                for sub in kind:
                    naam = _strip_ns(sub.tag)
                    if naam == "nr":
                        nummer = _tekst_van(sub)
                    elif naam in ("titel", "opschrift"):
                        titel = _tekst_van(sub)
            if nummer and _normaliseer_nr(nummer) == gezocht:
                return Wetsartikel(
                    bwb_id=bwb_id,
                    artikel=artikel,
                    titel=titel or f"Artikel {artikel}",
                    tekst=_tekst_van(element),
                    versiedatum=versie,
                    url=f"https://wetten.overheid.nl/{bwb_id}/{versie}#artikel{artikel}",
                )
        return None

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WettenClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
