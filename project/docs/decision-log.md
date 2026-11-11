# Decision Log: Cold-Chain Shipment Temperature Compliance and Claims Engine

**Team ID:** T077  
**Problem Statement:** PS-052

## Decision 1: Programming Language

**Decision:** Use Python 3.10 or later.  
**Reason:** Python supports modular application development, data processing, and automated testing.

## Decision 2: Application Architecture

**Decision:** Evolve from a standalone CLI into a FastAPI-backed web architecture with a responsive dashboard, while preserving the command-line interface and modular core engine.  
**Reason:** Allows both interactive browser-based cold chain logistics management and automated CLI/headless verification.

## Decision 3: Testing Framework

**Decision:** Use Python's built-in `unittest` framework.  
**Reason:** It supports automated testing across unit and integration levels without external test dependencies.

## Decision 4: Temperature Compliance

**Decision:** Compare temperature readings against configured product-specific limits.  
**Reason:** Different products (e.g. 2–8°C vaccines, -20°C frozen items, ambient supplies) require distinct operating bands and hard excursion limits.

## Decision 5: Missing Data

**Decision:** Automatically detect data gaps exceeding `max_gap_minutes` and evaluate cumulative and single gap thresholds against profile tolerances.  
**Reason:** Sensor dropouts or logger tampering must be flagged for quarantine rather than assumed compliant.

## Decision 6: Shipment Decisions

**Decision:** Support RELEASE, QUARANTINE, and REJECT outcomes with full audit trails.  
**Reason:** Regulated life-sciences logistics requires explicit, deterministic, and auditable rationale for every disposition.

## Decision 7: Claims Calculation

**Decision:** Calculate carrier penalties using documented claim rules, liability allocation per transport leg, and carrier agreements.  
**Reason:** Claim amounts should be traceable, reproducible, and contract-aligned.

## Decision 8: Automated Testing

**Decision:** Test normal conditions, boundary conditions, and invalid inputs.  
**Reason:** Automated testing ensures mathematical accuracy in MKT calculations, gap tracking, and decision logic.

## Decision 9: Trailing Excursion Detection

**Decision:** Close any ongoing excursion at the final logger timestamp if readings terminate while out of specification, marking it with an `ongoing: True` attribute.  
**Reason:** Prevents silent dropping of excursions that persist through the end of the logger data series.

## Decision 10: Two-Sided MKT Validation

**Decision:** Validate Mean Kinetic Temperature against both lower (`min_mkt`) and upper (`max_mkt`) profile boundaries.  
**Reason:** Cold-sensitive products can degrade if exposed to prolonged low temperatures even if hard freezing limits are not breached.

## Decision 11: Auditable Decision Results & Backward Compatibility

**Decision:** Implement `DecisionResult` as a string subclass inheriting from `str` while attaching `.reasons` and `.audit_trail`.  
**Reason:** Guarantees 100% backward compatibility with equality assertions (`result == "RELEASE"`) while providing structured audit trails for reports and UI dashboards.
