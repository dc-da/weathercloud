# WeatherStation PWS — Specifica di Progetto

## Panoramica

Applicazione web Python per il monitoraggio, la storicizzazione e l'analisi dei dati meteorologici provenienti da una stazione personale (PWS) registrata su Weather Underground (WU). L'app offre 4 viste principali (istantanea, giornaliera, storica, report/aggregazioni) con visualizzazioni grafiche e tabellari.

---

## Stack Tecnologico

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.11+ / Flask |
| Database | DuckDB (file singolo, embedded, orientato all'analisi) |
| Frontend | HTML5 / CSS3 / JavaScript |
| Grafici | Plotly.js (grafici interattivi, zoom, pan, export) |
| Tabelle | DataTables.js (sorting, filtering, pagination, export) |
| Scheduler | APScheduler (integrato in Flask) |
| HTTP Client | `requests` |
| Configurazione | YAML (`config.yaml`) |

### Dipendenze Python principali

```
flask
duckdb
apscheduler
requests
pyyaml
pandas
```

---

## Configurazione (`config.yaml`)

```yaml
# Weather Underground
wu:
  api_key: "YOUR_API_KEY"
  station_id: "YOUR_STATION_ID"
  units: "m"  # m = metrico (°C, km/h, mm, hPa)

# Database
database:
  path: "data/weather.duckdb"

# API Base URLs
api:
  current_conditions: "https://api.weather.com/v2/pws/observations/current"
  daily_summary_7day: "https://api.weather.com/v2/pws/dailysummary/7day"
  rapid_history_1day: "https://api.weather.com/v2/pws/observations/all/1day"
  hourly_history_7day: "https://api.weather.com/v2/pws/observations/hourly/7day"  
  historical: "https://api.weather.com/v2/pws/history/daily"
  forecast_5day: "https://api.weather.com/v3/wx/forecast/daily/5day"

# Job Scheduler
scheduler:
  rapid_history:
    enabled: true
    interval_hours: 4      # ogni 4 ore
  hourly_history:
    enabled: true
    interval_hours: 12     # ogni 12 ore
  # historical: lanciato manualmente dall'utente

# App
app:
  host: "0.0.0.0"
  port: 5000
  debug: false
```

> **NOTA IMPORTANTE sugli URL delle API:** Gli URL sopra sono quelli standard documentati da Weather Underground / The Weather Company. Gli URL abbreviati forniti dall'utente (`https://twcapi.co/v2PWSO`, etc.) sono redirect/alias. L'implementazione deve usare gli URL completi dell'API ufficiale. Se gli URL non funzionano, controllare la documentazione WU aggiornata e adattare. I parametri comuni a tutte le chiamate sono: `stationId`, `apiKey`, `units=m`, `format=json`.

---

## Modello Dati (DuckDB)

### Tabella: `rapid_observations`

Dati a granularità massima (~5 minuti, dipende dalla frequenza di trasmissione della stazione). Fonte: API Rapid History 1-Day.

```sql
CREATE TABLE IF NOT EXISTS rapid_observations (
    station_id          VARCHAR NOT NULL,
    observed_at         TIMESTAMP NOT NULL,     -- UTC
    observed_at_local   TIMESTAMP,              -- timezone locale stazione
    
    -- Temperatura
    temp_c              DOUBLE,                 -- °C
    heat_index_c        DOUBLE,
    dew_point_c         DOUBLE,
    wind_chill_c        DOUBLE,
    
    -- Umidità
    humidity_pct        DOUBLE,                 -- %
    
    -- Pressione
    pressure_hpa        DOUBLE,                 -- hPa (= mbar)
    
    -- Vento
    wind_speed_kmh      DOUBLE,                 -- km/h
    wind_gust_kmh       DOUBLE,
    wind_dir_deg        INTEGER,                -- gradi (0-360)
    
    -- Precipitazioni
    precip_rate_mmh     DOUBLE,                 -- mm/h (tasso istantaneo)
    precip_total_mm     DOUBLE,                 -- mm (accumulo giornaliero)
    
    -- Radiazione solare / UV
    solar_radiation_wm2 DOUBLE,                 -- W/m²
    uv_index            DOUBLE,
    
    -- Metadati sincronizzazione
    synced_at           TIMESTAMP DEFAULT current_timestamp,
    source              VARCHAR DEFAULT 'rapid', -- 'rapid'
    
    PRIMARY KEY (station_id, observed_at)
);
```

### Tabella: `hourly_observations`

Dati a granularità oraria. Fonte: API Hourly History 7-Day.

```sql
CREATE TABLE IF NOT EXISTS hourly_observations (
    station_id          VARCHAR NOT NULL,
    observed_at         TIMESTAMP NOT NULL,     -- UTC
    observed_at_local   TIMESTAMP,
    
    -- Stessi campi meteo di rapid_observations
    temp_c              DOUBLE,
    heat_index_c        DOUBLE,
    dew_point_c         DOUBLE,
    wind_chill_c        DOUBLE,
    humidity_pct        DOUBLE,
    pressure_hpa        DOUBLE,
    wind_speed_kmh      DOUBLE,
    wind_gust_kmh       DOUBLE,
    wind_dir_deg        INTEGER,
    precip_rate_mmh     DOUBLE,
    precip_total_mm     DOUBLE,
    solar_radiation_wm2 DOUBLE,
    uv_index            DOUBLE,
    
    synced_at           TIMESTAMP DEFAULT current_timestamp,
    source              VARCHAR DEFAULT 'hourly',
    
    PRIMARY KEY (station_id, observed_at)
);
```

### Tabella: `daily_observations`

Dati a granularità giornaliera (aggregati dalla stazione). Fonte: API Historical.

```sql
CREATE TABLE IF NOT EXISTS daily_observations (
    station_id          VARCHAR NOT NULL,
    obs_date            DATE NOT NULL,
    
    -- Temperature (min/max/avg della giornata)
    temp_avg_c          DOUBLE,
    temp_high_c         DOUBLE,
    temp_low_c          DOUBLE,
    
    -- Umidità
    humidity_avg_pct    DOUBLE,
    humidity_high_pct   DOUBLE,
    humidity_low_pct    DOUBLE,
    
    -- Punto di rugieda
    dew_point_avg_c     DOUBLE,
    dew_point_high_c    DOUBLE,
    dew_point_low_c     DOUBLE,
    
    -- Pressione
    pressure_avg_hpa    DOUBLE,
    pressure_max_hpa    DOUBLE,
    pressure_min_hpa    DOUBLE,
    
    -- Vento
    wind_speed_avg_kmh  DOUBLE,
    wind_speed_high_kmh DOUBLE,
    wind_gust_high_kmh  DOUBLE,
    
    -- Precipitazioni
    precip_total_mm     DOUBLE,
    
    -- Metadati
    synced_at           TIMESTAMP DEFAULT current_timestamp,
    source              VARCHAR DEFAULT 'historical',
    
    PRIMARY KEY (station_id, obs_date)
);
```

### Tabella: `sync_log`

Log di tutte le operazioni di sincronizzazione per tracciabilità e debug.

```sql
CREATE TABLE IF NOT EXISTS sync_log (
    id                  INTEGER PRIMARY KEY,
    started_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    job_type            VARCHAR NOT NULL,       -- 'rapid', 'hourly', 'historical'
    status              VARCHAR NOT NULL,       -- 'running', 'success', 'error'
    records_fetched     INTEGER DEFAULT 0,
    records_inserted    INTEGER DEFAULT 0,
    records_updated     INTEGER DEFAULT 0,
    date_range_start    TIMESTAMP,
    date_range_end      TIMESTAMP,
    error_message       TEXT,
    api_calls_made      INTEGER DEFAULT 0
);
```

### Gestione Valori Mancanti

**Principio fondamentale:** I timestamp devono essere SEMPRE presenti. Se un dato meteo è mancante, il valore è `NULL` ma il record con il timestamp esiste.

**Strategia per `rapid_observations`:**

1. Dopo ogni fetch dall'API, determinare la griglia temporale attesa (es. ogni 5 minuti tra il primo e l'ultimo dato ricevuto)
2. Generare tutti i timestamp della griglia
3. Fare LEFT JOIN con i dati ricevuti
4. Inserire i record con valori `NULL` per i timestamp senza dati
5. Questo garantisce che i grafici mostrino i "buchi" come interruzioni visibili

**Strategia per `hourly_observations`:**

Stessa logica, con griglia oraria (ogni 60 minuti).

**Strategia per `daily_observations`:**

Stessa logica, con griglia giornaliera (ogni giorno tra data inizio e data fine).

---

## API Weather Underground — Specifiche di Chiamata

### Parametri comuni a tutte le chiamate

```
stationId={station_id}
apiKey={api_key}
units=m
format=json
```

### 1. Current Conditions (`v2/pws/observations/current`)

- **Uso:** Vista istantanea
- **Parametri:** solo quelli comuni
- **Risposta:** oggetto singolo con le condizioni correnti
- **Rate limit:** consultare documentazione WU (tipicamente generoso per PWS owner)

### 2. Rapid History 1-Day (`v2/pws/observations/all/1day`)

- **Uso:** Job rapid_history + Vista giornaliera dettagliata
- **Parametri:** solo quelli comuni (restituisce le ultime 24h)
- **Risposta:** array di osservazioni a granularità ~5 min
- **NOTA:** Questa è la finestra a più alta risoluzione. Dopo 24h i dati non sono più disponibili a questa granularità.

### 3. Hourly History 7-Day (`v2/pws/observations/hourly/7day`)  

- **Uso:** Job hourly_history + Vista giornaliera
- **Parametri:** solo quelli comuni (restituisce gli ultimi 7 giorni)
- **Risposta:** array di osservazioni a granularità oraria

### 4. Historical Daily (`v2/pws/history/daily`)

- **Uso:** Job historical (manuale) + Vista storica
- **Parametri aggiuntivi:** `date=YYYYMMDD` (un giorno alla volta)
- **Risposta:** summary giornaliero per la data richiesta
- **NOTA:** Per il backfill completo, iterare giorno per giorno dalla data di installazione della stazione fino a oggi. Implementare throttling tra le chiamate (es. 500ms-1s di pausa) per rispettare i rate limit.

### 5. Daily Forecast 5-Day (`v3/wx/forecast/daily/5day`)

- **Uso:** Widget previsioni nella vista istantanea (opzionale, fase 2)
- **Parametri:** `geocode={lat},{lon}` oppure query location
- **Risposta:** previsioni per i prossimi 5 giorni

### Gestione Errori API

- **HTTP 401:** API key non valida o scaduta → log + notifica utente
- **HTTP 204 / body vuoto:** nessun dato disponibile per la stazione/periodo → log, nessun inserimento
- **HTTP 429:** rate limit raggiunto → retry con backoff esponenziale (2s, 4s, 8s, max 3 tentativi)
- **Timeout:** 30 secondi per chiamata → retry
- **Errore generico:** log dettagliato in `sync_log`, continua con la prossima iterazione

---

## Job di Sincronizzazione

### Job 1: Rapid History (automatico)

- **Frequenza:** Ogni 4 ore (configurabile in `config.yaml`)
- **API:** Rapid History 1-Day
- **Tabella destinazione:** `rapid_observations`
- **Logica:**
  1. Chiama API Rapid History 1-Day
  2. Parsa la risposta JSON, estrai tutti i record
  3. Per ogni record, mappa i campi JSON ai campi DB
  4. Genera la griglia temporale completa (ogni 5 min) tra il primo e l'ultimo timestamp ricevuto
  5. `INSERT OR REPLACE` — se il record esiste già (stesso station_id + observed_at), aggiorna
  6. Per i timestamp della griglia senza dati, inserisci record con valori meteo `NULL`
  7. Logga in `sync_log`

### Job 2: Hourly History (automatico)

- **Frequenza:** Ogni 12 ore (configurabile in `config.yaml`)
- **API:** Hourly History 7-Day
- **Tabella destinazione:** `hourly_observations`
- **Logica:** Stessa logica del Job 1, ma con griglia oraria

### Job 3: Historical Backfill (manuale)

- **Trigger:** Lanciato dall'utente via UI (bottone "Scarica Storico")
- **API:** Historical Daily
- **Tabella destinazione:** `daily_observations`
- **Logica:**
  1. L'utente specifica la data di inizio (o "dall'inizio" se la stazione ha storico)
  2. Determina la data di fine = oggi
  3. Query DB: trova l'ultimo `obs_date` presente → riparti da lì (se esiste già dello storico)
  4. Per ogni giorno mancante:
     a. Chiama API Historical con `date=YYYYMMDD`
     b. Se dati presenti: inserisci/aggiorna in `daily_observations`
     c. Se dati assenti (HTTP 204 o body vuoto): inserisci record con `obs_date` valorizzato e tutti i campi meteo a `NULL`
     d. Pausa 500ms tra le chiamate (rate limiting)
  5. Mostra progresso all'utente (progress bar o log in tempo reale via SSE/WebSocket)
  6. Logga in `sync_log`

### Riconciliazione (integrata nei Job 1 e 2)

I Job 1 e 2 scaricano sempre l'intera finestra disponibile (1 giorno per rapid, 7 giorni per hourly) e fanno `INSERT OR REPLACE`. Questo copre automaticamente:
- Dati mancanti da run precedenti falliti
- Dati arrivati in ritardo dalla stazione
- Correzioni di dati

Non serve un job separato di riconciliazione mensile: la sovrapposizione delle finestre temporali è sufficiente.

---

## Struttura dell'Applicazione

```
weatherstation/
├── config.yaml                  # Configurazione (API key, station ID, scheduler)
├── config.yaml.example          # Template di configurazione
├── requirements.txt
├── run.py                       # Entry point
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Caricamento config YAML
│   ├── database.py              # DuckDB connection, init schema, utility queries
│   ├── models.py                # Mapping campi API → campi DB
│   ├── api_client.py            # Client Weather Underground (tutte le chiamate API)
│   ├── scheduler.py             # APScheduler setup e job definitions
│   ├── sync/
│   │   ├── __init__.py
│   │   ├── rapid.py             # Job 1: rapid history sync
│   │   ├── hourly.py            # Job 2: hourly history sync
│   │   └── historical.py        # Job 3: historical backfill
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── dashboard.py         # Vista istantanea
│   │   ├── daily.py             # Vista giornaliera
│   │   ├── historical.py        # Vista storica
│   │   ├── reports.py           # Vista report/aggregazioni
│   │   ├── sync_api.py          # API endpoints per gestione sync (start/stop/status)
│   │   └── export.py            # Export CSV/Excel
│   ├── templates/
│   │   ├── base.html            # Layout base (navbar, sidebar)
│   │   ├── dashboard.html       # Vista istantanea
│   │   ├── daily.html           # Vista giornaliera
│   │   ├── historical.html      # Vista storica
│   │   └── reports.html         # Vista report
│   └── static/
│       ├── css/
│       │   └── style.css
│       └── js/
│           ├── dashboard.js     # Logica vista istantanea (polling, gauge)
│           ├── daily.js         # Logica vista giornaliera
│           ├── historical.js    # Logica vista storica
│           └── reports.js       # Logica report
└── data/
    └── weather.duckdb           # Database (creato automaticamente)
```

---

## Viste dell'Applicazione

### Vista 1: Istantanea (Dashboard)

**Fonte dati:** API Current Conditions (chiamata diretta, non da DB)

**Refresh:** Configurabile dall'utente tramite un selettore nella UI:
- Opzioni: 30 secondi, 1 minuto, 5 minuti, Manuale (bottone)
- Il valore selezionato viene salvato in localStorage e ricordato tra le sessioni

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  [Refresh: ▼ 60s]  Ultimo aggiornamento: HH:MM:SS  │
├────────────┬────────────┬────────────┬──────────────┤
│            │            │            │              │
│  🌡️ TEMP   │  💧 UMIDITÀ │  🌬️ VENTO  │  🌧️ PIOGGIA  │
│   22.3°C   │    65%     │  12 km/h   │  0.0 mm/h   │
│            │            │   NW 315°  │  Tot: 2.4mm  │
├────────────┴────────────┴────────────┴──────────────┤
│            │            │            │              │
│  📊 PRESS  │  ☀️ SOLARE  │  UV INDEX  │  DEW POINT   │
│ 1013.2 hPa │  450 W/m²  │    3       │   14.2°C    │
│            │            │            │              │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Mini-grafico: ultime 24h temperatura + umidità    │
│   (da rapid_observations in DB se disponibile)      │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Componenti UI:**
- Card/gauge per ogni metrica principale con colori contestuali (es. temp calda = arancione, fredda = blu)
- Bussola per direzione vento
- Mini-grafico sparkline ultime 24h (opzionale, dalla tabella `rapid_observations`)
- Indicatore di stato connessione/ultimo dato ricevuto

---

### Vista 2: Giornaliera

**Fonte dati:** Tabelle `rapid_observations` e `hourly_observations` dal DB

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Data: [📅 date picker]    Fonte: [● Rapid ○ Hourly]│
├─────────────────────────────────────────────────────┤
│                                                     │
│  GRAFICO PRINCIPALE (Plotly, interattivo)           │
│  - Asse X: tempo                                    │
│  - Metriche selezionabili via checkbox:             │
│    ☑ Temperatura  ☑ Umidità  ☐ Pressione           │
│    ☐ Vento  ☐ Precipitazioni  ☐ UV                 │
│  - Multi-asse Y per metriche con scale diverse      │
│  - Zoom, pan, hover con dettagli                    │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TABELLA DATI (DataTables)                          │
│  Tutte le colonne, sorting, ricerca, paginazione    │
│  Righe con valori NULL evidenziate (sfondo diverso) │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Funzionalità:**
- Selettore data (default: oggi)
- Toggle tra fonte Rapid (5 min) e Hourly
- Selezione multipla delle metriche da visualizzare sul grafico
- Tabella completa con tutti i campi, valori NULL evidenziati visivamente
- La tabella e il grafico si aggiornano insieme al cambio di filtri

---

### Vista 3: Storica (solo consultazione)

**Fonte dati:** Tabella `daily_observations` dal DB

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Range: [📅 Da] → [📅 A]    [🔍 Filtra]             │
│                                                     │
│  [▶ Avvia Scaricamento Storico]  Status: ████░ 73%  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  GRAFICO (Plotly)                                   │
│  - Serie temporale giornaliera                      │
│  - Metriche selezionabili (temp avg/high/low, etc.) │
│  - Range slider sotto il grafico                    │
│                                                     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TABELLA DATI GIORNALIERI                           │
│  Tutte le colonne, sorting, export                  │
│  Righe mancanti (tutti NULL) evidenziate            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Funzionalità:**
- Filtro per range di date
- Bottone per lanciare il backfill storico
  - Input: data inizio (opzionale, default: prima data disponibile su WU)
  - Progress bar in tempo reale (via Server-Sent Events)
  - Possibilità di interrompere lo scaricamento
- Grafico con range slider per navigare periodi lunghi
- Solo consultazione: NO report/aggregazioni su questi dati

---

### Vista 4: Report e Aggregazioni

**Fonte dati:** Tabelle `rapid_observations` e `hourly_observations`

**Layout:**

```
┌─────────────────────────────────────────────────────┐
│  Fonte: [● Rapid ○ Hourly]                         │
│  Periodo: [📅 Da] → [📅 A]                          │
│  Aggregazione: [Giornaliera ▼]                      │
│  [📊 Genera Report]   [📥 Export CSV] [📥 Export XLS]│
├─────────────────────────────────────────────────────┤
│                                                     │
│  SEZIONE 1: MEDIE GIORNALIERE MIN/MAX               │
│  ┌─────────────────────────────────────────────┐    │
│  │ Tabella:                                    │    │
│  │ Data | Temp Avg | Temp Min | Temp Max | ... │    │
│  │ Grafico: barre min/max con linea media      │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  SEZIONE 2: CONFRONTO TRA PERIODI                   │
│  ┌─────────────────────────────────────────────┐    │
│  │ Periodo A: [📅 Da] → [📅 A]                 │    │
│  │ Periodo B: [📅 Da] → [📅 A]                 │    │
│  │ Metrica: [Temperatura ▼]                    │    │
│  │                                             │    │
│  │ Grafico overlay: due serie sovrapposte      │    │
│  │ Tabella comparativa: avg, min, max, delta   │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  SEZIONE 3: HEATMAP ORARIA                          │
│  ┌─────────────────────────────────────────────┐    │
│  │ Metrica: [Temperatura ▼]                    │    │
│  │                                             │    │
│  │ Heatmap: asse X = ora (0-23), asse Y = data │    │
│  │ Colore = valore della metrica               │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**Funzionalità dettagliate:**

#### Medie Giornaliere Min/Max
- Calcolo da `rapid_observations` o `hourly_observations` (scelta utente)
- Per ogni giorno nel range: media, minimo, massimo di ogni metrica
- Grafico a barre con errore (min-max) e linea media
- Tabella con tutte le metriche aggregate

#### Confronto tra Periodi
- L'utente seleziona due range di date e una metrica
- Grafico overlay: le due serie allineate sullo stesso asse temporale relativo (giorno 1, giorno 2, ...)
- Tabella: media, min, max, deviazione standard per entrambi i periodi + delta/variazione %

#### Heatmap Oraria
- Solo da `rapid_observations` (necessaria granularità sub-oraria) o `hourly_observations`
- Matrice: righe = giorni, colonne = ore (0-23)
- Valore nella cella = media della metrica in quell'ora di quel giorno
- Scala colore continua (es. blu-rosso per temperatura)
- Utile per identificare pattern giornalieri (es. "a che ora fa più caldo?")

#### Export
- **CSV:** Export diretto dei dati filtrati (raw o aggregati)
- **Excel (.xlsx):** Export con formattazione, intestazioni, e un foglio per ogni sezione del report
- Il download viene generato lato server e servito come file

---

## Navbar e Navigazione

```
┌─────────────────────────────────────────────────────┐
│  🌤️ WeatherStation    │ Istantanea │ Giornaliera │   │
│  Station: IXXXXXX     │ Storica    │ Report      │   │
│                       │            │ Sync Status │   │
└─────────────────────────────────────────────────────┘
```

- **Sync Status:** Pagina/modale con lo stato di tutti i job:
  - Ultimo run di ogni job (timestamp, esito, record processati)
  - Prossimo run schedulato
  - Log degli ultimi N sync da `sync_log`
  - Possibilità di forzare un run manuale per Job 1 e Job 2

---

## API Endpoints Backend

### Viste HTML (pagine)

| Metodo | URL | Descrizione |
|---|---|---|
| GET | `/` | Redirect a `/dashboard` |
| GET | `/dashboard` | Vista istantanea |
| GET | `/daily` | Vista giornaliera |
| GET | `/historical` | Vista storica |
| GET | `/reports` | Vista report |
| GET | `/sync-status` | Stato sincronizzazione |

### API JSON (per chiamate AJAX dal frontend)

| Metodo | URL | Descrizione |
|---|---|---|
| GET | `/api/current` | Condizioni correnti (proxy a WU API) |
| GET | `/api/rapid?date=YYYY-MM-DD` | Dati rapid dal DB per una data |
| GET | `/api/hourly?date=YYYY-MM-DD` | Dati hourly dal DB per una data |
| GET | `/api/daily?from=YYYY-MM-DD&to=YYYY-MM-DD` | Dati giornalieri dal DB |
| GET | `/api/report/daily-stats?source=rapid&from=...&to=...` | Medie/min/max giornaliere |
| GET | `/api/report/comparison?...` | Confronto periodi |
| GET | `/api/report/heatmap?source=rapid&metric=temp_c&from=...&to=...` | Dati heatmap |
| POST | `/api/sync/historical/start` | Avvia backfill storico |
| GET | `/api/sync/historical/progress` | SSE: progresso backfill |
| POST | `/api/sync/historical/stop` | Interrompi backfill |
| POST | `/api/sync/rapid/run` | Forza run Job 1 |
| POST | `/api/sync/hourly/run` | Forza run Job 2 |
| GET | `/api/sync/status` | Stato di tutti i job |
| GET | `/api/sync/log?limit=50` | Ultimi N log di sync |
| GET | `/api/export/csv?source=rapid&from=...&to=...` | Export CSV |
| GET | `/api/export/xlsx?source=rapid&from=...&to=...&report_type=...` | Export Excel |

---

## Mapping Campi API → Database

I campi restituiti dall'API WU hanno nomi annidati nel JSON. Ecco il mapping atteso (da verificare con la risposta effettiva dell'API):

### Rapid / Hourly Observations

| Campo API (nested path) | Campo DB |
|---|---|
| `obsTimeUtc` | `observed_at` |
| `obsTimeLocal` | `observed_at_local` |
| `metric.tempAvg` o `metric.temp` | `temp_c` |
| `metric.heatindexAvg` o `metric.heatindex` | `heat_index_c` |
| `metric.dewptAvg` o `metric.dewpt` | `dew_point_c` |
| `metric.windchillAvg` o `metric.windchill` | `wind_chill_c` |
| `humidityAvg` o `humidity` | `humidity_pct` |
| `metric.pressureMax` / `metric.pressure` | `pressure_hpa` |
| `metric.windspeedAvg` o `metric.windspeed` | `wind_speed_kmh` |
| `metric.windgustAvg` o `metric.windgust` | `wind_gust_kmh` |
| `winddirAvg` o `winddir` | `wind_dir_deg` |
| `metric.precipRate` | `precip_rate_mmh` |
| `metric.precipTotal` | `precip_total_mm` |
| `solarRadiation` o `solarRadiationHigh` | `solar_radiation_wm2` |
| `uvHigh` o `uv` | `uv_index` |

> **NOTA:** I nomi esatti dei campi possono variare tra le API (rapid vs hourly vs current). L'implementazione deve gestire entrambe le varianti con fallback. Fare una prima chiamata di test per ogni API e loggare la struttura JSON completa per validare il mapping.

### Historical Daily

| Campo API | Campo DB |
|---|---|
| `metric.tempAvg` | `temp_avg_c` |
| `metric.tempHigh` | `temp_high_c` |
| `metric.tempLow` | `temp_low_c` |
| `humidityAvg` | `humidity_avg_pct` |
| `humidityHigh` | `humidity_high_pct` |
| `humidityLow` | `humidity_low_pct` |
| `metric.dewptAvg` | `dew_point_avg_c` |
| `metric.dewptHigh` | `dew_point_high_c` |
| `metric.dewptLow` | `dew_point_low_c` |
| `metric.pressureMax` | `pressure_max_hpa` |
| `metric.pressureMin` | `pressure_min_hpa` |
| `metric.windspeedAvg` | `wind_speed_avg_kmh` |
| `metric.windspeedHigh` | `wind_speed_high_kmh` |
| `metric.windgustHigh` | `wind_gust_high_kmh` |
| `metric.precipTotal` | `precip_total_mm` |

---

## Note Implementative

### Primo Avvio

1. Se `config.yaml` non esiste, copiare da `config.yaml.example` e avvisare l'utente
2. Verificare che `api_key` e `station_id` siano valorizzati
3. Creare il database DuckDB e le tabelle se non esistono
4. Fare una chiamata di test a Current Conditions per validare le credenziali
5. Avviare lo scheduler con i job configurati
6. L'utente può subito vedere la vista istantanea; le altre viste mostreranno "Nessun dato — avvia una sincronizzazione" finché i job non hanno popolato il DB

### Performance

- DuckDB è ottimizzato per query analitiche su milioni di righe — nessun problema di performance per anni di dati a granularità 5 min (~105.000 record/anno)
- Le query per i report devono usare le funzioni aggregate native di DuckDB (`AVG`, `MIN`, `MAX`, `date_trunc`, `EXTRACT(HOUR FROM ...)`)
- Per la heatmap, usare `PIVOT` o `GROUP BY date, hour` direttamente in SQL

### Sicurezza

- L'API key è nel file di configurazione, MAI nel codice sorgente
- `config.yaml` deve essere nel `.gitignore`
- Nessuna autenticazione utente per ora (fase futura)

### UI/UX

- Framework CSS: Bootstrap 5 (o Tailwind, a scelta dell'implementatore)
- Dark mode toggle (opzionale ma consigliato per dashboard meteo)
- Responsive: le card della dashboard devono funzionare su mobile
- Colori contestuali per i valori (es. temperatura: scala blu → rosso)
- Indicatore visivo per dati mancanti (celle grigie, tratteggio nei grafici)

---

## Fasi di Sviluppo Suggerite

### Fase 1 — Fondamenta
- Setup progetto, config, database
- `api_client.py` con tutte le chiamate API
- Job 1 (rapid) e Job 2 (hourly)
- Vista istantanea (dashboard)

### Fase 2 — Viste Dati
- Vista giornaliera (grafici + tabelle da rapid/hourly)
- Vista storica (backfill + grafici + tabelle da daily)

### Fase 3 — Report
- Medie giornaliere min/max
- Confronto periodi
- Heatmap oraria
- Export CSV/Excel

### Fase 4 — Polish
- Sync status page
- Error handling robusto
- Dark mode
- Responsive mobile
- Test automatici
