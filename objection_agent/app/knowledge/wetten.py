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


@dataclass(frozen=True)
class RuwArtikel:
    nummer: str
    titel: str
    tekst: str


def lees_artikelen(wortel: ET.Element) -> list[RuwArtikel]:
    """Alle artikelen uit een BWB-document, met hun eigen nummer en tekst."""
    artikelen: list[RuwArtikel] = []
    for element in wortel.iter():
        if _strip_ns(element.tag) != "artikel":
            continue
        nummer = ""
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
        if nummer:
            artikelen.append(RuwArtikel(nummer=nummer, titel=titel, tekst=_tekst_van(element)))
    return artikelen


def doorzoek(
    artikelen: list[RuwArtikel],
    verplicht: list[str],
    trefwoorden: list[str],
    *,
    uitsluiten: list[str] | None = None,
    maximum: int = 5,
    minimale_score: int = 1,
) -> list[RuwArtikel]:
    """Rangschikt artikelen op onderwerp.

    Elk woord uit `verplicht` moet voorkomen, geen enkel woord uit `uitsluiten`, en
    `trefwoorden` bepalen de volgorde. Een artikel dat geen enkel trefwoord raakt
    haalt de drempel niet: dat is meestal een artikel dat toevallig dezelfde
    begrippen noemt, zoals een tariefbepaling die 'netbeheerder' en 'aansluiting'
    bevat maar niet over de aansluittaak gaat.

    Bewust simpel en deterministisch: de uitkomst moet voor een jurist na te lopen
    zijn, en een artikel dat hier bovenaan komt is nog steeds een voorstel.
    """
    uitsluiten = uitsluiten or []
    gescoord: list[tuple[int, int, RuwArtikel]] = []
    for artikel in artikelen:
        inhoud = f"{artikel.titel} {artikel.tekst}".lower()
        if not all(woord.lower() in inhoud for woord in verplicht):
            continue
        if any(woord.lower() in inhoud for woord in uitsluiten):
            continue
        score = sum(inhoud.count(woord.lower()) for woord in trefwoorden)
        # Een treffer in de kop van het artikel zegt meer dan een losse vermelding
        # ergens in een lid.
        score += sum(3 for woord in trefwoorden if woord.lower() in artikel.titel.lower())
        if score < minimale_score:
            continue
        gescoord.append((score, -len(artikel.tekst), artikel))

    gescoord.sort(key=lambda rij: (rij[0], rij[1]), reverse=True)
    return [artikel for _, _, artikel in gescoord[:maximum]]


def _naar_wetsartikel(ruw: RuwArtikel, bwb_id: str, versie: str) -> Wetsartikel:
    return Wetsartikel(
        bwb_id=bwb_id,
        artikel=ruw.nummer,
        titel=ruw.titel or f"Artikel {ruw.nummer}",
        tekst=ruw.tekst,
        versiedatum=versie,
        url=f"https://wetten.overheid.nl/{bwb_id}/{versie}#artikel{ruw.nummer}",
    )


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
        for gevonden in lees_artikelen(wortel):
            if _normaliseer_nr(gevonden.nummer) == gezocht:
                return _naar_wetsartikel(gevonden, bwb_id, versie)
        return None

    def doorzoek_artikelen(
        self,
        bwb_id: str,
        *,
        verplicht: list[str],
        trefwoorden: list[str],
        uitsluiten: list[str] | None = None,
        peildatum: date | None = None,
        maximum: int = 5,
    ) -> list[Wetsartikel]:
        """Zoekt de artikelen op die over een onderwerp gaan.

        Hiermee hoeft niemand een artikelnummer uit het hoofd op te schrijven: het
        nummer komt uit de opgehaalde wettekst zelf.
        """
        versie = self.versie_op(bwb_id, peildatum)
        if versie is None:
            return []
        wortel = self.haal_document(bwb_id, versie)
        treffers = doorzoek(
            lees_artikelen(wortel),
            verplicht,
            trefwoorden,
            uitsluiten=uitsluiten,
            maximum=maximum,
        )
        return [_naar_wetsartikel(t, bwb_id, versie) for t in treffers]

    def alle_artikelen(
        self, bwb_id: str, *, peildatum: date | None = None
    ) -> list[Wetsartikel]:
        versie = self.versie_op(bwb_id, peildatum)
        if versie is None:
            return []
        wortel = self.haal_document(bwb_id, versie)
        return [_naar_wetsartikel(a, bwb_id, versie) for a in lees_artikelen(wortel)]

    def zoek_bwb_id(self, titel: str, *, maximum: int = 10) -> list[tuple[str, str]]:
        """Zoekt een BWB-id op titel via de SRU-dienst van KOOP.

        Voor regelingen waarvan het id nog niet in de seed staat, zoals de
        Aansluit- en transportcode elektriciteit.
        """
        response = self._client.get(
            "https://repository.overheid.nl/sru",
            params={
                "operation": "searchRetrieve",
                "version": "2.0",
                "maximumRecords": maximum,
                "query": f'c.product-area==officielepublicaties AND dt.title all "{titel}"',
            },
        )
        response.raise_for_status()
        wortel = ET.fromstring(response.content)

        gevonden: list[tuple[str, str]] = []
        huidige_titel = ""
        for element in wortel.iter():
            naam = _strip_ns(element.tag)
            tekst = (element.text or "").strip()
            if naam == "title" and tekst:
                huidige_titel = tekst
            elif tekst.startswith("BWBR"):
                gevonden.append((tekst, huidige_titel))
            elif naam == "identifier" and "BWBR" in tekst:
                match = re.search(r"BWBR\d+", tekst)
                if match:
                    gevonden.append((match.group(0), huidige_titel))
        # dubbele ids ontdubbelen met behoud van volgorde
        uniek: dict[str, str] = {}
        for bwb_id, naam in gevonden:
            uniek.setdefault(bwb_id, naam)
        return list(uniek.items())

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "WettenClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
