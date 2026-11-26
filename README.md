# Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

## Project overview

A Python command-driven engine that evaluates temperature-sensitive shipments using product profiles, shipment/consignment details, transport legs, handoff records, and temperature-logger CSV files. It detects excursions and data gaps, calculates MKT, records release/quarantine/reject decisions, attributes events to responsible carriers or the 3PL, calculates carrier penalties, allocates rejected-consignment claims, and exports auditable CSV reports.

## Technology

- Python 3.10+
- Python standard library (`csv`, `datetime`, `math`, `unittest`)
- CSV input and output

## Project structure

```text
T077-PS-052/
├── docs/                 # Design and decision log
├── output/               # Generated CSV reports
├── sample_data/          # Shipment, profile, handoff and logger CSV inputs
├── src/                  # Compliance and decision engine modules
├── tests/                # Automated tests
├── run_project.py        # Runs the complete sample command pipeline
└── README.md
```

## Run the complete sample project

Open Command Prompt in this folder and run:

```bash
python run_project.py
```

The command file is `sample_data/commands.txt`. The pipeline writes:

- `output/excursions.csv`
- `output/decisions.csv`
- `output/penalties.csv`
- `output/claims.csv`
- `output/release_certificates.csv`

## Easy run on Windows

Double-click `RUN_ALL.bat` to run all automated tests first and, if they pass, execute the full sample pipeline.

## Run automated tests

```bash
python -m unittest discover tests -v
```

The current regression suite contains 41 tests.

## BR-08 claims and insurance behaviour

- Claim liability is grouped by responsible party (carrier ID or `3PL`), not duplicated by transport leg.
- The configured shipment insurance value is applied as a cumulative cap per party across all rejected consignments in that shipment. The supplied sample data sets this to ₹10,00,000.
- Excess is redistributed only to parties with positive attributed excursion minutes and remaining cap capacity.
- ## project Contributors-Mohith
- A party with zero attributed excursion minutes receives zero liability.
- If all attributable parties reach their caps, the remainder is recorded as `UNALLOCATED`; it is not assigned to an unrelated party.

`python -m src.main` starts the separate interactive single-shipment temperature-check demonstration. Use `python run_project.py` for the complete CSV command-file pipeline.





---

## Project Demo Video

Watch the complete project demonstration:

[Click here to watch T077-PS-052 – Cold-Chain Shipment Temperature Compliance and Claims Engine](https://drive.google.com/file/d/11_O_AbQyluchF7Vbet2727Vb73U8fydH/view?usp=drive_web)
