"""Bezwaren ophalen uit een gedeelde postbus.

Ophalen gebeurt niet-destructief: berichten worden gelezen, gemarkeerd en
desgewenst verplaatst naar een verwerkt-map. Er wordt nooit iets verwijderd, en
er wordt vanuit deze module nooit iets verzonden.
"""

from __future__ import annotations

import email
import hashlib
import imaplib
import logging
import re
from dataclasses import dataclass, field
from email.header import decode_header, make_header
from email.message import Message
from pathlib import Path

from ..config import get_settings

logger = logging.getLogger(__name__)

BIJLAGE_TYPES = {".pdf", ".txt", ".eml"}


@dataclass
class Bericht:
    message_id: str
    afzender_naam: str | None
    afzender_email: str | None
    onderwerp: str
    tekst: str
    bijlagen: list[Path] = field(default_factory=list)


def _decodeer(waarde: str | None) -> str:
    if not waarde:
        return ""
    try:
        return str(make_header(decode_header(waarde)))
    except Exception:
        return waarde


def _platte_tekst(bericht: Message) -> str:
    delen: list[str] = []
    for onderdeel in bericht.walk():
        if onderdeel.get_content_maintype() == "multipart":
            continue
        if onderdeel.get_filename():
            continue
        if onderdeel.get_content_type() == "text/plain":
            lading = onderdeel.get_payload(decode=True) or b""
            delen.append(lading.decode(onderdeel.get_content_charset() or "utf-8", errors="replace"))
        elif onderdeel.get_content_type() == "text/html" and not delen:
            lading = onderdeel.get_payload(decode=True) or b""
            html = lading.decode(onderdeel.get_content_charset() or "utf-8", errors="replace")
            delen.append(re.sub(r"<[^>]+>", " ", html))
    return "\n".join(delen).strip()


def _bijlagen(bericht: Message, doelmap: Path, sleutel: str) -> list[Path]:
    opgeslagen: list[Path] = []
    for index, onderdeel in enumerate(bericht.walk()):
        naam = onderdeel.get_filename()
        if not naam:
            continue
        naam = _decodeer(naam)
        suffix = Path(naam).suffix.lower()
        if suffix not in BIJLAGE_TYPES:
            continue
        lading = onderdeel.get_payload(decode=True)
        if not lading:
            continue
        veilig = re.sub(r"[^A-Za-z0-9._-]", "_", naam)[:80]
        pad = doelmap / f"{sleutel}_{index}_{veilig}"
        pad.write_bytes(lading)
        opgeslagen.append(pad)
    return opgeslagen


def haal_berichten(maximum: int | None = None) -> list[Bericht]:
    settings = get_settings()
    if not (settings.imap_host and settings.imap_user and settings.imap_password):
        raise RuntimeError(
            "IMAP is niet geconfigureerd. Zet OA_IMAP_HOST, OA_IMAP_USER en OA_IMAP_PASSWORD."
        )

    maximum = maximum or settings.imap_max_per_run
    doelmap = settings.upload_dir
    doelmap.mkdir(parents=True, exist_ok=True)

    verbinding = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
    berichten: list[Bericht] = []
    try:
        verbinding.login(settings.imap_user, settings.imap_password)
        verbinding.select(settings.imap_folder)
        status, data = verbinding.search(None, "UNSEEN")
        if status != "OK":
            return []

        ids = data[0].split()[:maximum]
        for bericht_id in ids:
            status, ruw = verbinding.fetch(bericht_id, "(RFC822)")
            if status != "OK" or not ruw or not isinstance(ruw[0], tuple):
                continue
            bericht = email.message_from_bytes(ruw[0][1])

            message_id = _decodeer(bericht.get("Message-ID")) or hashlib.sha256(
                ruw[0][1]
            ).hexdigest()
            sleutel = hashlib.sha256(message_id.encode()).hexdigest()[:16]
            afzender = _decodeer(bericht.get("From"))
            adres = re.search(r"<([^>]+)>", afzender)

            berichten.append(
                Bericht(
                    message_id=message_id,
                    afzender_naam=afzender.split("<")[0].strip().strip('"') or None,
                    afzender_email=adres.group(1) if adres else (afzender or None),
                    onderwerp=_decodeer(bericht.get("Subject")),
                    tekst=_platte_tekst(bericht),
                    bijlagen=_bijlagen(bericht, doelmap, sleutel),
                )
            )

            if settings.imap_processed_folder:
                try:
                    verbinding.copy(bericht_id, settings.imap_processed_folder)
                except imaplib.IMAP4.error as exc:
                    logger.warning("Kon bericht niet kopieren naar verwerkt-map: %s", exc)
            verbinding.store(bericht_id, "+FLAGS", "\\Seen")
    finally:
        try:
            verbinding.close()
        except imaplib.IMAP4.error:
            pass
        verbinding.logout()

    return berichten
