"""De artikelzoeker: de wettekst levert zelf het artikelnummer op.

Getest tegen een lokaal XML-fragment, zodat de logica controleerbaar is zonder
netwerktoegang tot het KOOP-repository.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest
import yaml

from app.knowledge.loader import SEED_DIR, load_wetsartikelen
from app.knowledge.wetten import doorzoek, lees_artikelen


@pytest.fixture()
def artikelen(fixtures_dir):
    wortel = ET.parse(fixtures_dir / "bwb_fragment.xml").getroot()
    return lees_artikelen(wortel)


def test_leest_alle_artikelen_met_nummer_en_tekst(artikelen):
    nummers = [a.nummer for a in artikelen]
    assert nummers == ["3.10", "3.11", "3.12", "4.20"]
    assert "aansluiting te" in artikelen[0].tekst
    assert artikelen[0].titel == "Taken van de netbeheerder"


def test_vindt_de_aansluittaak(artikelen):
    treffers = doorzoek(
        artikelen,
        verplicht=["netbeheerder", "aansluiting"],
        trefwoorden=["taak", "verzoek", "realiseren", "aangeslotene"],
        maximum=2,
    )
    assert treffers[0].nummer == "3.10"


def test_vindt_de_tariefbepaling(artikelen):
    treffers = doorzoek(
        artikelen,
        verplicht=["tarief"],
        trefwoorden=["ACM", "vaststellen", "in rekening", "transport"],
        maximum=3,
    )
    assert treffers[0].nummer == "4.20"


def test_verplichte_woorden_sluiten_artikelen_uit(artikelen):
    # 3.12 gaat over een vergoeding, maar noemt geen aansluiting.
    treffers = doorzoek(artikelen, verplicht=["aansluiting"], trefwoorden=["vergoeding"])
    assert "3.12" not in [t.nummer for t in treffers]


def test_geen_treffer_levert_lege_lijst(artikelen):
    assert doorzoek(artikelen, verplicht=["warmtenet"], trefwoorden=["tarief"]) == []


def test_titel_weegt_zwaarder_dan_losse_vermeldingen(artikelen):
    treffers = doorzoek(artikelen, verplicht=["netbeheerder"], trefwoorden=["transport"])
    assert treffers[0].nummer == "3.11"


# --- samenhang met de seed ------------------------------------------------


def test_elke_zoeker_verwijst_naar_een_bestaande_wet():
    data = load_wetsartikelen()
    afkortingen = {w["afkorting"] for w in data["wetten"] if w.get("afkorting")}
    for zoeker in data["artikelzoekers"]:
        assert zoeker["wet"] in afkortingen, zoeker["key"]
        assert zoeker.get("verplicht"), f"{zoeker['key']} zonder verplichte woorden"


def test_elke_zoeker_gebruikt_een_bestaande_categorie():
    taxonomie = yaml.safe_load((SEED_DIR / "taxonomie.yaml").read_text(encoding="utf-8"))
    bekend = set(taxonomie["categorieen"])
    for zoeker in load_wetsartikelen()["artikelzoekers"]:
        onbekend = set(zoeker.get("categorieen") or []) - bekend
        assert not onbekend, f"{zoeker['key']}: {onbekend}"


def test_seed_bevat_geen_verzonnen_artikelnummers_voor_de_energiewet():
    """De Energiewet komt binnen via zoekopdrachten, niet via ingetypte nummers."""
    data = load_wetsartikelen()
    energiewet_artikelen = [a for a in data["artikelen"] if a.get("wet") == "Ew"]
    assert energiewet_artikelen == []


def test_ingetrokken_wetten_hebben_een_einddatum_en_opvolger():
    wetten = {w["afkorting"]: w for w in load_wetsartikelen()["wetten"]}
    for afkorting in ("E-wet", "Gaswet"):
        assert wetten[afkorting]["geldig_tot"] == "2025-12-31"
        assert wetten[afkorting]["vervangen_door"] == "Ew"
    assert wetten["Ew"]["bwb_id"] == "BWBR0050714"
    assert wetten["Ew"]["geldig_vanaf"] == "2026-01-01"
