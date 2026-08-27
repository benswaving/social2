"""CLI voor het vullen en verifieren van de kennisbank.

    python -m app.knowledge.sync seed             # seed-items inladen (offline)
    python -m app.knowledge.sync wetten           # wetteksten ophalen en verifieren
    python -m app.knowledge.sync artikelen        # artikelnummers laten opzoeken door de wet zelf
    python -m app.knowledge.sync wet-volledig BWBR0050714   # hele wet doorzoekbaar inladen
    python -m app.knowledge.sync resolve-bwb "titel"        # BWB-id van een regeling opzoeken
    python -m app.knowledge.sync jurisprudentie   # kandidaat-uitspraken oogsten
    python -m app.knowledge.sync ecli ECLI:NL:...  # losse uitspraak toevoegen/verifieren
    python -m app.knowledge.sync status           # wat is citeerbaar en wat niet
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone

import httpx
from sqlalchemy import func, select

from ..db import init_db, session_scope
from ..models import Source, SourceKind, Verification
from .loader import _as_date, load_jurisprudentieprofielen, load_wetsartikelen, seed_sources
from .rechtspraak import RechtspraakClient
from .wetten import WettenClient, doorzoek, lees_artikelen


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cmd_seed(args: argparse.Namespace) -> int:
    with session_scope() as session:
        resultaat = seed_sources(session, overschrijf=args.overschrijf)
    print(f"Seed geladen: {resultaat['toegevoegd']} nieuw, {resultaat['bijgewerkt']} bijgewerkt.")
    print("Let op: alles staat op `ongeverifieerd` en is dus nog niet citeerbaar.")
    print("Volgende stappen: `sync wetten` (vaste artikelnummers) en daarna")
    print("`sync artikelen` (laat de Energiewet zelf de nummers opleveren).")
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



def _toon_treffer(zoeker_key: str, volgnummer: int, treffer, vindplaats: str) -> None:
    fragment = " ".join(treffer.tekst.split())[:220]
    print(f"      {volgnummer}. {vindplaats}")
    if treffer.titel:
        print(f"         kop: {treffer.titel}")
    print(f"         {fragment}{'...' if len(treffer.tekst) > 220 else ''}")


def cmd_artikelen(args: argparse.Namespace) -> int:
    """Laat de wettekst zelf de artikelnummers opleveren.

    Dit is de plek waar de Energiewet binnenkomt: niet als een lijst nummers uit
    iemands hoofd, maar als de artikelen die bij het opgehaalde BWB-document
    daadwerkelijk over het onderwerp blijken te gaan.

    Drie draaistanden:
      (standaard)   haalt de wet op bij het KOOP-repository
      --droogloop   toont alleen wat er gezocht gaat worden, zonder netwerk
      --bestand     zoekt in een lokaal opgeslagen BWB-XML, voor omgevingen
                    zonder uitgaand netwerk
    """
    data = load_wetsartikelen()
    wetten = {w["afkorting"]: w for w in data.get("wetten", []) if w.get("afkorting")}
    zoekers = data.get("artikelzoekers", [])
    peildatum = date.fromisoformat(args.peildatum) if args.peildatum else None
    if args.zoeker:
        zoekers = [z for z in zoekers if z["key"] in set(args.zoeker)]

    # --- droogloop: het zoekplan, zonder een enkele netwerkaanroep ------
    if args.droogloop:
        print(f"Zoekplan ({len(zoekers)} zoekopdrachten), peildatum {peildatum or 'huidige versie'}:\n")
        onbruikbaar = 0
        for zoeker in zoekers:
            wet = wetten.get(zoeker.get("wet") or "")
            bwb = (wet or {}).get("bwb_id")
            status = bwb or "GEEN BWB-ID -> wordt overgeslagen"
            if not bwb:
                onbruikbaar += 1
            print(f"  {zoeker['key']}")
            print(f"      wet          {zoeker.get('wet')} ({status})")
            print(f"      doel         {zoeker.get('doel', '')}")
            print(f"      verplicht    alle van: {', '.join(zoeker.get('verplicht') or [])}")
            print(f"      rangschikt   {', '.join(zoeker.get('trefwoorden') or [])}")
            if zoeker.get("uitsluiten"):
                print(f"      uitsluiten   {', '.join(zoeker['uitsluiten'])}")
            print(f"      categorieen  {', '.join(zoeker.get('categorieen') or [])}")
            print(f"      max treffers {zoeker.get('maximum', 5)}\n")
        print(f"{len(zoekers) - onbruikbaar} uitvoerbaar, {onbruikbaar} zonder BWB-id.")
        print("Draai zonder --droogloop op een omgeving met internettoegang.")
        return 0

    # --- lokaal bestand: dezelfde zoeklogica, andere bron ----------------
    if args.bestand:
        wortel = ET.parse(args.bestand).getroot()
        artikelen = lees_artikelen(wortel)
        print(f"{len(artikelen)} artikelen gelezen uit {args.bestand}\n")
        gevonden_totaal = 0
        with session_scope() as session:
            for zoeker in zoekers:
                wet = wetten.get(zoeker.get("wet") or "") or {}
                treffers = doorzoek(
                    artikelen,
                    list(zoeker.get("verplicht") or []),
                    list(zoeker.get("trefwoorden") or []),
                    uitsluiten=list(zoeker.get("uitsluiten") or []),
                    maximum=int(zoeker.get("maximum", 5)),
                )
                print(f"  {zoeker['key']}: {len(treffers)} treffer(s)")
                for volgnummer, treffer in enumerate(treffers, start=1):
                    vindplaats = f"art. {treffer.nummer} {wet.get('naam', zoeker.get('wet'))}"
                    _toon_treffer(zoeker["key"], volgnummer, treffer, vindplaats)
                    if args.opslaan:
                        _bewaar_treffer(session, zoeker, wet, treffer, vindplaats,
                                        volgnummer, "lokaal bestand", None)
                        gevonden_totaal += 1
                print()
        if args.opslaan:
            print(f"{gevonden_totaal} artikelen opgenomen als `auto-gemapt`.")
        else:
            print("Alleen getoond. Gebruik --opslaan om ze in de kennisbank te zetten.")
        return 0

    # --- normale run: ophalen bij de officiele bron ----------------------
    toegevoegd = 0
    with WettenClient() as client, session_scope() as session:
        for zoeker in zoekers:
            wet = wetten.get(zoeker.get("wet") or "")
            if not wet or not wet.get("bwb_id"):
                print(
                    f"  - {zoeker['key']}: BWB-id van {zoeker.get('wet')} ontbreekt; "
                    f"draai eerst `resolve-bwb \"{(wet or {}).get('naam', zoeker.get('wet'))}\"`"
                )
                continue

            try:
                treffers = client.doorzoek_artikelen(
                    wet["bwb_id"],
                    verplicht=list(zoeker.get("verplicht") or []),
                    trefwoorden=list(zoeker.get("trefwoorden") or []),
                    uitsluiten=list(zoeker.get("uitsluiten") or []),
                    peildatum=peildatum,
                    maximum=int(zoeker.get("maximum", 5)),
                )
            except httpx.HTTPError as exc:
                print(f"  ! {zoeker['key']}: netwerkfout ({exc.__class__.__name__}: {exc})", file=sys.stderr)
                continue

            if not treffers:
                print(f"  x {zoeker['key']}: geen artikel gevonden dat aan de eisen voldoet")
                continue

            print(f"  v {zoeker['key']}: {len(treffers)} treffer(s)")
            for volgnummer, treffer in enumerate(treffers, start=1):
                vindplaats = f"art. {treffer.artikel} {wet['naam']}"
                _toon_treffer(zoeker["key"], volgnummer, treffer, vindplaats)
                _bewaar_treffer(
                    session, zoeker, wet, treffer, vindplaats, volgnummer,
                    wet["bwb_id"], treffer.versiedatum, url=treffer.url,
                )
                toegevoegd += 1
            print()

    if not toegevoegd:
        print("Geen artikelen opgenomen.")
        return 1
    print(f"{toegevoegd} artikelen opgenomen.")
    print("Deze staan als `auto-gemapt` in de kennisbank en zijn nog niet citeerbaar.")
    print("Loop ze na op /kennisbank en accordeer wat klopt.")
    return 0


def _bewaar_treffer(
    session,
    zoeker: dict,
    wet: dict,
    treffer,
    vindplaats: str,
    volgnummer: int,
    herkomst: str,
    versiedatum: str | None,
    url: str | None = None,
) -> None:
    nummer = getattr(treffer, "artikel", None) or treffer.nummer
    key = f"{zoeker['key']}-{nummer.replace(' ', '')}"
    bron = session.scalar(select(Source).where(Source.key == key))
    if bron is None:
        bron = Source(key=key, soort=SourceKind.WET, toegevoegd_door="sync")
        session.add(bron)
    bron.titel = (treffer.titel or vindplaats)[:500]
    bron.vindplaats = vindplaats
    bron.tekst = treffer.tekst
    bron.samenvatting = zoeker.get("doel")
    bron.url = url
    bron.geldig_vanaf = _as_date(wet.get("geldig_vanaf"))
    bron.geldig_tot = _as_date(wet.get("geldig_tot"))
    bron.vervangen_door = wet.get("vervangen_door")
    bron.categorieen = list(zoeker.get("categorieen") or [])
    # De tekst is echt en geverifieerd. Of dit artikel bij deze bezwaarcategorie
    # hoort, is een keuze van de zoekopdracht - en die beoordeelt een jurist
    # voordat de agent ermee argumenteert.
    bron.verificatie = Verification.BEVESTIGD
    bron.verificatie_toelichting = (
        f"Automatisch gevonden in {herkomst}"
        + (f" (versie {versiedatum})" if versiedatum else "")
        + f", treffer {volgnummer} voor zoekopdracht '{zoeker['key']}'. "
        "Tekst geverifieerd; koppeling aan de categorie nog te accorderen."
    )
    bron.tags = ["auto-gemapt", zoeker["key"]]
    bron.laatst_gecontroleerd = _now()


def cmd_wet_volledig(args: argparse.Namespace) -> int:
    """Laadt een hele wet in zodat een medewerker elk artikel kan opzoeken.

    Zonder categorieen: deze artikelen worden dus nooit vanzelf in een brief
    aangehaald. Ze staan er om op te zoeken, niet om mee te argumenteren.
    """
    peildatum = date.fromisoformat(args.peildatum) if args.peildatum else None
    with WettenClient() as client, session_scope() as session:
        try:
            artikelen = client.alle_artikelen(args.bwb_id, peildatum=peildatum)
        except httpx.HTTPError as exc:
            print(f"Netwerkfout: {exc}", file=sys.stderr)
            return 2

        toegevoegd = 0
        for artikel in artikelen:
            key = f"{args.bwb_id.lower()}-{artikel.artikel.replace(' ', '')}"
            if session.scalar(select(Source).where(Source.key == key)):
                continue
            session.add(
                Source(
                    key=key,
                    soort=SourceKind.WET,
                    titel=artikel.titel[:500],
                    vindplaats=f"art. {artikel.artikel} {args.naam or args.bwb_id}",
                    tekst=artikel.tekst,
                    url=artikel.url,
                    verificatie=Verification.BEVESTIGD,
                    verificatie_toelichting=f"Volledige inlading {args.bwb_id}, versie {artikel.versiedatum}",
                    categorieen=[],
                    tags=["volledige-inlading", args.bwb_id],
                    toegevoegd_door="sync",
                )
            )
            toegevoegd += 1

    print(f"{len(artikelen)} artikelen gelezen, {toegevoegd} nieuw opgenomen.")
    return 0


def cmd_resolve_bwb(args: argparse.Namespace) -> int:
    with WettenClient() as client:
        try:
            treffers = client.zoek_bwb_id(args.titel)
        except httpx.HTTPError as exc:
            print(f"Netwerkfout: {exc}", file=sys.stderr)
            return 2
    if not treffers:
        print(f"Geen BWB-id gevonden voor '{args.titel}'.")
        return 1
    print("Gevonden. Vul het juiste id in bij `wetten:` in wetsartikelen.yaml:\n")
    for bwb_id, titel in treffers:
        print(f"  - bwb_id: {bwb_id}\n    naam: \"{titel or args.titel}\"")
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

    p = sub.add_parser("artikelen", help="artikelnummers laten opzoeken in de wettekst")
    p.add_argument("--peildatum", help="YYYY-MM-DD; welke wetsversie moet gelden")
    p.add_argument("--zoeker", action="append", help="beperk tot deze zoekopdracht(en)")
    p.add_argument("--droogloop", action="store_true", help="toon alleen het zoekplan, zonder netwerk")
    p.add_argument("--bestand", help="zoek in een lokaal opgeslagen BWB-XML in plaats van online")
    p.add_argument("--opslaan", action="store_true", help="bij --bestand: treffers ook wegschrijven")
    p.set_defaults(func=cmd_artikelen)

    p = sub.add_parser("wet-volledig", help="een hele wet doorzoekbaar inladen")
    p.add_argument("bwb_id")
    p.add_argument("--naam", help="naam zoals die in de vindplaats moet komen")
    p.add_argument("--peildatum", help="YYYY-MM-DD")
    p.set_defaults(func=cmd_wet_volledig)

    p = sub.add_parser("resolve-bwb", help="BWB-id van een regeling opzoeken op titel")
    p.add_argument("titel")
    p.set_defaults(func=cmd_resolve_bwb)

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
