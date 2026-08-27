"""Zet de kansinschattingen naast de werkelijke afloop.

De priors in `taxonomie.yaml` zijn ingeschat, niet gemeten. Zolang niemand
vastlegt hoe een dossier werkelijk afliep, blijft dat zo en is er niets om ze
aan te toetsen. Dit commando maakt dat zichtbaar per categorie:

    python -m app.kalibratie
    python -m app.kalibratie --vanaf 2026-01-01 --minimaal 20

Wat je zoekt is een categorie waar de inschatting structureel de andere kant op
wijst dan de afloop. Een categorie met `prior 0.10` waar de vordering in de
praktijk vaak wordt gecorrigeerd, wijst erop dat de afdeling daar bezwaren
afwijst die hout snijden. Dat is de dure fout, en dit is de enige manier waarop
die aan het licht komt.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import init_db, session_scope
from .knowledge.loader import load_taxonomie
from .models import Afloop, Argument, Objection

# Hoe zwaar telt een afloop mee als bevestiging dat de klant een punt had?
GEGROND = {
    Afloop.VORDERING_INGETROKKEN: 1.0,
    Afloop.DEELS_GECORRIGEERD: 0.5,
    Afloop.VORDERING_GEHANDHAAFD: 0.0,
    Afloop.GESCHIL: 0.5,  # onbeslist; telt half mee zodat het niet wegvalt
}


def verzamel(session: Session, *, vanaf: date | None = None) -> dict[str, dict]:
    stmt = (
        select(Argument, Objection)
        .join(Objection, Argument.objection_id == Objection.id)
        .where(Objection.afloop != Afloop.ONBEKEND)
    )
    if vanaf:
        stmt = stmt.where(Objection.ontvangen_op >= datetime(vanaf.year, vanaf.month, vanaf.day, tzinfo=timezone.utc))

    per_categorie: dict[str, dict] = {}
    for argument, objection in session.execute(stmt):
        regel = per_categorie.setdefault(
            argument.categorie, {"aantal": 0, "som_inschatting": 0.0, "som_afloop": 0.0}
        )
        regel["aantal"] += 1
        regel["som_inschatting"] += argument.merit_score or 0.0
        regel["som_afloop"] += GEGROND.get(objection.afloop, 0.0)
    return per_categorie


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.kalibratie", description=__doc__)
    parser.add_argument("--vanaf", help="YYYY-MM-DD; alleen dossiers vanaf deze datum")
    parser.add_argument(
        "--minimaal", type=int, default=10, help="minimaal aantal dossiers voor een oordeel"
    )
    args = parser.parse_args(argv)

    init_db()
    taxonomie = load_taxonomie()
    vanaf = date.fromisoformat(args.vanaf) if args.vanaf else None

    with session_scope() as session:
        gegevens = verzamel(session, vanaf=vanaf)

    if not gegevens:
        print("Nog geen dossiers met een vastgelegde afloop.")
        print("Leg die vast via POST /api/bezwaren/{id}/afloop; zonder die gegevens")
        print("blijven de inschattingen een aanname.")
        return 0

    print(f"{'categorie':<34}{'n':>5}{'prior':>8}{'ingeschat':>11}{'werkelijk':>11}  oordeel")
    print("-" * 88)
    for sleutel in sorted(gegevens, key=lambda k: -gegevens[k]["aantal"]):
        regel = gegevens[sleutel]
        aantal = regel["aantal"]
        ingeschat = regel["som_inschatting"] / aantal
        werkelijk = regel["som_afloop"] / aantal
        prior = taxonomie.get(sleutel).prior

        if aantal < args.minimaal:
            oordeel = f"te weinig gegevens (< {args.minimaal})"
        elif werkelijk - ingeschat > 0.2:
            oordeel = "onderschat: bezwaren blijken vaker terecht"
        elif ingeschat - werkelijk > 0.2:
            oordeel = "overschat: bezwaren blijken vaker ongegrond"
        else:
            oordeel = "in lijn"

        print(
            f"{sleutel:<34}{aantal:>5}{prior:>8.2f}{ingeschat:>11.2f}{werkelijk:>11.2f}  {oordeel}"
        )

    print(
        "\n`ingeschat` is het gemiddelde oordeel van de agent, `werkelijk` de afloop "
        "(ingetrokken telt als 1, deels gecorrigeerd en geschil als 0,5, gehandhaafd als 0)."
    )
    print("Wijkt een categorie structureel af, stel dan de prior in taxonomie.yaml bij.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
