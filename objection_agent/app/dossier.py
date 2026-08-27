"""Samenhang tussen dossiers.

Een tweede brief van dezelfde klant, of een reactie op ons antwoord, kwam als
los dossier binnen zonder verband met het vorige. Bij een lopende discussie is
dat lastig werken: de medewerker mist wat er eerder is toegezegd.

Er wordt bewust niets automatisch samengevoegd. Dossiers samenvoegen is een
inhoudelijk oordeel - twee bewoners op hetzelfde adres zijn niet dezelfde
partij. Dit legt alleen het verband en laat de medewerker kijken.
"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .models import Objection


def zoek_gerelateerd(session: Session, objection: Objection, *, limiet: int = 10) -> list[Objection]:
    voorwaarden = []
    if objection.ean:
        voorwaarden.append(Objection.ean == objection.ean)
    if objection.dossier_ref:
        voorwaarden.append(Objection.dossier_ref == objection.dossier_ref)
    if objection.afzender_email:
        voorwaarden.append(Objection.afzender_email == objection.afzender_email)
    if not voorwaarden:
        return []

    return list(
        session.scalars(
            select(Objection)
            .where(or_(*voorwaarden))
            .where(Objection.id != objection.id)
            .order_by(Objection.ontvangen_op.desc())
            .limit(limiet)
        )
    )
