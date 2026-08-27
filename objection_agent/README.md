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

**Er staat geen enkel ECLI-nummer in de seed.** Uit het hoofd opgeschreven
jurisprudentie is precies de fout die we bestrijden. In plaats daarvan staan er
zoekprofielen in `jurisprudentie.yaml`; `sync jurisprudentie` haalt daarmee echte
uitspraken op met hun echte tekst. Die komen binnen als *kandidaat* en worden pas
citeerbaar nadat een jurist ze heeft geaccordeerd.

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
.venv/bin/python -m app.knowledge.sync wetten           # wetteksten ophalen en verifieren
.venv/bin/python -m app.knowledge.sync jurisprudentie   # kandidaat-uitspraken oogsten
.venv/bin/python -m app.knowledge.sync ecli ECLI:NL:HR:2024:123 --categorie verjaring --accorderen
.venv/bin/python -m app.knowledge.sync status           # wat is citeerbaar
```

Eigen materiaal — werkinstructies, standaardparagrafen, de ACM-codebesluiten —
gaat erin via `POST /api/kennisbank/bronnen`. Zolang `geaccordeerd` niet is gezet,
is het zichtbaar voor de medewerker maar niet citeerbaar.

## Draaien

```bash
.venv/bin/uvicorn app.main:app --reload --port 8100
```

- `http://localhost:8100/` — werkvoorraad en review-scherm
- `http://localhost:8100/docs` — API

Zonder LLM-sleutel draait alles door op trefwoorden en een briefsjabloon. Dat is
bruikbaar om te testen en om door te werken als de API onbereikbaar is; het is geen
productiemodus, en dossiers die zo zijn behandeld worden altijd geëscaleerd.

## Tests

```bash
.venv/bin/python -m pytest tests/ -q
```

26 tests, volledig offline: geen API-sleutel en geen netwerk nodig.

## Wat nog moet gebeuren voordat dit live kan

Dit is een werkend systeem, geen afgeronde implementatie. Openstaande punten:

1. **De Energiewet-artikelen moeten ingevuld.** Sinds 1 januari 2026 vervangt de
   Energiewet de Elektriciteitswet 1998 en de Gaswet. Het BWB-id staat nog op
   `null` in `wetsartikelen.yaml`, en de drie artikelen die de aansluit- en
   transporttaak dragen — het hart van elk ASC-dossier — moeten door een jurist
   worden aangewezen. Tot dat gebeurt zijn ze niet citeerbaar en valt de agent
   terug op het Burgerlijk Wetboek. Vorderingen over periodes vóór 2026 vallen nog
   onder het oude recht; het datamodel houdt dat per bron bij.
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
  api/           REST + server-rendered review-UI
  models.py      bezwaren, argumenten, bronnen, concepten, audit
tests/           26 tests, offline
```
