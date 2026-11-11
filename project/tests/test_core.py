"""
Unit tests for Core Cold-Chain Compliance Engine (Phase 1).

Tests excursion detection, trailing excursion handling, data gap detection,
configurable temperature profiles, upper & lower MKT validation,
and compliance decision engine evaluation.
"""

import unittest
from datetime import datetime, timedelta

from src.excursion_detector import detect_excursions, detect_data_gaps, remove_duplicates, parse_reading
from src.profiles import get_profile, register_profile, list_profiles, reset_profiles, validate_profile
from src.decision_engine import evaluate_shipment, DecisionResult
from src.mkt_calculator import calculate_mkt, validate_mkt
from src.shipment_processor import process_shipment


class TestCoreFeatures(unittest.TestCase):

    def setUp(self):
        reset_profiles()

    def tearDown(self):
        reset_profiles()

    # =========================================================================
    # 1. ORIGINAL TESTS PRESERVED
    # =========================================================================

    def test_excursion_detection(self):
        start = datetime(2026, 11, 1, 10, 0)

        readings = [
            (start, 5),
            (start + timedelta(minutes=5), 10),
            (start + timedelta(minutes=15), 7)
        ]

        result = detect_excursions(readings, 2, 8)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duration_minutes"], 10)

    def test_vaccine_profile(self):
        profile = get_profile("VACCINE_2_8")

        self.assertEqual(profile["min_temp"], 2)
        self.assertEqual(profile["max_temp"], 8)

    def test_shipment_release(self):
        profile = get_profile("VACCINE_2_8")

        readings = [
            (datetime(2026, 11, 1, 10, 0), 5)
        ]

        result = evaluate_shipment(
            excursions=[],
            readings=readings,
            profile=profile
        )

        self.assertEqual(result, "RELEASE")

    def test_mkt_calculation(self):
        result = calculate_mkt([5, 5, 5])

        self.assertAlmostEqual(result, 5, places=2)

    def test_shipment_processor(self):
        start = datetime(2026, 11, 1, 10, 0)

        readings = [
            (start, 5),
            (start + timedelta(minutes=5), 10),
            (start + timedelta(minutes=15), 7)
        ]

        result = process_shipment(
            readings,
            "VACCINE_2_8"
        )

        self.assertEqual(result["decision"], "RELEASE")
        self.assertEqual(len(result["excursions"]), 1)

        # Verify MKT using all temperature readings
        self.assertAlmostEqual(
            result["mkt"],
            7.588964040886879,
            delta=0.01
        )

    # =========================================================================
    # 2. DECISION RESULT BACKWARD COMPATIBILITY & MAPPING SUPPORT
    # =========================================================================

    def test_decision_result_backward_compatibility(self):
        """DecisionResult must work as a string, attribute holder, and dict-like object."""
        result = DecisionResult("RELEASE", reasons=["All good"], audit_trail={"total_readings": 10})

        # String equality
        self.assertEqual(result, "RELEASE")
        self.assertTrue(result == "RELEASE")
        self.assertEqual(str(result), "RELEASE")

        # Attribute access
        self.assertEqual(result.decision, "RELEASE")
        self.assertEqual(result.reasons, ["All good"])
        self.assertEqual(result.audit_trail["total_readings"], 10)
        self.assertTrue(result.is_release)
        self.assertFalse(result.is_quarantine)
        self.assertFalse(result.is_reject)

        # Mapping key access
        self.assertEqual(result["decision"], "RELEASE")
        self.assertEqual(result.get("decision"), "RELEASE")
        self.assertEqual(result["reasons"], ["All good"])
        self.assertTrue("decision" in result)
        self.assertTrue("audit_trail" in result)

        with self.assertRaises(KeyError):
            _ = result["non_existent_key"]

    # =========================================================================
    # 3. ONGOING & TRAILING EXCURSION DETECTION
    # =========================================================================

    def test_trailing_excursion_captured_at_end_of_readings(self):
        """Verify that an excursion that continues until the final reading is not dropped."""
        start = datetime(2026, 11, 1, 10, 0)

        readings = [
            (start, 5.0),
            (start + timedelta(minutes=10), 9.5),
            (start + timedelta(minutes=20), 10.0),
            (start + timedelta(minutes=30), 11.0)  # final reading, still out of spec!
        ]

        result = detect_excursions(readings, 2.0, 8.0)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duration_minutes"], 20.0)
        self.assertTrue(result[0]["ongoing"])
        self.assertEqual(result[0]["type"], "HIGH")
        self.assertEqual(result[0]["peak_temp"], 11.0)
        self.assertEqual(result[0]["reading_count"], 3)

    def test_single_reading_trailing_excursion(self):
        """A single reading excursion at the end of a series is recorded."""
        start = datetime(2026, 11, 1, 10, 0)
        readings = [
            (start, 5.0),
            (start + timedelta(minutes=10), 5.0),
            (start + timedelta(minutes=20), 12.0)  # instantaneous trailing breach
        ]

        result = detect_excursions(readings, 2.0, 8.0)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["duration_minutes"], 0.0)
        self.assertTrue(result[0]["ongoing"])
        self.assertEqual(result[0]["peak_temp"], 12.0)

    def test_low_temperature_freezing_excursion(self):
        """Verify low temperature excursions below min_temp are correctly detected."""
        start = datetime(2026, 11, 1, 8, 0)

        readings = [
            (start, 4.0),
            (start + timedelta(minutes=10), 0.5),   # below 2.0°C
            (start + timedelta(minutes=25), -1.2),  # sub-zero freezing
            (start + timedelta(minutes=40), 4.5)    # recovered
        ]

        result = detect_excursions(readings, 2.0, 8.0)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "LOW")
        self.assertEqual(result[0]["duration_minutes"], 30.0)
        self.assertAlmostEqual(result[0]["peak_temp"], -1.2)
        self.assertFalse(result[0]["ongoing"])

    def test_multiple_excursions_mixed_high_and_low(self):
        """Verify multiple excursions with both high and low spikes are tracked independently."""
        start = datetime(2026, 11, 1, 10, 0)

        readings = [
            (start, 5.0),
            (start + timedelta(minutes=10), 12.0), # High excursion starts
            (start + timedelta(minutes=20), 5.0),  # High excursion ends (10 min)
            (start + timedelta(minutes=30), 5.0),  # Compliant
            (start + timedelta(minutes=40), 1.0),  # Low excursion starts
            (start + timedelta(minutes=55), 5.0)   # Low excursion ends (15 min)
        ]

        result = detect_excursions(readings, 2.0, 8.0)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["type"], "HIGH")
        self.assertEqual(result[0]["duration_minutes"], 10.0)
        self.assertEqual(result[1]["type"], "LOW")
        self.assertEqual(result[1]["duration_minutes"], 15.0)

    # =========================================================================
    # 4. DATA GAP DETECTION & IRREGULAR / DUPLICATE TIMESTAMP HANDLING
    # =========================================================================

    def test_data_gap_detection_normal_sampling(self):
        """Regular 10-minute intervals within 15-minute tolerance produce no gaps."""
        start = datetime(2026, 11, 1, 12, 0)
        readings = [
            (start + timedelta(minutes=10 * i), 5.0)
            for i in range(5)
        ]

        gaps = detect_data_gaps(readings, max_gap_minutes=15.0)
        self.assertEqual(len(gaps), 0)

    def test_data_gap_detection_with_dropout(self):
        """A 45-minute missing interval exceeds 15-minute threshold and triggers gap alert."""
        start = datetime(2026, 11, 1, 12, 0)
        readings = [
            (start, 5.0),
            (start + timedelta(minutes=10), 5.2),
            (start + timedelta(minutes=55), 5.1),  # 45 min gap!
            (start + timedelta(minutes=65), 5.0)
        ]

        gaps = detect_data_gaps(readings, max_gap_minutes=15.0)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["duration_minutes"], 45.0)
        self.assertEqual(gaps[0]["start"], start + timedelta(minutes=10))
        self.assertEqual(gaps[0]["end"], start + timedelta(minutes=55))

    def test_data_gap_empty_and_single_reading(self):
        """Verify edge cases for gap detection with <2 readings."""
        self.assertEqual(detect_data_gaps([]), [])
        self.assertEqual(detect_data_gaps([(datetime(2026, 11, 1, 12, 0), 5.0)]), [])

    def test_data_gap_non_positive_threshold_raises_value_error(self):
        """Non-positive max_gap_minutes must raise ValueError."""
        readings = [(datetime(2026, 11, 1, 10, 0), 5.0), (datetime(2026, 11, 1, 10, 10), 5.0)]
        with self.assertRaises(ValueError):
            detect_data_gaps(readings, max_gap_minutes=0)
        with self.assertRaises(ValueError):
            detect_data_gaps(readings, max_gap_minutes=-5)

    def test_remove_duplicates_handles_out_of_order_and_duplicates(self):
        """Out of order timestamps and duplicate timestamps are sanitized correctly."""
        t1 = datetime(2026, 11, 1, 10, 0)
        t2 = datetime(2026, 11, 1, 10, 5)
        t3 = datetime(2026, 11, 1, 10, 10)

        unordered_with_dups = [
            (t2, 6.0),
            (t1, 5.0),
            (t1, 9.9),  # duplicate of t1, must be discarded
            (t3, 5.5),
            (t2, 7.7)   # duplicate of t2, must be discarded
        ]

        cleaned = remove_duplicates(unordered_with_dups)
        self.assertEqual(len(cleaned), 3)
        self.assertEqual(cleaned[0], (t1, 5.0))
        self.assertEqual(cleaned[1], (t2, 6.0))
        self.assertEqual(cleaned[2], (t3, 5.5))

    def test_parse_reading_iso_strings(self):
        """ISO formatted strings are converted into datetime objects seamlessly."""
        dt, temp = parse_reading(("2026-11-01 10:00:00", "5.5"))
        self.assertEqual(dt, datetime(2026, 11, 1, 10, 0, 0))
        self.assertEqual(temp, 5.5)

    def test_parse_reading_invalid_inputs(self):
        """Invalid readings raise clear descriptive ValueErrors."""
        with self.assertRaises(ValueError):
            parse_reading("not-a-tuple")
        with self.assertRaises(ValueError):
            parse_reading((datetime(2026, 11, 1, 10, 0), "not-a-number"))
        with self.assertRaises(ValueError):
            parse_reading(("invalid-date-string", 5.0))

    # =========================================================================
    # 5. TIME-WEIGHTED MKT AND WEIGHT VALIDATION
    # =========================================================================

    def test_mkt_upper_limit_violation(self):
        """MKT exceeding upper bound must report violation."""
        val = validate_mkt(9.2, min_mkt=2.0, max_mkt=8.0)
        self.assertFalse(val["valid"])
        self.assertEqual(val["violation"], "EXCEEDED_MAX")
        self.assertIn("exceeds maximum permitted limit", val["reason"])

    def test_mkt_lower_limit_violation(self):
        """MKT below lower bound must report violation."""
        val = validate_mkt(1.1, min_mkt=2.0, max_mkt=8.0)
        self.assertFalse(val["valid"])
        self.assertEqual(val["violation"], "SUB_MIN")
        self.assertIn("below minimum permitted limit", val["reason"])

    def test_mkt_compliant_within_bounds(self):
        """MKT within permitted bounds passes validation."""
        val = validate_mkt(5.4, min_mkt=2.0, max_mkt=8.0)
        self.assertTrue(val["valid"])
        self.assertIsNone(val["reason"])

    def test_mkt_time_weighted_calculation(self):
        """Calculate time-weighted MKT with varying interval weights."""
        temps = [5.0, 15.0]
        # 5°C for 60 minutes, 15°C for 10 minutes
        weights = [60.0, 10.0]
        mkt_weighted = calculate_mkt(temps, weights=weights)
        mkt_unweighted = calculate_mkt(temps)

        # The weighted MKT should be closer to 5°C than the unweighted MKT
        self.assertLess(mkt_weighted, mkt_unweighted)

    def test_mkt_rejects_negative_weights(self):
        """Negative weights must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_mkt([5.0, 10.0], weights=[20.0, -5.0])

    def test_mkt_rejects_zero_total_weight(self):
        """Zero total weight must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_mkt([5.0, 10.0], weights=[0.0, 0.0])

    def test_mkt_rejects_mismatched_weights_length(self):
        """Mismatched weights length must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_mkt([5.0, 10.0], weights=[10.0])

    def test_mkt_rejects_sub_absolute_zero_temperature(self):
        """Temperatures at or below absolute zero (-273.15°C) must raise ValueError."""
        with self.assertRaises(ValueError):
            calculate_mkt([-274.0])

    # =========================================================================
    # 6. CONFIGURABLE PROFILES & REGISTRY ISOLATION
    # =========================================================================

    def test_register_and_retrieve_custom_profile(self):
        """Test registering and retrieving a custom clinical trial ultra-cold profile."""
        ultra_cold = {
            "min_temp": -80.0,
            "max_temp": -60.0,
            "hard_min": -90.0,
            "hard_max": -50.0,
            "allowed_minutes": 15.0,
            "allowed_excursions": 1,
            "min_mkt": -80.0,
            "max_mkt": -60.0,
            "max_gap_minutes": 10.0,
            "allowed_gap_minutes": 20.0
        }

        register_profile("ULTRA_COLD", ultra_cold)
        self.assertIn("ULTRA_COLD", list_profiles())

        retrieved = get_profile("ULTRA_COLD")
        self.assertEqual(retrieved["min_temp"], -80.0)
        self.assertEqual(retrieved["hard_max"], -50.0)

    def test_profile_mutation_does_not_affect_registry(self):
        """Modifying a retrieved profile dictionary does not corrupt the internal registry."""
        p = get_profile("VACCINE_2_8")
        p["min_temp"] = -999.0  # Attempt in-place mutation

        re_read = get_profile("VACCINE_2_8")
        self.assertEqual(re_read["min_temp"], 2.0)

    def test_profile_reset_restores_defaults(self):
        """Calling reset_profiles restores original defaults and removes custom profiles."""
        register_profile("TEMPORARY", {
            "min_temp": 1.0, "max_temp": 5.0, "hard_min": 0.0, "hard_max": 10.0,
            "allowed_minutes": 10.0, "allowed_excursions": 1
        })
        self.assertIn("TEMPORARY", list_profiles())

        reset_profiles()
        self.assertNotIn("TEMPORARY", list_profiles())
        self.assertIn("VACCINE_2_8", list_profiles())

    def test_profile_validation_rejects_inconsistent_thresholds(self):
        """Invalid profile hierarchy (e.g. min_temp > max_temp) must raise ValueError."""
        invalid_profile = {
            "min_temp": 10.0,
            "max_temp": 5.0,  # invalid! min > max
            "hard_min": 0.0,
            "hard_max": 20.0,
            "allowed_minutes": 30.0,
            "allowed_excursions": 2
        }

        with self.assertRaises(ValueError):
            register_profile("INVALID_P", invalid_profile)

    # =========================================================================
    # 7. DECISION PRIORITY HIERARCHY & AUDIT TRAILS
    # =========================================================================

    def test_decision_priority_reject_overrides_quarantine(self):
        """When hard limits AND MKT AND data gaps occur simultaneously, REJECT takes priority."""
        profile = get_profile("VACCINE_2_8")
        start = datetime(2026, 11, 1, 10, 0)
        # 1 reading breaching hard_max (16.0°C), plus a 60-min gap
        readings = [
            (start, 5.0),
            (start + timedelta(minutes=5), 16.0), # Critical REJECT breach!
            (start + timedelta(minutes=65), 5.0)  # 60 min gap (QUARANTINE violation)
        ]

        excursions = detect_excursions(readings, profile["min_temp"], profile["max_temp"])
        data_gaps = detect_data_gaps(readings, max_gap_minutes=profile["max_gap_minutes"])

        # MKT is also intentionally elevated (QUARANTINE violation)
        result = evaluate_shipment(
            excursions=excursions,
            readings=readings,
            profile=profile,
            mkt=12.0,
            data_gaps=data_gaps
        )

        # REJECT must win over QUARANTINE
        self.assertEqual(result, "REJECT")
        self.assertTrue(result.is_reject)
        self.assertFalse(result.is_quarantine)

        # But all violations must be captured in reasons for complete auditability
        reasons_text = " ".join(result.reasons)
        self.assertIn("Critical hard temperature limit breached", reasons_text)
        self.assertIn("exceeds maximum permitted limit", reasons_text)
        self.assertIn("missing data gap duration", reasons_text)

        # Audit trail must accurately record all metrics
        self.assertTrue(result.audit_trail["hard_limit_breached"])
        self.assertFalse(result.audit_trail["mkt_valid"])
        self.assertEqual(result.audit_trail["data_gaps_count"], 1)

    def test_decision_reject_on_hard_min_limit_breach(self):
        """A temperature reading breaching hard_min (< 0.0°C for vaccine) must REJECT."""
        profile = get_profile("VACCINE_2_8")
        start = datetime(2026, 11, 1, 10, 0)
        readings = [
            (start, 4.0),
            (start + timedelta(minutes=5), -1.5),  # hard_min is 0.0°C
            (start + timedelta(minutes=10), 4.0)
        ]

        excursions = detect_excursions(readings, profile["min_temp"], profile["max_temp"])
        result = evaluate_shipment(excursions, readings, profile, mkt=3.0)

        self.assertEqual(result, "REJECT")
        self.assertTrue(result.is_reject)

    def test_decision_quarantine_on_data_gap_excess(self):
        """Shipment must be quarantined if data gaps exceed allowed tolerance."""
        profile = get_profile("VACCINE_2_8")
        start = datetime(2026, 11, 1, 10, 0)
        readings = [
            (start, 5.0),
            (start + timedelta(minutes=60), 5.0)  # 60 min gap > 30 min allowed
        ]

        data_gaps = detect_data_gaps(readings, max_gap_minutes=profile["max_gap_minutes"])
        result = evaluate_shipment(
            excursions=[],
            readings=readings,
            profile=profile,
            mkt=5.0,
            data_gaps=data_gaps
        )

        self.assertEqual(result, "QUARANTINE")
        self.assertTrue(result.is_quarantine)
        self.assertTrue(any("missing data gap duration" in r for r in result.reasons))

    def test_decision_quarantine_on_mkt_lower_bound_breach(self):
        """Shipment must be quarantined if MKT drops below lower bound."""
        profile = get_profile("VACCINE_2_8")  # min_mkt = 2.0°C
        readings = [(datetime(2026, 11, 1, 10, 0), 1.5)]

        result = evaluate_shipment(
            excursions=[],
            readings=readings,
            profile=profile,
            mkt=1.5
        )

        self.assertEqual(result, "QUARANTINE")
        self.assertTrue(any("below minimum permitted limit" in r for r in result.reasons))

    def test_decision_quarantine_on_invalid_chain_of_custody(self):
        """Shipment must be quarantined if chain of custody is not valid."""
        profile = get_profile("VACCINE_2_8")
        readings = [(datetime(2026, 11, 1, 10, 0), 5.0)]

        result = evaluate_shipment(
            excursions=[],
            readings=readings,
            profile=profile,
            mkt=5.0,
            chain_custody_valid=False
        )

        self.assertEqual(result, "QUARANTINE")
        self.assertIn("Invalid or unverified chain of custody", result.reasons[0])


if __name__ == "__main__":
    unittest.main()
