"""Vult een demo-database, zodat de werkvoorraad iets te laten zien heeft.

    OA_DATABASE_URL="sqlite:///demo.db" python -m app.demo

Gebruikt de voorbeeldbrieven uit tests/fixtures. Bedoeld om de tool te tonen en
om een nieuwe medewerker de schermen te laten zien - niet voor productie.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from .agent.pipeline import verwerk_bezwaar
from .db import init_db, session_scope
from .ingest.intake import uit_tekst
from .knowledge.loader import seed_sources
from .models import Objection, Source, Verification

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

# Bronnen die in een echte opstelling door `sync wetten` zijn opgehaald en door
# een jurist geaccordeerd. Hier alvast gezet zodat de conceptbrieven vindplaatsen
# bevatten en het scherm laat zien hoe dat eruitziet.
GEACCORDEERD = {
    "bw6-217": "Een overeenkomst komt tot stand door een aanbod en de aanvaarding daarvan.",
    "bw3-35": (
        "Tegen hem die eens anders verklaring of gedraging heeft opgevat als een tot hem "
        "gerichte verklaring van een bepaalde strekking, kan geen beroep worden gedaan op "
        "het ontbreken van een met deze verklaring overeenstemmende wil."
    ),
    "bw3-308": "Rechtsvorderingen tot betaling van periodiek verschuldigde bedragen verjaren.",
    "bw6-234": "De gebruiker biedt een redelijke mogelijkheid om van de voorwaarden kennis te nemen.",
}

# Een ECLI die niet blijkt te bestaan; zo staat hij in de kennisbank nadat
# `sync ecli` hem heeft opgezocht.
NIET_BESTAANDE_UITSPRAAK = "ECLI:NL:HR:2019:1423"


def main() -> int:
    init_db()
    with session_scope() as session:
        seed_sources(session)

        for key, tekst in GEACCORDEERD.items():
            bron = session.scalar(select(Source).where(Source.key == key))
            if bron is not None:
                bron.tekst = tekst
                bron.verificatie = Verification.HANDMATIG
                bron.verificatie_toelichting = "Opgehaald bij KOOP en geaccordeerd (demo)"

        if not session.scalar(
            select(Source).where(Source.vindplaats == NIET_BESTAANDE_UITSPRAAK)
        ):
            session.add(
                Source(
                    key=NIET_BESTAANDE_UITSPRAAK.lower().replace(":", "-"),
                    soort="jurisprudentie",
                    titel="Niet gevonden bij de Rechtspraak",
                    vindplaats=NIET_BESTAANDE_UITSPRAAK,
                    verificatie=Verification.NIET_GEVONDEN,
                    verificatie_toelichting="Opgezocht via `sync ecli`; levert geen uitspraak op.",
                )
            )
        session.commit()

        brieven = [
            ("pseudojuridisch.txt", "J. de Vries"),
            ("terecht_bezwaar.txt", "M. Jansen"),
            ("verjaring_en_incasso.txt", "P. Bakker"),
        ]
        for bestand, naam in brieven:
            pad = FIXTURES / bestand
            if not pad.exists():
                continue
            objection = uit_tekst(session, pad.read_text(encoding="utf-8"), afzender_naam=naam)
            verwerk_bezwaar(session, objection, online=False)

        aantal = session.scalar(select(Objection).order_by(Objection.id.desc()))
        print(f"Demo klaar. Laatste dossier: {aantal.id if aantal else 0}")
        print("Start de tool met: uvicorn app.main:app --port 8100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
