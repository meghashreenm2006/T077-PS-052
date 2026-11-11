# System Design: Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

## 1. Overview

The Cold-Chain Shipment Temperature Compliance and Claims Engine is a production-grade system designed to monitor temperature-sensitive shipments in pharmaceutical, vaccine, and frozen-food logistics.

The system processes temperature logger readings, detects temperature excursions (including trailing and freezing events), monitors data transmission gaps, calculates Mean Kinetic Temperature (MKT) via Arrhenius kinetics, evaluates multi-tier release compliance, allocates carrier liability across multi-modal transport legs, calculates financial penalties, and generates regulatory audit reports.

## 2. Objectives

- **Profile Configuration:** Define product temperature profiles with minimum, maximum, hard thresholds, MKT limits, and gap tolerances.
- **Shipment Management:** Manage multi-leg shipments, consignments, carriers, and chain-of-custody hand-offs.
- **Sensor Data Ingestion:** Ingest and validate time-series temperature logger data from CSV, JSON, and CLI inputs.
- **Excursion Detection:** Accurately detect closed and trailing excursions, classify severity (HIGH/LOW), and record extreme temperatures.
- **Data Gap Detection:** Identify missing data intervals exceeding configured logger frequencies.
- **MKT Calculation & Validation:** Compute Haynes/Arrhenius Mean Kinetic Temperature and validate against lower and upper limits.
- **Disposition Engine:** Render auditable `RELEASE`, `QUARANTINE`, or `REJECT` decisions with comprehensive audit rationale.
- **Claims & Penalties:** Attribute temperature breaches to responsible transport legs and calculate contractual carrier penalties.
- **Reporting & Documentation:** Generate official Release Certificates, Deviation Notices, and Claim Settlement Invoices.
- **Web Dashboard:** Modern, responsive interface providing interactive temperature curves, timeline visualization, and reporting.

## 3. Technology Stack

- **Core Engine:** Python 3.10+ (Standard Library: `math`, `datetime`, `unittest`)
- **Backend API:** FastAPI with Pydantic v2 validation and Uvicorn ASGI server
- **Database:** SQLite via SQLAlchemy ORM
- **Frontend Dashboard:** Modern responsive SPA (HTML5, CSS, Chart.js) served via FastAPI static mounting
- **CLI:** Interactive terminal interface preserving backward compatibility
- **Testing:** Python `unittest` test suite covering core, custody, claims, reports, and API

## 4. Architecture and Modules

```text
T077-PS-052/
├── src/
│   ├── main.py                  # CLI interactive interface
│   ├── profiles.py              # Configurable product profiles registry
│   ├── excursion_detector.py    # Excursion & data gap detection
│   ├── mkt_calculator.py        # Arrhenius MKT calculation & bounds validation
│   ├── decision_engine.py       # Auditable compliance rule engine
│   ├── shipment_processor.py    # Pipeline coordinator
│   ├── custody_tracker.py       # Multi-leg chain-of-custody validation (Phase 2)
│   ├── claims_engine.py         # Carrier liability & penalties engine (Phase 3)
│   ├── reporting.py             # Certificates & report generators (Phase 4)
│   ├── database.py              # SQLAlchemy database engine & sessions (Phase 2)
│   ├── models/                  # ORM database models (Phases 2-3)
│   ├── schemas/                 # Pydantic schemas (Phase 5)
│   ├── api/                     # FastAPI route handlers (Phase 5)
│   └── static/                  # Responsive web dashboard assets (Phase 5)
└── tests/
    ├── test_main.py             # CLI test suite
    ├── test_core.py             # Core analytical engine tests (25 tests)
    ├── test_custody.py          # Custody hand-off tests (Phase 2)
    ├── test_claims.py           # Liability allocation tests (Phase 3)
    ├── test_reports.py          # Report export tests (Phase 4)
    └── test_api.py              # End-to-end API tests (Phase 5)
```

## 5. Core Analytical Formulas & Rules

### Mean Kinetic Temperature (Haynes Equation)
$$T_{k} = \frac{-\Delta H / R}{\ln\left(\frac{\sum_{i=1}^{n} w_i e^{-\Delta H / (R T_i)}}{\sum_{i=1}^{n} w_i}\right)}$$
- $\Delta H = 83,144\text{ J/mol}$ (Activation Energy)
- $R = 8.314\text{ J/(mol}\cdot\text{K)}$ (Universal Gas Constant)
- $T_i$: Temperature at reading $i$ in Kelvin ($^\circ\text{C} + 273.15$)
- $w_i$: Reading interval duration (weights)

### Compliance Hierarchy
1. **REJECT (Critical Severity):** Any temperature reading $T < \text{hard\_min}$ or $T > \text{hard\_max}$.
2. **QUARANTINE (Investigation Required):**
   - Invalid or unverified chain of custody.
   - $\text{MKT} < \text{min\_mkt}$ or $\text{MKT} > \text{max\_mkt}$.
   - Total missing data gap duration $> \text{allowed\_gap\_minutes}$.
   - Any single data gap $> \text{single\_gap\_limit\_minutes}$.
   - Cumulative excursion duration $> \text{allowed\_minutes}$.
   - Number of qualifying excursions ($\ge 5\text{ min}$) $> \text{allowed\_excursions}$.
3. **RELEASE (Compliant):** All criteria satisfied without deviation.
