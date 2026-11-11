# Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

---

## Project Overview

The Cold-Chain Shipment Temperature Compliance and Claims Engine is a production-grade system for monitoring temperature-sensitive shipments in pharmaceutical, vaccine, and perishable food logistics.

The system processes temperature logger time-series data, accurately identifies temperature excursions (including ongoing trailing excursions and freezing events), monitors data transmission dropouts, calculates Mean Kinetic Temperature (MKT) via Arrhenius kinetics, renders auditable consignment release decisions, allocates multi-modal carrier liability, calculates contract penalties, and produces compliance certificates and claim settlement reports.

---

## ✅ Phase Status

| Phase | Feature | Status |
|---|---|---|
| Phase 1 | Core Engine — Excursion detection, MKT, Decisions, CLI | ✅ Complete |
| Phase 2 | Consignment, carrier, transport-leg, chain-of-custody management | ✅ Complete |
| Phase 3 | Multi-modal liability allocation, penalty calculation, claim settlement | ✅ Complete |
| Phase 4 | Release certificates, quarantine deviation reports, claim invoices | ✅ Complete |
| Phase 5 | FastAPI backend, Pydantic v2, SQLite/SQLAlchemy, HTML/CSS/JS dashboard | ✅ Complete |
| Phase 6 | Integration — real sample data wired to API and dashboard | ✅ Complete |

---

## Project Structure

```text
T077-PS-052/
├── src/
│   ├── __init__.py
│   ├── main.py                  # CLI interface (preserved)
│   ├── profiles.py              # Product temperature profiles
│   ├── excursion_detector.py    # Excursion & data-gap detector
│   ├── mkt_calculator.py        # Arrhenius MKT calculator
│   ├── decision_engine.py       # Compliance decision engine
│   ├── shipment_processor.py    # End-to-end shipment processor
│   ├── compliance_engine.py     # Full engine: multi-leg, claims, penalties
│   ├── database.py              # SQLAlchemy models + SQLite setup (NEW)
│   ├── api.py                   # FastAPI backend (extended Phase 5/6)
│   └── static/
│       ├── index.html           # Dashboard HTML (NEW)
│       ├── style.css            # Dashboard CSS (NEW)
│       └── app.js               # Dashboard JavaScript (NEW)
├── tests/
│   ├── test_core.py             # 70 unit/integration tests
│   ├── test_compliance_engine.py
│   └── test_main.py
├── sample_data/
│   └── T077-PS-052-sample-data/
│       ├── commands.txt
│       ├── shipments.csv        # 20 shipments
│       ├── consignments.csv     # 35 consignments
│       ├── legs.csv             # 57 transport legs
│       ├── handoffs.csv         # Custody handoff events
│       ├── profiles.csv         # 5 temperature profiles
│       └── readings_shp_*.csv   # Temperature logger data
├── output/
│   ├── decisions.csv
│   ├── excursions.csv
│   ├── penalties.csv
│   ├── claims.csv
│   └── release_certificates.csv
├── docs/
│   ├── design.md
│   └── decision-log.md
├── coldchain.db                 # SQLite database (auto-created on first run)
├── requirements.txt
└── README.md
```

---

## ⚡ Quick Start — Windows PowerShell

### Step 1 — Install dependencies (run once)

```powershell
cd "C:\Users\Megha Shree\Desktop\T077-PS-052"
pip install -r requirements.txt
```

### Step 2 — Start the web application

```powershell
cd "C:\Users\Megha Shree\Desktop\T077-PS-052"
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

### Step 3 — Open the dashboard

Open your browser and go to:
```
http://localhost:8000
```

The first startup automatically loads all 20 sample shipments into the database. This takes about 5–10 seconds.

---

## 🖥 Running the CLI (preserved)

```powershell
cd "C:\Users\Megha Shree\Desktop\T077-PS-052"
python -m src.main
```

---

## 🧪 Running the Tests

```powershell
cd "C:\Users\Megha Shree\Desktop\T077-PS-052"
python -m unittest discover tests -v
```

---

## 🌐 API Endpoints

| Method | URL | Description |
|---|---|---|
| GET | `/` | Dashboard HTML |
| GET | `/api/dashboard` | Live summary stats for all 20 shipments |
| GET | `/api/shipments/{id}/readings` | Temperature readings for Chart.js |
| GET | `/api/shipments/{id}/detail` | Full shipment audit from database |
| GET | `/api/reports/excursions` | All excursion events |
| GET | `/api/reports/penalties` | All carrier penalties |
| GET | `/api/reports/claims` | All liability claims |
| GET | `/api/reports/certificates` | All release certificates |
| GET | `/api/reports/quarantine` | Quarantine deviation report |
| GET | `/api/reports/claim-invoice/{id}` | Claim invoice for one shipment |
| POST | `/api/run` | Upload CSV files and run evaluation |
| GET | `/docs` | Auto-generated API documentation |

---

## Technology Stack

| Layer | Technology |
|---|---|
| Core Engine | Python 3.10+ (stdlib only: `math`, `datetime`, `csv`) |
| Web API | FastAPI + Pydantic v2 + Uvicorn |
| Database | SQLite + SQLAlchemy 2.0 |
| Frontend | HTML5 / CSS3 / Vanilla JavaScript |
| Charts | Chart.js 4.4 (CDN) |
