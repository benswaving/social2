"""Tekst uit een aangeleverd bestand halen (PDF, gescande PDF of platte tekst)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Onder dit aantal tekens per pagina gaan we ervan uit dat het een scan is.
MIN_TEKENS_PER_PAGINA = 120


@dataclass
class Extractie:
    tekst: str
    kwaliteit: str  # goed | ocr | slecht
    toelichting: str = ""

    @property
    def bruikbaar(self) -> bool:
        return bool(self.tekst.strip()) and self.kwaliteit != "slecht"


def _uit_pdf(pad: Path) -> tuple[str, int]:
    import pdfplumber

    delen: list[str] = []
    with pdfplumber.open(pad) as pdf:
        for pagina in pdf.pages:
            delen.append(pagina.extract_text() or "")
        aantal = len(pdf.pages)
    return "\n\n".join(delen).strip(), aantal


def _ocr(pad: Path) -> str:
    """OCR-terugval. Vereist pytesseract, pdf2image, tesseract-ocr en poppler-utils."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise RuntimeError(
            "OCR niet beschikbaar: installeer pytesseract en pdf2image, plus de "
            "systeempakketten tesseract-ocr, tesseract-ocr-nld en poppler-utils."
        ) from exc

    delen = [
        pytesseract.image_to_string(afbeelding, lang="nld")
        for afbeelding in convert_from_path(str(pad), dpi=300)
    ]
    return "\n\n".join(delen).strip()


def extraheer(pad: str | Path) -> Extractie:
    pad = Path(pad)
    suffix = pad.suffix.lower()

    if suffix in (".txt", ".md", ".eml"):
        return Extractie(pad.read_text(encoding="utf-8", errors="replace"), "goed")

    if suffix != ".pdf":
        return Extractie("", "slecht", f"Bestandstype {suffix} wordt niet ondersteund.")

    try:
        tekst, paginas = _uit_pdf(pad)
    except Exception as exc:  # pdfplumber werpt uiteenlopende fouten
        logger.warning("PDF-extractie mislukt voor %s: %s", pad, exc)
        tekst, paginas = "", 1

    if tekst and len(tekst) >= MIN_TEKENS_PER_PAGINA * max(paginas, 1):
        return Extractie(tekst, "goed")

    # Weinig of geen tekstlaag: waarschijnlijk een scan.
    try:
        ocr_tekst = _ocr(pad)
    except RuntimeError as exc:
        return Extractie(
            tekst,
            "slecht" if not tekst.strip() else "goed",
            f"Weinig tekstlaag gevonden en OCR is niet beschikbaar: {exc}",
        )

    if len(ocr_tekst) > len(tekst):
        return Extractie(
            ocr_tekst,
            "ocr",
            "Via OCR gelezen; controleer bedragen, data en namen extra zorgvuldig.",
        )
    return Extractie(tekst, "goed" if tekst.strip() else "slecht")
