"""CLI voor het vullen en verifieren van de kennisbank.

    python -m app.knowledge.sync seed             # seed-items inladen (offline)
    python -m app.knowledge.sync wetten           # wetteksten ophalen en verifieren
    python -m app.knowledge.sync jurisprudentie   # kandidaat-uitspraken oogsten
    python -m app.knowledge.sync ecli ECLI:NL:...  # losse uitspraak toevoegen/verifieren
    python -m app.knowledge.sync status           # wat is citeerbaar en wat niet
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import func, select

from ..db import init_db, session_scope
from ..models import Source, SourceKind, Verification
from .loader import load_jurisprudentieprofielen, load_wetsartikelen, seed_sources
from .rechtspraak import RechtspraakClient
from .wetten import WettenClient


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_seed(args: argparse.Namespace) -> int:
    with session_scope() as session:
        resultaat = seed_sources(session, overschrijf=args.overschrijf)
    print(f"Seed geladen: {resultaat['toegevoegd']} nieuw, {resultaat['bijgewerkt']} bijgewerkt.")
    print("Let op: alles staat op `ongeverifieerd` en is dus nog niet citeerbaar.")
    print("Volgende stap: python -m app.knowledge.sync wetten")
    return 0


def cmd_wetten(args: argparse.Namespace) -> int:
    data = load_wetsartikelen()
    wetten = {w["afkorting"]: w for w in data.get("wetten", []) if w.get("afkorting")}
    peildatum = date.fromisoformat(args.peildatum) if args.peildatum else None

    bevestigd = niet_gevonden = overgeslagen = 0
    with WettenClient() as client, session_scope() as session:
        for artikel in data.get("artikelen", []):
            wet = wetten.get(artikel.get("wet") or "")
            bron = session.scalar(select(Source).where(Source.key == artikel["key"]))
            if bron is None:
                continue
            if not wet or not wet.get("bwb_id") or not artikel.get("artikel"):
                bron.verificatie = Verification.ONGEVERIFIEERD
                bron.verificatie_toelichting = (
                    "BWB-id of artikelnummer ontbreekt in de seed; vul dit aan in "
                    "app/knowledge/seed/wetsartikelen.yaml. Niet citeerbaar."
                )
                overgeslagen += 1
                continue

            try:
                gevonden = client.haal_artikel(
                    wet["bwb_id"], artikel["artikel"], peildatum=peildatum
                )
            except httpx.HTTPError as exc:
                print(f"  ! {artikel['key']}: netwerkfout ({exc.__class__.__name__})", file=sys.stderr)
                continue

            bron.laatst_gecontroleerd = _now()
            if gevonden is None:
                bron.verificatie = Verification.NIET_GEVONDEN
                bron.verificatie_toelichting = (
                    f"Artikel {artikel['artikel']} niet aangetroffen in {wet['bwb_id']}"
                    + (f" op {peildatum}" if peildatum else "")
                )
                niet_gevonden += 1
                print(f"  x {artikel['key']}: NIET GEVONDEN -> wordt niet geciteerd")
            else:
                bron.tekst = gevonden.tekst
                bron.url = gevonden.url
                bron.titel = gevonden.titel or bron.titel
                bron.verificatie = Verification.BEVESTIGD
                bron.verificatie_toelichting = f"Opgehaald bij KOOP, versie {gevonden.versiedatum}"
                bevestigd += 1

    print(f"Wetteksten: {bevestigd} bevestigd, {niet_gevonden} niet gevonden, {overgeslagen} onvolledig.")
    return 0


def cmd_jurisprudentie(args: argparse.Namespace) -> int:
    profielen = load_jurisprudentieprofielen()
    standaard = profielen.get("standaard", {})
    vanaf = date.fromisoformat(standaard.get("vanaf", "2012-01-01"))
    maximum = int(standaard.get("max_per_profiel", 25))

    toegevoegd = 0
    with RechtspraakClient() as client, session_scope() as session:
        try:
            ruwe = client.zoek(
                rechtsgebied=standaard.get("rechtsgebied"), vanaf=vanaf, maximum=args.batch
            )
        except httpx.HTTPError as exc:
            print(f"Netwerkfout bij data.rechtspraak.nl: {exc}", file=sys.stderr)
            return 2

        print(f"{len(ruwe)} uitspraken opgehaald uit de open dataset.")
        for profiel in profielen.get("profielen", []):
            treffers = client.filter_op_trefwoorden(ruwe, profiel.get("zoektermen", []))[:maximum]
            print(f"  {profiel['key']}: {len(treffers)} kandidaten")
            for ecli, titel, samenvatting in treffers:
                key = ecli.lower().replace(":", "-")
                if session.scalar(select(Source).where(Source.key == key)):
                    continue
                session.add(
                    Source(
                        key=key,
                        soort=SourceKind.JURISPRUDENTIE,
                        titel=titel[:500],
                        vindplaats=ecli,
                        samenvatting=samenvatting,
                        url=f"https://uitspraken.rechtspraak.nl/details?id={ecli}",
                        # Bewust NIET `bevestigd`: de uitspraak bestaat, maar of ze
                        # steun biedt voor ons standpunt beoordeelt een jurist.
                        verificatie=Verification.ONGEVERIFIEERD,
                        verificatie_toelichting=(
                            "Kandidaat uit geautomatiseerde voorselectie. Zet op `handmatig` "
                            "na beoordeling door een jurist; pas dan citeerbaar."
                        ),
                        categorieen=list(profiel.get("categorieen") or []),
                        tags=["kandidaat", profiel["key"]],
                        toegevoegd_door="sync",
                    )
                )
                toegevoegd += 1

    print(f"{toegevoegd} kandidaat-uitspraken toegevoegd. Beoordeling door een jurist is vereist.")
    return 0


def cmd_ecli(args: argparse.Namespace) -> int:
    with RechtspraakClient() as client, session_scope() as session:
        for ecli in args.ecli:
            uitspraak = client.haal_uitspraak(ecli)
            key = ecli.lower().replace(":", "-")
            bron = session.scalar(select(Source).where(Source.key == key))
            if uitspraak is None:
                print(f"  x {ecli}: bestaat niet of is niet raadpleegbaar")
                if bron is not None:
                    bron.verificatie = Verification.NIET_GEVONDEN
                    bron.laatst_gecontroleerd = _now()
                continue
            if bron is None:
                bron = Source(key=key, soort=SourceKind.JURISPRUDENTIE, toegevoegd_door="handmatig")
                session.add(bron)
            bron.titel = uitspraak.titel[:500]
            bron.vindplaats = uitspraak.ecli
            bron.tekst = uitspraak.tekst
            bron.samenvatting = uitspraak.samenvatting
            bron.url = uitspraak.url
            bron.categorieen = list(args.categorie or [])
            bron.verificatie = Verification.HANDMATIG if args.accorderen else Verification.ONGEVERIFIEERD
            bron.verificatie_toelichting = (
                "Handmatig toegevoegd en geaccordeerd" if args.accorderen
                else "Opgehaald; nog te accorderen door een jurist"
            )
            bron.laatst_gecontroleerd = _now()
            print(f"  v {ecli}: {uitspraak.titel[:80]}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    with session_scope() as session:
        rijen = session.execute(
            select(Source.soort, Source.verificatie, func.count()).group_by(
                Source.soort, Source.verificatie
            )
        ).all()
    if not rijen:
        print("Kennisbank is leeg. Draai eerst: python -m app.knowledge.sync seed")
        return 0
    print(f"{'soort':<18}{'verificatie':<18}{'aantal':>7}")
    citeerbaar = 0
    for soort, verificatie, aantal in rijen:
        print(f"{soort.value:<18}{verificatie.value:<18}{aantal:>7}")
        if verificatie in (Verification.BEVESTIGD, Verification.HANDMATIG):
            citeerbaar += aantal
    print(f"\nCiteerbaar in uitgaande brieven: {citeerbaar}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.knowledge.sync", description=__doc__)
    sub = parser.add_subparsers(dest="commando", required=True)

    p = sub.add_parser("seed", help="seed-items inladen")
    p.add_argument("--overschrijf", action="store_true")
    p.set_defaults(func=cmd_seed)

    p = sub.add_parser("wetten", help="wetteksten ophalen en verifieren")
    p.add_argument("--peildatum", help="YYYY-MM-DD; welke wetsversie moet gelden")
    p.set_defaults(func=cmd_wetten)

    p = sub.add_parser("jurisprudentie", help="kandidaat-uitspraken oogsten")
    p.add_argument("--batch", type=int, default=1000, help="hoeveel uitspraken voorselecteren")
    p.set_defaults(func=cmd_jurisprudentie)

    p = sub.add_parser("ecli", help="losse uitspraak toevoegen of verifieren")
    p.add_argument("ecli", nargs="+")
    p.add_argument("--categorie", action="append", help="bezwaarcategorie (meermaals mogelijk)")
    p.add_argument("--accorderen", action="store_true", help="direct als geaccordeerd markeren")
    p.set_defaults(func=cmd_ecli)

    p = sub.add_parser("status", help="overzicht van de kennisbank")
    p.set_defaults(func=cmd_status)

    args = parser.parse_args(argv)
    init_db()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
