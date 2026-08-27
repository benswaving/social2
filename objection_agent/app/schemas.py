"""Pydantic-schema's voor de API."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ArgumentUit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    volgnummer: int
    categorie: str
    stelling: str
    citaat: str | None = None
    merit: str
    merit_score: float
    onderbouwing: str | None = None
    benodigde_feitencheck: list[str] | None = None
    bron_keys: list[str] | None = None


class BronoordeelUit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ruwe_verwijzing: str
    soort: str
    genormaliseerd: str | None = None
    uitkomst: str
    toelichting: str | None = None


class ConceptUit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    versie: int
    onderwerp: str
    tekst: str
    gebruikte_bron_keys: list[str] | None = None
    guardrail_rapport: dict | None = None
    geblokkeerd: bool
    model: str | None = None
    beoordelaar: str | None = None
    goedgekeurd_op: datetime | None = None
    created_at: datetime


class BezwaarKort(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dossier_ref: str | None = None
    ean: str | None = None
    afzender_naam: str | None = None
    kanaal: str
    status: str
    globale_kans: str
    escalatie: bool
    ai_gegenereerd_signaal: float | None = None
    ontvangen_op: datetime
    reactie_uiterlijk: date | None = None
    te_laat: bool = False
    afloop: str = "onbekend"


class BezwaarDetail(BezwaarKort):
    ruwe_tekst: str
    tekst_kwaliteit: str
    samenvatting: str | None = None
    escalatie_reden: str | None = None
    ai_signaal_toelichting: str | None = None
    analyse_fout: str | None = None
    termijn_grond: str | None = None
    afloop_notitie: str | None = None
    argumenten: list[ArgumentUit] = Field(default_factory=list)
    aangehaalde_bronnen: list[BronoordeelUit] = Field(default_factory=list)
    concepten: list[ConceptUit] = Field(default_factory=list)


class TekstIn(BaseModel):
    tekst: str = Field(min_length=20, description="De volledige brieftekst")
    afzender_naam: str | None = None
    direct_verwerken: bool = True


class GoedkeuringIn(BaseModel):
    beoordelaar: str = Field(min_length=2, description="Naam of personeelsnummer van de medewerker")
    notitie: str | None = None
    aangepaste_tekst: str | None = Field(
        default=None, description="Definitieve tekst als de medewerker het concept heeft bijgewerkt"
    )


class AfloopIn(BaseModel):
    afloop: str = Field(
        description=(
            "onbekend | vordering_gehandhaafd | deels_gecorrigeerd | "
            "vordering_ingetrokken | geschil"
        )
    )
    vastgelegd_door: str = Field(min_length=2)
    notitie: str | None = None


class BronIn(BaseModel):
    key: str
    soort: str = "eigen"
    titel: str
    vindplaats: str
    tekst: str = ""
    samenvatting: str | None = None
    url: str | None = None
    categorieen: list[str] = Field(default_factory=list)
    geaccordeerd: bool = Field(
        default=False,
        description="Alleen geaccordeerde bronnen mogen in een uitgaande brief geciteerd worden",
    )


class BronUit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    soort: str
    titel: str
    vindplaats: str
    samenvatting: str | None = None
    url: str | None = None
    verificatie: str
    verificatie_toelichting: str | None = None
    categorieen: list[str] | None = None
    citeerbaar: bool
