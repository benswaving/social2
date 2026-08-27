"""Jurisprudentie via de Open Data van de Rechtspraak.

Twee functies, met een bewust verschil in betrouwbaarheid:

1. `bestaat(ecli)` / `haal_uitspraak(ecli)` gebruiken het gedocumenteerde
   content-endpoint en zijn de kern van de bronnencontrole. Bestaat een ECLI niet,
   dan geeft dit endpoint geen document terug - en dat is precies wat we willen
   weten bij een brief die zich beroept op ECLI:NL:HR:2021:9999.

2. `zoek(...)` doorloopt de open dataset op rechtsgebied en periode en filtert
   daarna zelf op trefwoorden. De open data-zoekingang kent geen volledige
   tekstzoekfunctie, dus dit is bewust een grove voorselectie die kandidaten
   oplevert voor een jurist - geen vervanging van een echte zoekslag op
   uitspraken.rechtspraak.nl.

Niet live getest in de bouwomgeving: het netwerkbeleid daar blokkeerde
data.rechtspraak.nl. Draai `python -m app.knowledge.sync jurisprudentie --check`
als eerste stap op een omgeving met internettoegang.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date

import httpx

from ..config import get_settings

ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass(frozen=True)
class Uitspraak:
    ecli: str
    titel: str
    samenvatting: str
    instantie: str | None
    datum: str | None
    tekst: str
    url: str


def _tekst(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return " ".join(t.strip() for t in element.itertext() if t and t.strip())


class RechtspraakClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        settings = get_settings()
        self._zoek_url = settings.rechtspraak_search_url
        self._content_url = settings.rechtspraak_content_url
        self._client = client or httpx.Client(
            timeout=settings.knowledge_http_timeout,
            headers={"User-Agent": "ASC-bezwarenagent/1.0"},
        )

    # -- verificatie -----------------------------------------------------

    def haal_uitspraak(self, ecli: str) -> Uitspraak | None:
        """Haalt de volledige uitspraak op. `None` betekent: bestaat niet."""
        response = self._client.get(self._content_url, params={"id": ecli})
        if response.status_code == 404 or not response.content.strip():
            return None
        response.raise_for_status()
        try:
            wortel = ET.fromstring(response.content)
        except ET.ParseError:
            return None

        def vind(naam: str) -> ET.Element | None:
            for element in wortel.iter():
                if element.tag.rsplit("}", 1)[-1] == naam:
                    return element
            return None

        inhoud = vind("uitspraak") or vind("conclusie")
        samenvatting = _tekst(vind("inhoudsindicatie"))
        if inhoud is None and not samenvatting:
            return None  # leeg omhulsel: de ECLI is niet raadpleegbaar

        return Uitspraak(
            ecli=ecli.upper(),
            titel=_tekst(vind("title")) or ecli.upper(),
            samenvatting=samenvatting,
            instantie=_tekst(vind("creator")) or None,
            datum=_tekst(vind("date")) or None,
            tekst=_tekst(inhoud),
            url=f"https://uitspraken.rechtspraak.nl/details?id={ecli.upper()}",
        )

    def bestaat(self, ecli: str) -> bool:
        return self.haal_uitspraak(ecli) is not None

    # -- voorselectie ----------------------------------------------------

    def zoek(
        self,
        *,
        rechtsgebied: str | None = None,
        vanaf: date | None = None,
        tot: date | None = None,
        maximum: int = 100,
    ) -> list[tuple[str, str, str]]:
        """(ecli, titel, samenvatting) uit de open dataset."""
        params: dict[str, object] = {"max": maximum, "return": "DOC"}
        if rechtsgebied:
            params["subject"] = rechtsgebied
        datums = [d.isoformat() for d in (vanaf, tot) if d]
        if datums:
            params["date"] = datums

        response = self._client.get(self._zoek_url, params=params)
        response.raise_for_status()
        wortel = ET.fromstring(response.content)

        resultaten: list[tuple[str, str, str]] = []
        for entry in wortel.findall(f"{ATOM}entry"):
            ecli = _tekst(entry.find(f"{ATOM}id"))
            titel = _tekst(entry.find(f"{ATOM}title"))
            samenvatting = _tekst(entry.find(f"{ATOM}summary"))
            if ecli:
                resultaten.append((ecli.upper(), titel, samenvatting))
        return resultaten

    @staticmethod
    def filter_op_trefwoorden(
        resultaten: list[tuple[str, str, str]], zoektermen: list[str], *, minimaal: int = 2
    ) -> list[tuple[str, str, str]]:
        """Grove voorselectie: hoeveel losse woorden uit de zoekterm komen terug?"""
        woorden = {
            woord.lower()
            for term in zoektermen
            for woord in term.split()
            if len(woord) > 3
        }
        if not woorden:
            return resultaten

        gescoord = []
        for ecli, titel, samenvatting in resultaten:
            haystack = f"{titel} {samenvatting}".lower()
            treffers = sum(1 for woord in woorden if woord in haystack)
            if treffers >= minimaal:
                gescoord.append((treffers, (ecli, titel, samenvatting)))
        gescoord.sort(key=lambda paar: paar[0], reverse=True)
        return [item for _, item in gescoord]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "RechtspraakClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
