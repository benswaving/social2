"""De controles die voorkomen dat een concept met verzonnen inhoud de deur uitgaat."""

from app.agent.guardrails import controleer_concept


class _Argument:
    def __init__(self, stelling: str) -> None:
        self.stelling = stelling


def _codes(rapport) -> set[str]:
    return {b.code for b in rapport.bevindingen}


def test_blokkeert_vindplaats_buiten_kennisbank():
    rapport = controleer_concept(
        "Op grond van artikel 6:217 BW bestaat de overeenkomst. Zie ook ECLI:NL:HR:2020:1111.",
        toegestane_vindplaatsen={"art. 6:217 BW"},
        brontekst="",
        argumenten=[],
    )
    assert rapport.geblokkeerd
    assert "vindplaats_buiten_kennisbank" in _codes(rapport)
    bevinding = next(b for b in rapport.bevindingen if b.code == "vindplaats_buiten_kennisbank")
    assert bevinding.details == ["ECLI:NL:HR:2020:1111"]


def test_laat_toegestane_vindplaats_door():
    rapport = controleer_concept(
        "Op grond van artikel 6:217 BW komt de overeenkomst tot stand.",
        toegestane_vindplaatsen={"art. 6:217 BW"},
        brontekst="",
        argumenten=[],
    )
    assert not rapport.geblokkeerd


def test_blokkeert_bedrag_dat_niet_in_het_dossier_staat():
    rapport = controleer_concept(
        "U bent ons € 999,00 verschuldigd.",
        toegestane_vindplaatsen=set(),
        brontekst="De vordering bedraagt € 1.284,55.",
        argumenten=[],
    )
    assert rapport.geblokkeerd
    assert "bedrag_niet_uit_dossier" in _codes(rapport)


def test_blokkeert_ongepaste_toon():
    rapport = controleer_concept(
        "Uw brief is kennelijk AI-gegenereerd en daarom onzin.",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[],
    )
    assert rapport.geblokkeerd
    assert "toon" in _codes(rapport)


def test_waarschuwt_bij_onbehandeld_argument():
    rapport = controleer_concept(
        "Wij hebben uw brief ontvangen en danken u daarvoor.",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[_Argument("Het pand staat leeg sinds maart 2022 en is inmiddels gesloopt")],
    )
    assert not rapport.geblokkeerd  # waarschuwing, geen blokkade
    assert "argument_niet_behandeld" in _codes(rapport)


def test_blokkeert_interne_werkinstructie_in_de_brief():
    """Interne aanwijzingen uit de taxonomie mogen de klant nooit bereiken."""
    rapport = controleer_concept(
        "Wij hebben uw bezwaar ontvangen. Gemengde feiten- en rechtsvraag. Nooit standaard "
        "afwijzen; laat een jurist de opeisbaarheidsdata nalopen.",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[],
        interne_instructies=[
            "Gemengde feiten- en rechtsvraag. Nooit standaard afwijzen; laat een jurist de "
            "opeisbaarheidsdata en de stuitingsbrieven nalopen."
        ],
    )
    assert rapport.geblokkeerd
    assert "interne_instructie_in_brief" in _codes(rapport)


def test_normale_brief_raakt_de_instructiecontrole_niet():
    rapport = controleer_concept(
        "Wij hebben uw bezwaar ontvangen en onderzoeken of de vordering is verjaard.",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[],
        interne_instructies=["Nooit standaard afwijzen; laat een jurist de stuitingsbrieven nalopen."],
    )
    assert not rapport.geblokkeerd


class _Volledig:
    """Argument zoals het bij de controle aankomt, met alle signalen."""

    def __init__(self, volgnummer, stelling, standpunt="", citaat=""):
        self.volgnummer = volgnummer
        self.stelling = stelling
        self.standpunt = standpunt
        self.citaat = citaat


def test_genummerde_alinea_telt_als_behandeld():
    """Een brief mag het bezwaar parafraseren in plaats van het na te praten."""
    brief = (
        "Geachte heer,\n\nPunt 1\nWij lichten toe waarom de betalingsverplichting blijft "
        "bestaan.\n\nPunt 2\nDit onderzoeken wij nog.\n"
    )
    rapport = controleer_concept(
        brief,
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[
            _Volledig(1, "Pseudojuridische constructie (soevereine burger e.d.)"),
            _Volledig(2, "Het pand staat leeg / is gesloopt"),
        ],
    )
    assert "argument_niet_behandeld" not in _codes(rapport)


def test_standpunt_van_de_afdeling_telt_ook_als_behandeld():
    rapport = controleer_concept(
        "Wij lichten toe dat de aansluitvergoeding niet verbruiksafhankelijk is.",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[
            _Volledig(
                1,
                "Ik verbruik niets",
                standpunt="De aansluitvergoeding is niet verbruiksafhankelijk.",
            )
        ],
    )
    assert "argument_niet_behandeld" not in _codes(rapport)


def test_echt_overgeslagen_argument_wordt_nog_steeds_gemeld():
    rapport = controleer_concept(
        "Geachte heer,\n\nWij hebben uw brief ontvangen en danken u daarvoor.\n",
        toegestane_vindplaatsen=set(),
        brontekst="",
        argumenten=[_Volledig(1, "De vordering is verjaard", standpunt="Verjaring van periodieke betalingen")],
    )
    assert "argument_niet_behandeld" in _codes(rapport)
