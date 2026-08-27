"""Postbus-commando's.

    python -m app.postbus test       # verbinding en mappen controleren, leest niets
    python -m app.postbus ophalen    # ongelezen berichten binnenhalen

`test` raakt niets aan: het opent de map alleen-lezen en telt. Begin daarmee
voordat er echte post door de molen gaat, en zet `OA_IMAP_MAX_PER_RUN` de eerste
keren laag.
"""

from __future__ import annotations

import argparse

from .config import get_settings
from .db import init_db, session_scope
from .ingest.imap_client import test_verbinding
from .ingest.intake import haal_postbus_op
from .models import CaseStatus
from .worker import meld_aan


def cmd_test(_: argparse.Namespace) -> int:
    try:
        uitkomst = test_verbinding()
    except Exception as exc:
        print(f"Verbinding mislukt: {exc.__class__.__name__}: {exc}")
        return 2

    print(f"Verbonden met {uitkomst['host']}, map '{uitkomst['map']}'.")
    print(f"  ongelezen : {uitkomst['ongelezen']}")
    print(f"  totaal    : {uitkomst['totaal']}")
    settings = get_settings()
    if uitkomst["verwerkt_map_bestaat"]:
        print(f"  verwerkt-map '{settings.imap_processed_folder}' bestaat")
    else:
        print(
            f"  LET OP: map '{settings.imap_processed_folder}' bestaat niet. "
            "Maak hem aan, anders blijven verwerkte berichten in de inbox staan."
        )
    print("\nEr is niets gelezen, gemarkeerd of verplaatst.")
    return 0


def cmd_ophalen(args: argparse.Namespace) -> int:
    init_db()
    with session_scope() as session:
        try:
            bezwaren = haal_postbus_op(session, args.maximum)
        except RuntimeError as exc:
            print(f"Ophalen mislukt: {exc}")
            return 2

        aangemeld = 0
        for bezwaar in bezwaren:
            if bezwaar.status == CaseStatus.NIEUW:
                meld_aan(session, bezwaar.id)
                aangemeld += 1

    print(f"{len(bezwaren)} bericht(en) opgehaald, {aangemeld} in de wachtrij gezet.")
    print("De werker pakt ze op (`python -m app.worker`).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.postbus", description=__doc__)
    sub = parser.add_subparsers(dest="commando", required=True)

    p = sub.add_parser("test", help="verbinding controleren zonder iets te lezen")
    p.set_defaults(func=cmd_test)

    p = sub.add_parser("ophalen", help="ongelezen berichten binnenhalen")
    p.add_argument("--maximum", type=int, default=None)
    p.set_defaults(func=cmd_ophalen)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
