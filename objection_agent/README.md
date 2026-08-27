# Bezwaren-agent — Aansluiting Zonder Contract

Leest binnengekomen bezwaarbrieven, splitst ze in losse argumenten, beoordeelt die
tegen **geverifieerde** bronnen en schrijft een conceptantwoord. Een medewerker
keurt elk concept goed voordat het de deur uitgaat; **deze applicatie verstuurt
zelf niets.**

Gebouwd voor het probleem dat de aanleiding was: een groeiende stroom brieven die
met een taalmodel is opgesteld, met argumenten die overtuigend klinken en
vindplaatsen die niet bestaan.

## Wat de agent doet

1. **Intake** — PDF of scan uploaden, of ongelezen berichten uit een gedeelde
   postbus (IMAP) ophalen. Gescande brieven gaan door OCR.
2. **Ontleden** — de brief wordt gesplitst in losse argumenten, elk met een
   letterlijk citaat, ingedeeld in een van de 16 categorieën uit
   `app/knowledge/seed/taxonomie.yaml`.
3. **Bronnencontrole** — elke wetsbepaling en ECLI waar de klant zich op beroept
   wordt opgezocht. Uitkomst per verwijzing: *bestaat en is relevant*, *niet van
   toepassing*, *ingetrokken*, *bestaat niet*, of *onbekend*.
4. **Beoordelen** — per argument een kansinschatting, plus de feiten die een
   medewerker nog moet opzoeken. Escalatieregels bepalen wat altijd naar een mens gaat.
5. **Concept schrijven** — een brief die op elk argument ingaat, met vindplaatsen
   die uitsluitend uit de geverifieerde kennisbank komen.
6. **Controleren** — guardrails houden een concept tegen dat een vindplaats,
   bedrag of interne werkinstructie bevat die er niet in hoort.
7. **Goedkeuren** — de medewerker past aan en tekent af. Dat wordt vastgelegd.

## Drie ontwerpkeuzes die het uitleggen waard zijn

**Een bron is niet citeerbaar tot hij is opgehaald bij de officiële bron.**
De seed in `app/knowledge/seed/` bevat vindplaatsen, geen wetteksten. Pas als
`sync wetten` het artikel echt heeft opgehaald bij het KOOP-repository gaat de
status naar `bevestigd`, en pas dan mag de agent ernaar verwijzen. Een artikel dat
daar niet blijkt te bestaan komt op `niet_gevonden` en wordt nooit meer geciteerd —
ook niet als het model erop staat. Zo kan de agent niet hetzelfde doen als de
brieven die hij beoordeelt.

**Er staat geen enkel ECLI-nummer én geen enkel Energiewet-artikelnummer in de seed.** Uit het hoofd opgeschreven
jurisprudentie is precies de fout die we bestrijden. In plaats daarvan staan er
zoekprofielen in `jurisprudentie.yaml`; `sync jurisprudentie` haalt daarmee echte
uitspraken op met hun echte tekst.

Voor de wet werkt het net zo. `wetsartikelen.yaml` bevat geen artikelnummers voor
de Energiewet maar *artikelzoekers*: "zoek in BWBR0050714 de artikelen waarin zowel
`netbeheerder` als `aansluiting` voorkomt, en rangschik op `taak`, `verzoek`,
`realiseren`". `sync artikelen` haalt de wet op, doorzoekt de artikelen en slaat op
wat er echt in staat — met het echte nummer, de echte tekst en de versiedatum. Het
artikelnummer komt dus uit de wet, niet uit een geheugen.

Wat zo binnenkomt is *geverifieerd van tekst* maar *niet geaccordeerd van
toepassing*: de zoekopdracht koppelt het artikel aan een bezwaarcategorie, en dat
is een juridisch oordeel. Zulke bronnen krijgen de tag `auto-gemapt` en zijn niet
citeerbaar tot een jurist ze op `/kennisbank` heeft vrijgegeven. Hetzelfde geldt
voor de kandidaat-uitspraken.

**"Bestaat niet" zeggen we alleen als we het echt hebben opgezocht.** Kon een
verwijzing niet gecontroleerd worden, dan blijft de uitkomst `onbekend` en zwijgt
de brief erover. Een onterecht "deze uitspraak bestaat niet" in een uitgaande
brief is erger dan geen opmerking.

## De agent is geen afwijsmachine

De vraag was om kansarme bezwaren te weerleggen. Het systeem doet dat, maar
beoordeelt eerst of een bezwaar kansarm ís:

- Categorieën als verjaring, algemene voorwaarden, AVG en schrijnende
  omstandigheden gaan **altijd** naar een mens, ongeacht de score.
- Eén kansrijk argument tussen negen kansloze escaleert het hele dossier.
- Voor een kansrijk of twijfelachtig argument schrijft de agent geen weerlegging
  maar een toezegging ("dit onderzoeken wij").
- Het signaal dat een brief met AI is opgesteld is triage-informatie en staat
  expliciet los van de inhoudelijke beoordeling. Een gegenereerde brief kan
  gewoon gelijk hebben.

De reden is niet alleen netheid: een onterechte afwijzing leidt tot een
aansprakelijkstelling van iemand die niets fout deed, en dat is de duurste fout
die deze afdeling kan maken.

## Installatie

```bash
cd objection_agent
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # vul OA_OPENAI_API_KEY en de IMAP-gegevens in
```

Voor OCR van gescande brieven ook op systeemniveau:

```bash
sudo apt install tesseract-ocr tesseract-ocr-nld poppler-utils
.venv/bin/pip install pytesseract pdf2image
```

## Kennisbank vullen

```bash
.venv/bin/python -m app.knowledge.sync seed             # vindplaatsen inladen (offline)
.venv/bin/python -m app.knowledge.sync wetten           # BW- en Awb-artikelen ophalen
.venv/bin/python -m app.knowledge.sync artikelen        # Energiewet en ACM-codes: nummers laten opzoeken
.venv/bin/python -m app.knowledge.sync artikelen --droogloop   # alleen het zoekplan tonen, zonder netwerk
.venv/bin/python -m app.knowledge.sync jurisprudentie   # kandidaat-uitspraken oogsten
.venv/bin/python -m app.knowledge.sync ecli ECLI:NL:HR:2024:123 --categorie verjaring --accorderen
.venv/bin/python -m app.knowledge.sync status           # wat is citeerbaar
```

Losse hulpmiddelen:

```bash
# Hele wet doorzoekbaar inladen (zonder categorieën, dus alleen om op te zoeken)
.venv/bin/python -m app.knowledge.sync wet-volledig BWBR0050714 --naam Energiewet

# BWB-id van een regeling opzoeken waarvan het nummer nog niet in de seed staat
.venv/bin/python -m app.knowledge.sync resolve-bwb "Aansluit- en transportcode elektriciteit"

# Zoeken in een handmatig gedownload BWB-XML, voor omgevingen zonder uitgaand netwerk
.venv/bin/python -m app.knowledge.sync artikelen --bestand energiewet.xml            # tonen
.venv/bin/python -m app.knowledge.sync artikelen --bestand energiewet.xml --opslaan  # opnemen
```

Een zoekopdracht kent drie soorten woorden: `verplicht` (moeten allemaal voorkomen),
`uitsluiten` (mogen niet voorkomen) en `trefwoorden` (bepalen de rangschikking). Een
artikel dat geen enkel trefwoord raakt valt af — anders komt bijvoorbeeld een
tariefbepaling mee bij de aansluittaak, alleen omdat daar ook "netbeheerder" en
"aansluiting" in staan. Zien de treffers er niet uit, stel dan de woorden bij en
draai opnieuw; de zoekopdrachten staan in `wetsartikelen.yaml`.

Deze wetten en regelingen staan met hun BWB-id in de seed en worden dus automatisch
opgehaald:

| Regeling | BWB-id | Geldig |
|---|---|---|
| Energiewet | BWBR0050714 | vanaf 01-01-2026 |
| Elektriciteitswet 1998 | BWBR0009755 | t/m 31-12-2025 |
| Gaswet | BWBR0011440 | t/m 31-12-2025 |
| Tarievencode elektriciteit 2026 | BWBR0052321 | vanaf 01-01-2026 |
| Begrippencode elektriciteit 2026 | BWBR0052320 | vanaf 01-01-2026 |
| Systeemcode elektriciteit 2026 | BWBR0052336 | vanaf 01-01-2026 |
| Aansluit- en transportcode gas DSB | BWBR0052332 | vanaf 01-01-2026 |
| Energieregeling | BWBR0051774 | vanaf 01-01-2026 |
| BW Boeken 3, 5 en 6 | BWBR0005291 / 0005288 / 0005289 | — |
| Algemene wet bestuursrecht | BWBR0005537 | — |

Sinds de Energiewet staan de ACM-codebesluiten in het BWB, en zijn ze dus langs
dezelfde weg op te halen en te verifiëren als de wet zelf. Dat scheelt jullie het
handmatig aanleveren ervan. Het BWB-id van de Aansluit- en transportcode
*elektriciteit* heb ik niet kunnen vaststellen; `resolve-bwb` zoekt dat op.

Wat overblijft om zelf aan te leveren via `POST /api/kennisbank/bronnen`: de interne
werkinstructie, de vastgestelde standaardparagrafen, en verder materiaal dat niet
openbaar gepubliceerd is. Zolang `geaccordeerd` niet is gezet, is het zichtbaar voor
de medewerker maar niet citeerbaar.

## Draaien

```bash
# Optioneel: demo-dossiers inladen zodat de werkvoorraad iets te tonen heeft
.venv/bin/python -m app.demo

.venv/bin/uvicorn app.main:app --reload --port 8100
```

Analyseren duurt met een taalmodel al gauw een halve minuut. Dat gebeurt daarom
niet in het HTTP-verzoek: de intake-routes antwoorden met **202** en zetten het
dossier in een wachtrij. Standaard loopt er een werker mee in het webproces; in
productie is een los proces beter:

```bash
OA_WERKER_IN_PROCES=false .venv/bin/uvicorn app.main:app --port 8100   # webproces
.venv/bin/python -m app.worker                                        # werker
.venv/bin/python -m app.worker --eenmalig                              # rij leegwerken
```

De wachtrij is een tabel in dezelfde database — geen Redis of Celery om te
beheren. Een taak die tijdens de verwerking afbreekt blijft op `bezig` staan en
wordt na `OA_WERKER_VASTLOPER_MINUTEN` opnieuw opgepakt; na drie mislukte
pogingen gaat het dossier op `mislukt` met de foutmelding erbij. Zet
`OA_WACHTRIJ_ACTIEF=false` om alles binnen het verzoek te doen (handig bij lage
volumes en in tests).

## Postbus

```bash
.venv/bin/python -m app.postbus test       # verbinding en mappen controleren
.venv/bin/python -m app.postbus ophalen    # ongelezen berichten binnenhalen
```

`test` opent de map alleen-lezen en telt; er wordt niets gelezen, gemarkeerd of
verplaatst. Begin daarmee, en zet `OA_IMAP_MAX_PER_RUN` de eerste keren laag.

## Termijnen

Elk dossier krijgt bij binnenkomst een uiterste reactiedatum, die na de analyse
korter kan worden. Er gelden drie termijnen en de **kortste** wint — de
AVG-termijn is een wettelijk maximum, geen streefdatum, dus een AVG-verzoek dat
ook geëscaleerd is blijft niet langer liggen dan een gewone escalatie.

| Termijn | Standaard | Status |
|---|---|---|
| `OA_TERMIJN_AVG_DAGEN` | 28 | wettelijk (een maand) |
| `OA_TERMIJN_ESCALATIE_DAGEN` | 14 | werkafspraak, stel bij naar eigen beleid |
| `OA_TERMIJN_STANDAARD_DAGEN` | 21 | werkafspraak, stel bij naar eigen beleid |

De werkvoorraad kleurt wat over de termijn is en heeft een filter op *over de
termijn* en *binnen 7 dagen*.

## De inschattingen toetsen

De priors in `taxonomie.yaml` zijn ingeschat. Leg per dossier vast hoe het
werkelijk afliep — via het scherm of `POST /api/bezwaren/{id}/afloop` — en zet ze
daarna naast elkaar:

```bash
.venv/bin/python -m app.kalibratie --minimaal 20
```

Wat je zoekt is een categorie die structureel wordt **onderschat**: laag
ingeschat, maar de vordering wordt in de praktijk vaak gecorrigeerd. Dat betekent
dat de afdeling daar bezwaren afwijst die hout snijden, en dat is de dure fout.

- `http://localhost:8100/` — werkvoorraad en review-scherm
- `http://localhost:8100/docs` — API

Zonder LLM-sleutel draait alles door op trefwoorden en een briefsjabloon. Dat is
bruikbaar om te testen en om door te werken als de API onbereikbaar is; het is geen
productiemodus, en dossiers die zo zijn behandeld worden altijd geëscaleerd.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

45 tests, volledig offline: geen API-sleutel en geen netwerk nodig. De artikelzoeker
wordt getest tegen een lokaal BWB-fragment, zodat de logica controleerbaar is zonder
toegang tot het repository.

## Wat nog moet gebeuren voordat dit live kan

Dit is een werkend systeem, geen afgeronde implementatie. Openstaande punten:

1. **Draai `sync artikelen` en laat een jurist de treffers nalopen.** De acht
   zoekopdrachten dekken de aansluittaak, de transporttaak, verwijdering van een
   aansluiting, de verplichte leveringsovereenkomst, de tariefvaststelling, het
   afsluitbeleid, de periodieke aansluitvergoeding en de definitie van
   *aangeslotene*. Wat de zoeker oplevert is echte wettekst, maar de koppeling aan
   een bezwaarcategorie is een voorstel — accordeer op `/kennisbank` wat klopt en
   laat de rest staan. Tot dat gebeurt argumenteert de agent alleen met het
   Burgerlijk Wetboek. Vorderingen over periodes vóór 2026 worden automatisch onder
   de Elektriciteitswet 1998 en de Gaswet beantwoord; het datamodel houdt die grens
   per bron bij.
2. **De fetchers zijn niet live getest.** Ze zijn geschreven tegen de
   gedocumenteerde open-data-endpoints van KOOP en de Rechtspraak, maar in de
   bouwomgeving blokkeerde het netwerkbeleid beide domeinen. Draai
   `sync wetten` en `sync jurisprudentie` als eerste stap op een omgeving met
   internettoegang.
3. **De open dataset van de Rechtspraak kent geen volledige tekstzoekfunctie.**
   `sync jurisprudentie` maakt daarom een grove voorselectie op trefwoorden. Voor
   serieus zoekwerk levert een jurist ECLI's aan, die met `sync ecli` worden
   opgehaald en geverifieerd.
4. **Authenticatie ontbreekt.** Er zit geen inlog op de API of de UI. Zet dit
   achter jullie bestaande SSO of in elk geval achter een reverse proxy met
   authenticatie voordat er dossiergegevens in gaan.
5. **AVG.** Bezwaarbrieven bevatten persoonsgegevens en de teksten gaan naar een
   LLM-provider. Leg een verwerkersovereenkomst en een bewaartermijn vast, en
   overweeg pseudonimisering vóór verzending naar het model. Bespreek dit met de
   functionaris gegevensbescherming voordat dit in gebruik gaat.
6. **De priors zijn een startpunt, geen meting.** De waarden in `taxonomie.yaml`
   zijn ingeschat. Meet ze na een paar honderd dossiers bij op de werkelijke
   uitkomsten en stel ze bij.

## Structuur

```
app/
  agent/         analyse -> bronnencontrole -> beoordeling -> concept -> guardrails
  knowledge/     kennisbank, fetchers voor wetten.overheid.nl en rechtspraak.nl
    seed/        taxonomie, wetsartikelen, jurisprudentieprofielen, trefwoorden
  ingest/        PDF/OCR, IMAP, intake
  worker.py      wachtrij en achtergrondverwerking
  termijnen.py   uiterste reactiedatum per dossier
  kalibratie.py  inschattingen naast de werkelijke afloop
  api/           REST + server-rendered review-UI
  models.py      bezwaren, argumenten, bronnen, concepten, audit
tests/           45 tests, offline
```
