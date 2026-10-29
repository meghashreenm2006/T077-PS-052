# System Design: Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

## 1. Overview

The Cold-Chain Shipment Temperature Compliance and Claims Engine is a command-driven backend application designed to monitor temperature-sensitive shipments used in pharmaceutical and frozen-food logistics.

The system processes temperature logger readings, detects temperature excursions and data gaps, evaluates compliance with product temperature profiles, determines shipment release decisions, calculates carrier penalties, and allocates claims.

## 2. Objectives

- Define product temperature profiles with minimum and maximum permitted temperatures.
- Manage shipments, consignments, transport legs, and hand-offs.
- Process temperature logger readings.
- Detect temperature excursions and missing data.
- Calculate cumulative excursion minutes.
- Calculate Mean Kinetic Temperature (MKT).
- Determine RELEASE, QUARANTINE, or REJECT decisions.
- Calculate carrier penalties and claims.
- Generate excursion reports, release certificates, and claim settlements.

## 3. Technology Stack

- **Programming Language:** Python 3.10+
- **Testing:** Python unittest
- **Version Control:** Git and GitHub
- **Documentation:** Markdown
- **Interface:** Command-line interface (CLI)

## 4. Project Structure

```text
T077-PS-052/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── temperature.py
│   ├── compliance.py
│   ├── claims.py
│   └── reports.py
├── tests/
│   ├── __init__.py
│   ├── test_temperature.py
│   ├── test_compliance.py
│   └── test_claims.py
├── docs/
│   ├── design.md
│   └── decision-log.md
└── README.md
```

## 5. System Architecture

The application follows a modular architecture.

1. **Input Module:** Accepts product profiles, shipment details, and temperature readings.
2. **Shipment Management Module:** Maintains shipment, consignment, transport-leg, and hand-off information.
3. **Temperature Monitoring Module:** Validates readings and detects temperature excursions and data gaps.
4. **Compliance Module:** Evaluates temperature compliance and calculates cumulative excursion duration and MKT.
5. **Decision Module:** Determines whether a shipment should be released, quarantined, or rejected.
6. **Claims Module:** Calculates carrier penalties and claim amounts.
7. **Reporting Module:** Generates excursion reports, release certificates, and claim settlements.

## 6. Core Data Models

### Product Temperature Profile

Stores the permitted temperature range and compliance settings for a product.

Fields:
- `product_id`
- `product_name`
- `min_temperature`
- `max_temperature`
- `max_excursion_minutes`

### Shipment

Represents a shipment being monitored.

Fields:
- `shipment_id`
- `product_id`
- `origin`
- `destination`
- `carrier