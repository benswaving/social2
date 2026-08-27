"""Datamodel: bezwaren, geëxtraheerde argumenten, kennisbronnen, concepten, audit."""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class CaseStatus(str, enum.Enum):
    NIEUW = "nieuw"
    GEANALYSEERD = "geanalyseerd"
    CONCEPT_GEREED = "concept_gereed"
    GOEDGEKEURD = "goedgekeurd"
    VERZONDEN = "verzonden"
    GEESCALEERD = "geescaleerd"
    MISLUKT = "mislukt"


class Merit(str, enum.Enum):
    """Hoeveel kans maakt dit argument volgens wet en jurisprudentie?"""

    KANSRIJK = "kansrijk"            # klant heeft (deels) een punt -> mens beslist
    TWIJFELACHTIG = "twijfelachtig"  # hangt af van feiten die we moeten checken
    KANSARM = "kansarm"              # weerlegbaar met concrete bron
    ONBEPAALD = "onbepaald"


class JobStatus(str, enum.Enum):
    WACHTEND = "wachtend"
    BEZIG = "bezig"
    KLAAR = "klaar"
    MISLUKT = "mislukt"


class Afloop(str, enum.Enum):
    """Hoe een dossier werkelijk is afgelopen - de meetlat voor de inschatting."""

    ONBEKEND = "onbekend"
    VORDERING_GEHANDHAAFD = "vordering_gehandhaafd"
    DEELS_GECORRIGEERD = "deels_gecorrigeerd"
    VORDERING_INGETROKKEN = "vordering_ingetrokken"
    GESCHIL = "geschil"  # doorgezet naar rechter of geschilleninstantie


class SourceKind(str, enum.Enum):
    WET = "wet"                      # wetsartikel (Energiewet, BW, ...)
    JURISPRUDENTIE = "jurisprudentie"
    REGELING = "regeling"            # ACM-codebesluiten, algemene voorwaarden
    EIGEN = "eigen"                  # eigen werkinstructie / standaardparagraaf


class Verification(str, enum.Enum):
    ONGEVERIFIEERD = "ongeverifieerd"  # seed, nog niet tegen de bron gecheckt
    BEVESTIGD = "bevestigd"            # opgehaald bij officiele bron
    NIET_GEVONDEN = "niet_gevonden"    # bestaat niet -> nooit citeren
    HANDMATIG = "handmatig"            # door jurist geaccordeerd


class Objection(Base):
    """Een binnengekomen bezwaarbrief."""

    __tablename__ = "objections"

    id: Mapped[int] = mapped_column(primary_key=True)
    dossier_ref: Mapped[str | None] = mapped_column(String(64), index=True)
    ean: Mapped[str | None] = mapped_column(String(24), index=True)
    afzender_naam: Mapped[str | None] = mapped_column(String(255))
    afzender_email: Mapped[str | None] = mapped_column(String(255))
    adres: Mapped[str | None] = mapped_column(String(255))

    kanaal: Mapped[str] = mapped_column(String(16), default="upload")  # upload | imap | api
    bron_id: Mapped[str | None] = mapped_column(String(255), unique=True)  # message-id / bestandshash
    bestandspad: Mapped[str | None] = mapped_column(String(512))
    ontvangen_op: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ruwe_tekst: Mapped[str] = mapped_column(Text, default="")
    tekst_kwaliteit: Mapped[str] = mapped_column(String(16), default="onbekend")  # goed | ocr | slecht

    status: Mapped[CaseStatus] = mapped_column(Enum(CaseStatus), default=CaseStatus.NIEUW, index=True)
    samenvatting: Mapped[str | None] = mapped_column(Text)
    ai_gegenereerd_signaal: Mapped[float | None] = mapped_column(Float)
    ai_signaal_toelichting: Mapped[str | None] = mapped_column(Text)
    globale_kans: Mapped[Merit] = mapped_column(Enum(Merit), default=Merit.ONBEPAALD)
    escalatie: Mapped[bool] = mapped_column(Boolean, default=False)
    escalatie_reden: Mapped[str | None] = mapped_column(Text)
    analyse_fout: Mapped[str | None] = mapped_column(Text)

    # Termijnbewaking: wanneer moet hier uiterlijk een antwoord uit?
    reactie_uiterlijk: Mapped[date | None] = mapped_column(Date, index=True)
    termijn_grond: Mapped[str | None] = mapped_column(String(64))

    # Werkelijke afloop, om de inschattingen aan te kunnen toetsen.
    afloop: Mapped[Afloop] = mapped_column(Enum(Afloop), default=Afloop.ONBEKEND, index=True)
    afloop_notitie: Mapped[str | None] = mapped_column(Text)
    afloop_vastgelegd_op: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def te_laat(self) -> bool:
        if self.reactie_uiterlijk is None or self.status in (
            CaseStatus.GOEDGEKEURD,
            CaseStatus.VERZONDEN,
        ):
            return False
        return self.reactie_uiterlijk < date.today()

    @property
    def dagen_resterend(self) -> int | None:
        if self.reactie_uiterlijk is None:
            return None
        return (self.reactie_uiterlijk - date.today()).days

    argumenten: Mapped[list["Argument"]] = relationship(
        back_populates="objection", cascade="all, delete-orphan", order_by="Argument.volgnummer"
    )
    aangehaalde_bronnen: Mapped[list["ClaimedCitation"]] = relationship(
        back_populates="objection", cascade="all, delete-orphan"
    )
    concepten: Mapped[list["Draft"]] = relationship(
        back_populates="objection", cascade="all, delete-orphan", order_by="Draft.versie"
    )
    events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="objection", cascade="all, delete-orphan", order_by="AuditEvent.id"
    )


class Argument(Base):
    """Een los argument uit de brief, met beoordeling."""

    __tablename__ = "arguments"

    id: Mapped[int] = mapped_column(primary_key=True)
    objection_id: Mapped[int] = mapped_column(ForeignKey("objections.id", ondelete="CASCADE"), index=True)
    volgnummer: Mapped[int] = mapped_column(Integer, default=0)

    categorie: Mapped[str] = mapped_column(String(64), index=True)  # sleutel uit taxonomie.yaml
    stelling: Mapped[str] = mapped_column(Text)                     # wat beweert de klant
    citaat: Mapped[str | None] = mapped_column(Text)                # letterlijk uit de brief

    merit: Mapped[Merit] = mapped_column(Enum(Merit), default=Merit.ONBEPAALD)
    merit_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0 = kansloos, 1 = zeer kansrijk
    onderbouwing: Mapped[str | None] = mapped_column(Text)          # waarom deze beoordeling
    weerlegging: Mapped[str | None] = mapped_column(Text)           # kernzin voor de brief
    benodigde_feitencheck: Mapped[list | None] = mapped_column(JSON)  # wat moet een mens opzoeken
    bron_keys: Mapped[list | None] = mapped_column(JSON)            # Source.key's die dit dragen

    objection: Mapped["Objection"] = relationship(back_populates="argumenten")


class ClaimedCitation(Base):
    """Bron die de klant zelf aanhaalt - inclusief verzonnen artikelen en ECLI's."""

    __tablename__ = "claimed_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    objection_id: Mapped[int] = mapped_column(ForeignKey("objections.id", ondelete="CASCADE"), index=True)

    ruwe_verwijzing: Mapped[str] = mapped_column(String(512))
    soort: Mapped[str] = mapped_column(String(32), default="overig")  # wetsartikel | ecli | regeling | overig
    genormaliseerd: Mapped[str | None] = mapped_column(String(255), index=True)
    context: Mapped[str | None] = mapped_column(Text)

    uitkomst: Mapped[str] = mapped_column(String(32), default="onbekend")
    # bestaat_en_relevant | niet_van_toepassing | bestaat_niet | ingetrokken | onbekend
    toelichting: Mapped[str | None] = mapped_column(Text)
    gecontroleerd_op: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    objection: Mapped["Objection"] = relationship(back_populates="aangehaalde_bronnen")


class Source(Base):
    """Kennisbankitem: wetsartikel, uitspraak, regeling of eigen standaardtekst."""

    __tablename__ = "sources"
    __table_args__ = (UniqueConstraint("key", name="uq_source_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), index=True)  # bv. "ew-3.10" of "ecli-nl-hr-2019-1234"
    soort: Mapped[SourceKind] = mapped_column(Enum(SourceKind), index=True)

    titel: Mapped[str] = mapped_column(String(512))
    vindplaats: Mapped[str] = mapped_column(String(255))  # "art. 6:217 BW" / "ECLI:NL:HR:2019:1234"
    tekst: Mapped[str] = mapped_column(Text, default="")
    samenvatting: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(512))

    # Temporele geldigheid: sinds 1-1-2026 vervangt de Energiewet de E-wet 1998 en de Gaswet.
    # Een vordering uit 2023 moet nog onder het oude recht worden beantwoord.
    geldig_vanaf: Mapped[date | None] = mapped_column(Date)
    geldig_tot: Mapped[date | None] = mapped_column(Date)
    vervangen_door: Mapped[str | None] = mapped_column(String(128))

    verificatie: Mapped[Verification] = mapped_column(
        Enum(Verification), default=Verification.ONGEVERIFIEERD, index=True
    )
    verificatie_toelichting: Mapped[str | None] = mapped_column(Text)
    laatst_gecontroleerd: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tags: Mapped[list | None] = mapped_column(JSON)
    categorieen: Mapped[list | None] = mapped_column(JSON)  # taxonomie-sleutels waar dit bij hoort
    toegevoegd_door: Mapped[str] = mapped_column(String(64), default="seed")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    @property
    def citeerbaar(self) -> bool:
        """Mag de agent hier in een uitgaande brief naar verwijzen?

        Een geverifieerde tekst is niet hetzelfde als een juiste onderbouwing. Een
        artikel dat de zoekopdracht automatisch bij een bezwaarcategorie heeft gezet
        (`auto-gemapt`) heeft een echte, opgehaalde tekst, maar of het artikel dit
        standpunt draagt is een juridisch oordeel. Dat blijft mensenwerk: pas na
        accorderen (`handmatig`) mag de agent het aanhalen.
        """
        if self.verificatie == Verification.HANDMATIG:
            return True
        if self.verificatie != Verification.BEVESTIGD:
            return False
        return "auto-gemapt" not in (self.tags or [])


class Draft(Base):
    """Conceptantwoord. Gaat nooit buiten de deur zonder menselijke goedkeuring."""

    __tablename__ = "drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    objection_id: Mapped[int] = mapped_column(ForeignKey("objections.id", ondelete="CASCADE"), index=True)
    versie: Mapped[int] = mapped_column(Integer, default=1)

    onderwerp: Mapped[str] = mapped_column(String(255), default="")
    tekst: Mapped[str] = mapped_column(Text)
    gebruikte_bron_keys: Mapped[list | None] = mapped_column(JSON)
    guardrail_rapport: Mapped[dict | None] = mapped_column(JSON)
    geblokkeerd: Mapped[bool] = mapped_column(Boolean, default=False)

    model: Mapped[str | None] = mapped_column(String(64))
    prompt_versie: Mapped[str | None] = mapped_column(String(32))

    beoordelaar: Mapped[str | None] = mapped_column(String(128))
    beoordeling_notitie: Mapped[str | None] = mapped_column(Text)
    goedgekeurd_op: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    objection: Mapped["Objection"] = relationship(back_populates="concepten")


class AuditEvent(Base):
    """Wie deed wat, wanneer - verplicht spoor bij aansprakelijkstelling."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    objection_id: Mapped[int | None] = mapped_column(
        ForeignKey("objections.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(String(128), default="systeem")
    actie: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict | None] = mapped_column(JSON)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    objection: Mapped["Objection"] = relationship(back_populates="events")


class Job(Base):
    """Werk dat buiten het verzoek om wordt gedaan.

    Bewust een tabel en geen Redis-wachtrij: dit draait op dezelfde database die er
    toch al is, werkt met SQLite zowel als Postgres, en overleeft een herstart. Het
    volume van een bezwarenafdeling rechtvaardigt geen extra dienst om te beheren.
    """

    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    soort: Mapped[str] = mapped_column(String(48), index=True)
    objection_id: Mapped[int | None] = mapped_column(
        ForeignKey("objections.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.WACHTEND, index=True)

    pogingen: Mapped[int] = mapped_column(Integer, default=0)
    max_pogingen: Mapped[int] = mapped_column(Integer, default=3)
    fout: Mapped[str | None] = mapped_column(Text)

    aangemaakt_op: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    gestart_op: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geeindigd_op: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def opnieuw_proberen(self) -> bool:
        return self.pogingen < self.max_pogingen
