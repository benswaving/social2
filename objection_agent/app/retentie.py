"""Opruimen van afgehandelde dossiers na de bewaartermijn.

Bezwaarbrieven bevatten persoonsgegevens en soms een financiele of medische
situatie. Ze mogen niet langer bewaard blijven dan nodig. Dit commando ruimt op
en laat een spoor achter dat er is opgeruimd, zonder de inhoud te bewaren.

    python -m app.retentie                 # toont wat er zou verdwijnen
    python -m app.retentie --uitvoeren     # ruimt daadwerkelijk op
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from .config import get_settings
from .db import init_db, session_scope
from .models import AuditEvent, CaseStatus, Objection

# Alleen wat is afgehandeld komt in aanmerking. Een lopend of geescaleerd dossier
# wordt nooit automatisch opgeruimd, hoe oud het ook is.
AFGEHANDELD = (CaseStatus.GOEDGEKEURD, CaseStatus.VERZONDEN, CaseStatus.MISLUKT)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="app.retentie", description=__doc__)
    parser.add_argument(
        "--dagen",
        type=int,
        default=settings.bewaartermijn_dagen,
        help=f"bewaartermijn in dagen (nu: {settings.bewaartermijn_dagen})",
    )
    parser.add_argument("--uitvoeren", action="store_true", help="daadwerkelijk verwijderen")
    parser.add_argument("--actor", default="retentie", help="wie deze opruiming uitvoert")
    args = parser.parse_args(argv)

    if args.dagen <= 0:
        print("Bewaartermijn staat op 0: automatisch opruimen is uitgeschakeld.")
        return 0

    init_db()
    grens = datetime.now(timezone.utc) - timedelta(days=args.dagen)

    with session_scope() as session:
        kandidaten = list(
            session.scalars(
                select(Objection)
                .where(Objection.status.in_(AFGEHANDELD))
                .where(Objection.ontvangen_op < grens)
                .order_by(Objection.ontvangen_op)
            )
        )

        if not kandidaten:
            print(f"Niets ouder dan {args.dagen} dagen en afgehandeld.")
            return 0

        print(f"{len(kandidaten)} dossier(s) ouder dan {args.dagen} dagen en afgehandeld:")
        for objection in kandidaten:
            print(
                f"  {objection.id:>5}  {objection.ontvangen_op:%d-%m-%Y}  "
                f"{objection.status.value:<14} {objection.dossier_ref or objection.ean or '-'}"
            )

        if not args.uitvoeren:
            print("\nProefdraai. Gebruik --uitvoeren om daadwerkelijk te verwijderen.")
            return 0

        for objection in kandidaten:
            # Spoor bewaren dat er is opgeruimd, zonder de inhoud te bewaren:
            # geen naam, geen adres, geen brieftekst.
            session.add(
                AuditEvent(
                    objection_id=None,
                    actor=args.actor,
                    actie="retentie_verwijderd",
                    detail={
                        "dossier_ref": objection.dossier_ref,
                        "ontvangen_op": objection.ontvangen_op.isoformat(),
                        "status": objection.status.value,
                        "bewaartermijn_dagen": args.dagen,
                    },
                )
            )
            session.delete(objection)

        print(f"\n{len(kandidaten)} dossier(s) verwijderd.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
