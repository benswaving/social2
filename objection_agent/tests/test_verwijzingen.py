"""Herkennen van vindplaatsen in een binnengekomen brief."""

from app.knowledge.store import vind_verwijzingen


def test_herkent_ecli_en_wetsartikelen(fixtures_dir):
    tekst = (fixtures_dir / "pseudojuridisch.txt").read_text(encoding="utf-8")
    verwijzingen = vind_verwijzingen(tekst)
    genormaliseerd = {v.genormaliseerd for v in verwijzingen}

    assert "ECLI:NL:HR:2019:1423" in genormaliseerd
    assert "ECLI:NL:GHAMS:2021:8899" in genormaliseerd
    assert "Awb 47" in genormaliseerd


def test_negeert_nummers_zonder_wetsnaam():
    # "artikel 3" zonder wet is niet te verifieren en mag geen verwijzing opleveren.
    assert vind_verwijzingen("Volgens artikel 3 heeft u ongelijk.") == []


def test_neemt_context_mee():
    verwijzingen = vind_verwijzingen("Zoals blijkt uit ECLI:NL:HR:2019:1423 is dit onjuist.")
    assert "blijkt uit" in verwijzingen[0].context
