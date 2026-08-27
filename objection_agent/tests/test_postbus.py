"""Ontleden van binnengekomen e-mail, zonder postbus.

De IMAP-koppeling zelf is niet te testen zonder mailserver; het ontleden wel, en
daar zit het meeste dat stuk kan gaan: codering van koppen, HTML-only berichten,
bijlagen met rare namen.
"""

from __future__ import annotations

import email

from app.ingest.imap_client import bericht_uit_email

BASIS = """From: "Jansen, P." <p.jansen@example.nl>
To: asc@netbeheerder.nl
Subject: Bezwaar tegen uw factuur
Message-ID: <abc123@example.nl>
Content-Type: text/plain; charset="utf-8"

Geachte heer, mevrouw,

Ik maak bezwaar tegen uw factuur. Ik heb nooit een contract getekend.

Met vriendelijke groet,
P. Jansen
"""


def _ontleed(ruwe_tekst: str, tmp_path):
    ruw = ruwe_tekst.encode("utf-8")
    return bericht_uit_email(email.message_from_bytes(ruw), ruw, tmp_path)


def test_leest_afzender_onderwerp_en_tekst(tmp_path):
    bericht = _ontleed(BASIS, tmp_path)
    assert bericht.afzender_email == "p.jansen@example.nl"
    assert bericht.afzender_naam == "Jansen, P."
    assert bericht.onderwerp == "Bezwaar tegen uw factuur"
    assert "nooit een contract getekend" in bericht.tekst
    assert bericht.message_id == "<abc123@example.nl>"


def test_gecodeerde_koppen_worden_leesbaar(tmp_path):
    ruw = BASIS.replace(
        "Subject: Bezwaar tegen uw factuur",
        "Subject: =?utf-8?q?Bezwaar_tegen_uw_factuur_=28co=CC=88rdinatie=29?=",
    )
    assert "Bezwaar tegen uw factuur" in _ontleed(ruw, tmp_path).onderwerp


def test_bericht_zonder_message_id_krijgt_een_eigen_sleutel(tmp_path):
    ruw = "\n".join(r for r in BASIS.splitlines() if not r.startswith("Message-ID"))
    bericht = _ontleed(ruw, tmp_path)
    assert len(bericht.message_id) == 64  # sha256 van de ruwe inhoud


def test_html_bericht_wordt_leesbare_tekst(tmp_path):
    ruw = """From: klant@example.nl
Subject: Bezwaar
Message-ID: <html1@example.nl>
Content-Type: text/html; charset="utf-8"

<html><body><p>Ik maak <b>bezwaar</b> tegen de factuur.</p></body></html>
"""
    tekst = _ontleed(ruw, tmp_path).tekst
    assert "bezwaar" in tekst
    assert "<b>" not in tekst


def test_pdf_bijlage_wordt_opgeslagen(tmp_path):
    ruw = """From: klant@example.nl
Subject: Bezwaar met bijlage
Message-ID: <bijlage1@example.nl>
Content-Type: multipart/mixed; boundary="grens"

--grens
Content-Type: text/plain; charset="utf-8"

Zie bijlage.
--grens
Content-Type: application/pdf
Content-Disposition: attachment; filename="mijn bezwaar (1).pdf"
Content-Transfer-Encoding: base64

JVBERi0xLjQK
--grens--
"""
    bericht = _ontleed(ruw, tmp_path)
    assert len(bericht.bijlagen) == 1
    opgeslagen = bericht.bijlagen[0]
    assert opgeslagen.exists()
    # Spaties en haakjes uit de bestandsnaam mogen niet in het pad terechtkomen.
    assert " " not in opgeslagen.name and "(" not in opgeslagen.name
    assert opgeslagen.read_bytes().startswith(b"%PDF")


def test_bijlage_met_ander_type_wordt_genegeerd(tmp_path):
    ruw = """From: klant@example.nl
Subject: Bezwaar
Message-ID: <exe1@example.nl>
Content-Type: multipart/mixed; boundary="grens"

--grens
Content-Type: text/plain

Zie bijlage.
--grens
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="virus.exe"
Content-Transfer-Encoding: base64

TVo=
--grens--
"""
    assert _ontleed(ruw, tmp_path).bijlagen == []
