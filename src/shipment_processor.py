"""
Shipment Processor.

Coordinates temperature logger data ingestion, excursion detection,
data gap detection, MKT calculation, and compliance evaluation.
"""

from src.excursion_detector import detect_excursions, detect_data_gaps, remove_duplicates
from src.profiles import get_profile
from src.decision_engine import evaluate_shipment
from src.mkt_calculator import calculate_mkt


def process_shipment(readings, profile_name, chain_custody_valid=True):
    """
    Process temperature readings for one shipment and return its
    compliance evaluation, detected excursions, data gaps, and audit trail.
    """
    profile = get_profile(profile_name)

    # Clean readings
    cleaned_readings = remove_duplicates(readings)

    # Detect excursions
    excursions = detect_excursions(
        cleaned_readings,
        profile["min_temp"],
        profile["max_temp"]
    )

    # Detect data gaps
    max_gap = profile.get("max_gap_minutes", 15.0)
    data_gaps = detect_data_gaps(cleaned_readings, max_gap_minutes=max_gap)

    # Extract temperatures for MKT calculation
    temperatures = [
        temperature for _, temperature in cleaned_readings
    ]

    mkt = calculate_mkt(temperatures) if temperatures else None

    # Evaluate compliance
    decision_result = evaluate_shipment(
        excursions=excursions,
        readings=cleaned_readings,
        profile=profile,
        mkt=mkt,
        chain_custody_valid=chain_custody_valid,
        data_gaps=data_gaps
    )

    return {
        "excursions": excursions,
        "data_gaps": data_gaps,
        "mkt": mkt,
        "decision": decision_result.decision,
        "reasons": decision_result.reasons,
        "audit_trail": decision_result.audit_trail
    }
