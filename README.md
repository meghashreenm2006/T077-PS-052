# Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

## Project Overview

The Cold-Chain Shipment Temperature Compliance and Claims Engine is a production-grade system for monitoring temperature-sensitive shipments in pharmaceutical, vaccine, and perishable food logistics.

The system processes temperature logger time-series data, accurately identifies temperature excursions (including ongoing trailing excursions and freezing events), monitors data transmission dropouts, calculates Mean Kinetic Temperature (MKT) via Arrhenius kinetics, renders auditable consignment release decisions, allocates multi-modal carrier liability, calculates contract penalties, and produces compliance certificates and claim settlement reports.

## Core Capabilities

- **Configurable Product Profiles:** Built-in profiles for Vaccines (2–8°C), Frozen Goods (-25 to -15°C), and Ambient Goods (15–25°C), with dynamic registration for custom profiles (e.g. ultra-cold clinical goods).
- **Accurate Excursion Detection:** Identifies HIGH and LOW temperature excursions, ongoing trailing excursions ending at the final logger point, peak/trough temperatures, and reading counts.
- **Data Gap Monitoring:** Automatically flags missing logger packets when intervals between consecutive readings exceed configurable thresholds.
- **Haynes MKT Calculation & Two-Sided Validation:** Computes Arrhenius MKT (with optional time-weighting) and validates against both lower and upper MKT tolerances.
- **Auditable Decision Engine:** Employs a strict hierarchy (`REJECT` for hard threshold breaches, `QUARANTINE` for MKT/gap/excursion/custody breaches, and `RELEASE` for compliant runs) with complete, traceable rationale logs.
- **Preserved CLI & Backward Compatibility:** CLI interface remains fully operational alongside the modular backend engine.

## Technology Stack

- **Python 3.10+** (Standard Library: `math`, `datetime`, `unittest`)
- **FastAPI / Pydantic v2 / Uvicorn** (Web API layer)
- **SQLite / SQLAlchemy** (Data storage)
- **Chart.js / Responsive Modern HTML & CSS** (Frontend dashboard)

## Project Structure

```text
T077-PS-052/
├── docs/
│   ├── design.md              # Detailed system design
│   └── decision-log.md        # Architectural decision records
├── src/
│   ├── __init__.py
│   ├── main.py                # Preserved CLI interface
│   ├── profiles.py            # Configurable product profiles
│   ├── excursion_detector.py  # Excursion and data gap detector
│   ├── mkt_calculator.py      # Arrhenius MKT calculator & validator
│   ├── decision_engine.py     # Auditable compliance decision engine
│   └── shipment_processor.py  # End-to-end shipment processor
└── tests/
    ├── __init__.py
    ├── test_core.py           # Core analytical engine unit tests (23 tests)
    └── test_main.py           # CLI interface tests (2 tests)
```

## Running Tests

Run the full automated test suite using Python's built-in `unittest`:

```bash
python -m unittest discover tests -v
```

All 25 unit and integration tests run in under 0.01 seconds and pass with 100% compliance.

## Running the CLI

Run the interactive command-line interface:

```bash
python -m src.main
```

## Phase Status

- [x] **Phase 1: Core Engine Refinement** (Trailing excursions, gap detection, upper/lower MKT validation, configurable profiles, auditable decisions, 25 tests)
- [ ] **Phase 2: Shipment & Custody Management** (Consignments, carriers, transport legs, chain of custody tracking)
- [ ] **Phase 3: Claims and Penalties Engine** (Liability allocation, penalty calculations, claim settlements)
- [ ] **Phase 4: Reports & Certificates** (Release certificates, quarantine deviation reports, claim invoices)
- [ ] **Phase 5: Web Application** (FastAPI backend and responsive modern dashboard)
- [ ] **Phase 6: Integration & Final Verification**
