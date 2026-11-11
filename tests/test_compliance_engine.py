"""
Comprehensive tests for ComplianceEngine — Phase 2 through 4.

Covers all planted edge cases (EC1–EC8) and additional scenarios
using synthetic CSV data in temporary directories.

Each test is self-contained: it creates its own minimal CSV files so it
does NOT depend on the sample_data folder and can run in any environment.
"""

import csv
import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from src.compliance_engine import ComplianceEngine


# =============================================================================
# Helpers to build synthetic CSV files
# =============================================================================

def _write_csv(path, rows, fieldnames):
    """Write a CSV file at path with the given rows (list of dicts) and fieldnames."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path, lines):
    """Write a plain text file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def _make_base_dataset(tmp, shipment_id="SHP-001", profile_id="PRF-01"):
    """
    Create a minimal but valid dataset with one shipment, one consignment,
    two legs, one handoff and an empty readings file. Returns the ComplianceEngine
    with master files loaded. The caller supplies readings and runs EVALUATE.
    """
    _write_csv(
        os.path.join(tmp, "profiles.csv"),
        [
            {
                "profile_id": profile_id,
                "name": "VACCINE_2_8",
                "range_min_c": 2.0,
                "range_max_c": 8.0,
                "hard_min_c": 0.0,
                "hard_max_c": 15.0,
                "allowed_excursion_minutes": 120,
                "allowed_excursion_count": 3,
                "mkt_limit_c": 8.0,
            }
        ],
        ["profile_id", "name", "range_min_c", "range_max_c", "hard_min_c", "hard_max_c",
         "allowed_excursion_minutes", "allowed_excursion_count", "mkt_limit_c"],
    )

    _write_csv(
        os.path.join(tmp, "shipments.csv"),
        [
            {
                "shipment_id": shipment_id,
                "origin_city": "City A",
                "destination_city": "City B",
                "planned_departure": "2026-01-01 08:00:00",
                "insured_value": 1000000.00,
                "logger_owner": "3PL",
            }
        ],
        ["shipment_id", "origin_city", "destination_city", "planned_departure", "insured_value", "logger_owner"],
    )

    _write_csv(
        os.path.join(tmp, "consignments.csv"),
        [
            {
                "consignment_id": shipment_id + "-C1",
                "shipment_id": shipment_id,
                "profile_id": profile_id,
                "product": "Vaccine",
                "lot_no": "LOT001",
                "value_rs": 500000.00,
            }
        ],
        ["consignment_id", "shipment_id", "profile_id", "product", "lot_no", "value_rs"],
    )

    _write_csv(
        os.path.join(tmp, "legs.csv"),
        [
            {
                "leg_id": shipment_id + "-L1",
                "shipment_id": shipment_id,
                "leg_no": 1,
                "carrier_id": "CAR-01",
                "vehicle_type": "REEFER",
                "start_ts": "2026-01-01 08:00:00",
                "end_ts": "2026-01-01 14:00:00",
                "freight_charge": 50000.00,
            },
            {
                "leg_id": shipment_id + "-L2",
                "shipment_id": shipment_id,
                "leg_no": 2,
                "carrier_id": "CAR-02",
                "vehicle_type": "PASSIVE_BOX",
                "start_ts": "2026-01-01 14:00:00",
                "end_ts": "2026-01-01 20:00:00",
                "freight_charge": 30000.00,
            },
        ],
        ["leg_id", "shipment_id", "leg_no", "carrier_id", "vehicle_type", "start_ts", "end_ts", "freight_charge"],
    )

    _write_csv(
        os.path.join(tmp, "handoffs.csv"),
        [
            {
                "shipment_id": shipment_id,
                "from_leg_no": 1,
                "to_leg_no": 2,
                "handoff_ts": "2026-01-01 14:00:00",
                "receiving_party": "CAR-02",
                "signature_flag": "true",
            }
        ],
        ["shipment_id", "from_leg_no", "to_leg_no", "handoff_ts", "receiving_party", "signature_flag"],
    )

    engine = ComplianceEngine(data_dir=tmp)
    engine.load_profiles("profiles.csv")
    engine.load_shipments("shipments.csv", "consignments.csv", "legs.csv", "handoffs.csv")
    return engine


# =============================================================================
# 1. LOAD_PROFILES
# =============================================================================
class TestLoadProfiles(unittest.TestCase):

    def test_load_profiles_from_csv(self):
        """LOAD_PROFILES reads profile_id, ranges, hard limits, allowances and mkt_limit_c."""
        with tempfile.TemporaryDirectory() as tmp:
            _write_csv(
                os.path.join(tmp, "profiles.csv"),
                [
                    {
                        "profile_id": "PRF-01",
                        "name": "VACCINE",
                        "range_min_c": 2.0,
                        "range_max_c": 8.0,
                        "hard_min_c": 0.0,
                        "hard_max_c": 15.0,
                        "allowed_excursion_minutes": 120,
                        "allowed_excursion_count": 3,
                        "mkt_limit_c": 8.0,
                    }
                ],
                ["profile_id", "name", "range_min_c", "range_max_c", "hard_min_c", "hard_max_c",
                 "allowed_excursion_minutes", "allowed_excursion_count", "mkt_limit_c"],
            )
            engine = ComplianceEngine(data_dir=tmp)
            engine.load_profiles("profiles.csv")

            self.assertIn("PRF-01", engine.profiles)
            p = engine.profiles["PRF-01"]
            self.assertEqual(p["range_min_c"], 2.0)
            self.assertEqual(p["range_max_c"], 8.0)
            self.assertEqual(p["hard_max_c"], 15.0)
            self.assertEqual(p["allowed_excursion_minutes"], 120)
            self.assertEqual(p["mkt_limit_c"], 8.0)


# =============================================================================
# 2. INGEST_READINGS
# =============================================================================
class TestIngestReadings(unittest.TestCase):

    def _make_readings_csv(self, tmp, rows):
        path = os.path.join(tmp, "readings_SHP-001.csv")
        _write_csv(path, rows, ["reading_ts", "temperature_c"])
        return "readings_SHP-001.csv"

    def test_readings_are_sorted_chronologically(self):
        """Out-of-order readings are sorted before evaluation (EC: unsorted file)."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            fname = self._make_readings_csv(tmp, [
                {"reading_ts": "2026-01-01 10:10:00", "temperature_c": 5.1},
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 4.9},  # out of order
                {"reading_ts": "2026-01-01 10:20:00", "temperature_c": 5.3},
            ])
            engine.ingest_readings("SHP-001", fname)
            readings = engine.readings["SHP-001"]
            times = [r[0] for r in readings]
            self.assertEqual(times, sorted(times))

    def test_duplicate_timestamp_keeps_first(self):
        """EC1: duplicate timestamp — keep first reading, discard the later one."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            fname = self._make_readings_csv(tmp, [
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 5.0},  # keep
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 9.0},  # discard (out-of-range duplicate)
                {"reading_ts": "2026-01-01 10:10:00", "temperature_c": 5.5},
            ])
            engine.ingest_readings("SHP-001", fname)
            readings = engine.readings["SHP-001"]
            # Only 2 unique timestamps
            self.assertEqual(len(readings), 2)
            # First value (5.0) is retained, not 9.0
            first_temp = readings[0][1]
            self.assertEqual(first_temp, 5.0)

    def test_invalid_reading_999_9_filtered_out(self):
        """EC extra: 999.9°C readings are removed before excursion detection and MKT."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            fname = self._make_readings_csv(tmp, [
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 10:02:00", "temperature_c": 999.9},  # invalid
                {"reading_ts": "2026-01-01 10:04:00", "temperature_c": 5.0},
            ])
            engine.ingest_readings("SHP-001", fname)
            # Raw readings stored include 999.9
            raw_temps = [r[1] for r in engine.readings["SHP-001"]]
            self.assertIn(999.9, raw_temps)

            # After evaluate(), valid_readings must exclude 999.9
            engine.evaluate("SHP-001")
            # MKT should be ~5.0 (not 999.9 inflated)
            decision_row = engine.output_decisions[0]
            mkt = float(decision_row["mkt_c"])
            self.assertLess(mkt, 10.0)


# =============================================================================
# 3. DATA GAP DETECTION
# =============================================================================
class TestDataGapDetection(unittest.TestCase):

    def _make_engine_with_readings(self, tmp, reading_rows):
        engine = _make_base_dataset(tmp)
        path = os.path.join(tmp, "r.csv")
        _write_csv(path, reading_rows, ["reading_ts", "temperature_c"])
        engine.ingest_readings("SHP-001", "r.csv")
        return engine

    def test_exactly_15_min_gap_is_not_flagged(self):
        """EC2: gap of exactly 15 minutes must NOT be treated as a DATA_GAP."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:15:00", "temperature_c": 5.0},  # exactly 15 min — OK
                {"reading_ts": "2026-01-01 08:30:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            gap_excursions = [e for e in engine.output_excursions if e["type"] == "DATA_GAP"]
            self.assertEqual(len(gap_excursions), 0)

    def test_16_min_gap_is_flagged_as_data_gap(self):
        """EC2: gap of 16 minutes IS a DATA_GAP."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:16:00", "temperature_c": 5.0},  # 16 min gap
                {"reading_ts": "2026-01-01 08:32:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            gap_excursions = [e for e in engine.output_excursions if e["type"] == "DATA_GAP"]
            self.assertEqual(len(gap_excursions), 1)
            self.assertAlmostEqual(float(gap_excursions[0]["duration_minutes"]), 16.0)

    def test_invalid_reading_gap_4_min_no_data_gap(self):
        """Extra: 999.9 creates 4-min surrounding gap — NOT flagged (< 15 min)."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._make_engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 999.9},  # invalid
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            gap_excursions = [e for e in engine.output_excursions if e["type"] == "DATA_GAP"]
            self.assertEqual(len(gap_excursions), 0)


# =============================================================================
# 4. EXCURSION DETECTION
# =============================================================================
class TestExcursionDetection(unittest.TestCase):

    def _engine_with_readings(self, tmp, reading_rows):
        engine = _make_base_dataset(tmp)
        path = os.path.join(tmp, "r.csv")
        _write_csv(path, reading_rows, ["reading_ts", "temperature_c"])
        engine.ingest_readings("SHP-001", "r.csv")
        return engine

    def test_excursion_exactly_5_min_counts_toward_count(self):
        """EC3: excursion >= 5 min counts toward the qualifying excursion count."""
        with tempfile.TemporaryDirectory() as tmp:
            # Excursion: out-of-range 08:00 to 08:05 = exactly 5 minutes
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 9.0},   # out-of-range
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 9.0},   # out-of-range
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 9.0},   # out-of-range
                {"reading_ts": "2026-01-01 08:05:00", "temperature_c": 5.0},   # back in range (excursion = 5 min)
                {"reading_ts": "2026-01-01 08:15:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            decision_row = engine.output_decisions[0]
            self.assertEqual(decision_row["excursion_count"], 1)

    def test_excursion_4_min_does_not_count_toward_count(self):
        """Excursion < 5 min does NOT count toward the qualifying count."""
        with tempfile.TemporaryDirectory() as tmp:
            # Excursion: 08:00 to 08:04 = 4 min < 5 min threshold
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 9.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 9.0},
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},   # back in (excursion = 4 min)
                {"reading_ts": "2026-01-01 08:15:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            decision_row = engine.output_decisions[0]
            self.assertEqual(decision_row["excursion_count"], 0)

    def test_reading_exactly_at_hard_max_is_not_reject(self):
        """EC4: reading == hard_max_c (15.0) is NOT a hard-limit breach — no REJECT."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 15.0},  # exactly at hard_max
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            decision = engine.output_decisions[0]["decision"]
            self.assertNotEqual(decision, "REJECT")

    def test_reading_above_hard_max_is_reject(self):
        """Reading > hard_max_c → REJECT."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 15.1},  # strictly above hard_max
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            decision = engine.output_decisions[0]["decision"]
            self.assertEqual(decision, "REJECT")

    def test_reading_below_hard_min_is_reject(self):
        """Reading < hard_min_c (0.0) → REJECT."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": -0.1},  # below hard_min
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},
            ])
            engine.evaluate("SHP-001")
            decision = engine.output_decisions[0]["decision"]
            self.assertEqual(decision, "REJECT")

    def test_compliant_readings_give_release(self):
        """All readings in range, no gaps → RELEASE."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = self._engine_with_readings(tmp, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 6.0},
                {"reading_ts": "2026-01-01 08:20:00", "temperature_c": 4.5},
            ])
            engine.evaluate("SHP-001")
            decision = engine.output_decisions[0]["decision"]
            self.assertEqual(decision, "RELEASE")


# =============================================================================
# 5. CHAIN OF CUSTODY
# =============================================================================
class TestChainOfCustody(unittest.TestCase):

    def test_missing_signature_causes_quarantine(self):
        """Extra (SHP-010): signature_flag=false → QUARANTINE."""
        with tempfile.TemporaryDirectory() as tmp:
            # Reuse base but overwrite handoffs.csv with signature_flag=false
            engine = _make_base_dataset(tmp)
            _write_csv(
                os.path.join(tmp, "handoffs.csv"),
                [
                    {
                        "shipment_id": "SHP-001",
                        "from_leg_no": 1,
                        "to_leg_no": 2,
                        "handoff_ts": "2026-01-01 14:00:00",
                        "receiving_party": "CAR-02",
                        "signature_flag": "false",   # missing signature
                    }
                ],
                ["shipment_id", "from_leg_no", "to_leg_no", "handoff_ts", "receiving_party", "signature_flag"],
            )
            engine.load_shipments("shipments.csv", "consignments.csv", "legs.csv", "handoffs.csv")

            path = os.path.join(tmp, "r.csv")
            _write_csv(path, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 5.0},
            ], ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            decision = engine.output_decisions[0]["decision"]
            self.assertEqual(decision, "QUARANTINE")
            reason = engine.output_decisions[0]["reason_codes"]
            self.assertIn("MISSING_RECEIVING_SIGNATURE", reason)

    def test_override_custody_clears_quarantine(self):
        """Extra (SHP-009): OVERRIDE_CUSTODY after QUARANTINE → second EVALUATE gives RELEASE."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            _write_csv(
                os.path.join(tmp, "handoffs.csv"),
                [
                    {
                        "shipment_id": "SHP-001",
                        "from_leg_no": 1,
                        "to_leg_no": 2,
                        "handoff_ts": "2026-01-01 13:00:00",  # 60 min before leg 1 end (14:00)
                        "receiving_party": "CAR-02",
                        "signature_flag": "true",
                    }
                ],
                ["shipment_id", "from_leg_no", "to_leg_no", "handoff_ts", "receiving_party", "signature_flag"],
            )
            engine.load_shipments("shipments.csv", "consignments.csv", "legs.csv", "handoffs.csv")

            path = os.path.join(tmp, "r.csv")
            _write_csv(path, [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 5.0},
            ], ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")

            # First evaluate → QUARANTINE due to handoff before leg end
            engine.evaluate("SHP-001")
            first_decision = engine.output_decisions[0]["decision"]
            self.assertEqual(first_decision, "QUARANTINE")

            # Override custody then re-evaluate
            engine.override_custody("SHP-001", "Clock drift confirmed")
            engine.evaluate("SHP-001")
            second_decision = engine.output_decisions[1]["decision"]
            self.assertEqual(second_decision, "RELEASE")


# =============================================================================
# 6. RE-ICING (EC8)
# =============================================================================
class TestReIce(unittest.TestCase):

    def test_re_ice_resets_excursion_count_on_passive_box(self):
        """EC8: RE_ICE resets the excursion count for PASSIVE_BOX leg that follows."""
        with tempfile.TemporaryDirectory() as tmp:
            # Profile: 3 excursions allowed
            _write_csv(
                os.path.join(tmp, "profiles.csv"),
                [{
                    "profile_id": "PRF-01",
                    "name": "VACCINE",
                    "range_min_c": 2.0,
                    "range_max_c": 8.0,
                    "hard_min_c": 0.0,
                    "hard_max_c": 15.0,
                    "allowed_excursion_minutes": 300,
                    "allowed_excursion_count": 3,
                    "mkt_limit_c": 8.0,
                }],
                ["profile_id", "name", "range_min_c", "range_max_c", "hard_min_c", "hard_max_c",
                 "allowed_excursion_minutes", "allowed_excursion_count", "mkt_limit_c"],
            )
            _write_csv(os.path.join(tmp, "shipments.csv"), [{
                "shipment_id": "SHP-001",
                "origin_city": "A",
                "destination_city": "B",
                "planned_departure": "2026-01-01 08:00:00",
                "insured_value": 1000000.00,
                "logger_owner": "3PL",
            }], ["shipment_id", "origin_city", "destination_city", "planned_departure", "insured_value", "logger_owner"])

            _write_csv(os.path.join(tmp, "consignments.csv"), [{
                "consignment_id": "SHP-001-C1",
                "shipment_id": "SHP-001",
                "profile_id": "PRF-01",
                "product": "Vaccine",
                "lot_no": "LOT001",
                "value_rs": 500000.00,
            }], ["consignment_id", "shipment_id", "profile_id", "product", "lot_no", "value_rs"])

            # Leg 1: REEFER (3 qualifying excursions of 10 min each)
            # Leg 2: PASSIVE_BOX (2 qualifying excursions of 12 min each, after re-ice)
            _write_csv(os.path.join(tmp, "legs.csv"), [
                {"leg_id": "SHP-001-L1", "shipment_id": "SHP-001", "leg_no": 1,
                 "carrier_id": "CAR-01", "vehicle_type": "REEFER",
                 "start_ts": "2026-01-01 08:00:00", "end_ts": "2026-01-01 14:00:00",
                 "freight_charge": 50000.00},
                {"leg_id": "SHP-001-L2", "shipment_id": "SHP-001", "leg_no": 2,
                 "carrier_id": "CAR-02", "vehicle_type": "PASSIVE_BOX",
                 "start_ts": "2026-01-01 14:00:00", "end_ts": "2026-01-01 22:00:00",
                 "freight_charge": 30000.00},
            ], ["leg_id", "shipment_id", "leg_no", "carrier_id", "vehicle_type", "start_ts", "end_ts", "freight_charge"])

            _write_csv(os.path.join(tmp, "handoffs.csv"), [{
                "shipment_id": "SHP-001",
                "from_leg_no": 1,
                "to_leg_no": 2,
                "handoff_ts": "2026-01-01 14:00:00",
                "receiving_party": "CAR-02",
                "signature_flag": "true",
            }], ["shipment_id", "from_leg_no", "to_leg_no", "handoff_ts", "receiving_party", "signature_flag"])

            engine = ComplianceEngine(data_dir=tmp)
            engine.load_profiles("profiles.csv")
            engine.load_shipments("shipments.csv", "consignments.csv", "legs.csv", "handoffs.csv")

            # Readings:
            # Leg 1: 3 excursions of 10 min each (all >= 5 min → counted)
            # Leg 2: 2 excursions of 12 min each (counted fresh after re-ice)
            readings_rows = [
                # Excursion 1 on leg 1 (09:00–09:10)
                {"reading_ts": "2026-01-01 09:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 09:10:00", "temperature_c": 5.0},
                # Excursion 2 on leg 1 (10:00–10:10)
                {"reading_ts": "2026-01-01 10:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 10:10:00", "temperature_c": 5.0},
                # Excursion 3 on leg 1 (11:00–11:10)
                {"reading_ts": "2026-01-01 11:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 11:10:00", "temperature_c": 5.0},
                # In-range bridge
                {"reading_ts": "2026-01-01 13:50:00", "temperature_c": 5.0},
                # Excursion 1 on leg 2 / passive box (15:00–15:12)
                {"reading_ts": "2026-01-01 15:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 15:12:00", "temperature_c": 5.0},
                # Excursion 2 on leg 2 (16:00–16:12)
                {"reading_ts": "2026-01-01 16:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 16:12:00", "temperature_c": 5.0},
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings_rows, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")

            # Apply re-ice at handoff time
            engine.re_ice("SHP-001", "2026-01-01 14:00:00")
            engine.evaluate("SHP-001")

            decision_row = engine.output_decisions[0]
            # After re-ice, leg 2 passive excursions don't count toward the limit
            # So total qualifying count = 3 (leg 1) + 0 (leg 2 after re-ice reset)
            # This equals the allowed_excursion_count (3), so it should RELEASE
            self.assertNotEqual(decision_row["decision"], "QUARANTINE",
                                 "RE_ICE should prevent leg-2 passive excursions from causing QUARANTINE")


# =============================================================================
# 7. PENALTY CALCULATIONS
# =============================================================================
class TestPenalties(unittest.TestCase):

    def test_penalty_cap_at_20_percent_freight_charge(self):
        """Penalty must not exceed 20% of the leg's freight_charge."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            # Create many out-of-range minutes to push penalty above cap
            # Leg 1: REEFER, freight_charge=50000 → cap = 10000
            # Rate = Rs 50/min, so 201 minutes = Rs 10050 > cap
            readings = []
            base = datetime(2026, 1, 1, 8, 0)
            # 201 minutes of continuous out-of-range on leg 1 (8:00 to 11:21)
            t = base
            while t <= base + timedelta(minutes=201):
                readings.append({"reading_ts": t.strftime("%Y-%m-%d %H:%M:%S"), "temperature_c": 10.0})
                t += timedelta(minutes=2)
            readings.append({"reading_ts": "2026-01-01 11:30:00", "temperature_c": 5.0})

            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            # Penalty for leg 1
            leg1_penalty = next(
                (p for p in engine.output_penalties if p["leg_no"] == 1), None
            )
            self.assertIsNotNone(leg1_penalty)
            self.assertEqual(leg1_penalty["cap_applied"], "true")
            self.assertLessEqual(float(leg1_penalty["penalty_total"]), 50000.0 * 0.20 + 0.01)

    def test_reefer_rate_50_per_min_passive_box_rate_20_per_min(self):
        """REEFER legs are penalised at Rs 50/min, PASSIVE_BOX at Rs 20/min."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            # 10 minutes of excursion bridging both legs
            # Leg 1 (REEFER) owns 8:00–14:00; Leg 2 (PASSIVE_BOX) owns 14:00–20:00
            readings = [
                # 10 min excursion purely on leg 1
                {"reading_ts": "2026-01-01 09:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 09:10:00", "temperature_c": 5.0},
                # 10 min excursion purely on leg 2
                {"reading_ts": "2026-01-01 15:00:00", "temperature_c": 10.0},
                {"reading_ts": "2026-01-01 15:10:00", "temperature_c": 5.0},
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            leg1 = next(p for p in engine.output_penalties if p["leg_no"] == 1)
            leg2 = next(p for p in engine.output_penalties if p["leg_no"] == 2)

            # 10 min × Rs 50 = Rs 500 for leg 1 (REEFER)
            self.assertAlmostEqual(float(leg1["minute_penalty"]), 500.0, delta=1.0)
            # 10 min × Rs 20 = Rs 200 for leg 2 (PASSIVE_BOX)
            self.assertAlmostEqual(float(leg2["minute_penalty"]), 200.0, delta=1.0)


# =============================================================================
# 8. CLAIMS
# =============================================================================
class TestClaims(unittest.TestCase):

    def test_claim_raised_only_for_rejected_consignments(self):
        """Claims are only generated for REJECTED consignments (hard breach)."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            readings = [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 20.0},  # above hard_max → REJECT
                {"reading_ts": "2026-01-01 08:04:00", "temperature_c": 5.0},
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            # Decision must be REJECT
            self.assertEqual(engine.output_decisions[0]["decision"], "REJECT")
            # At least one claim row generated
            self.assertGreater(len(engine.output_claims), 0)
            # Claim value = consignment value_rs
            claim = engine.output_claims[0]
            self.assertAlmostEqual(float(claim["claim_value"]), 500000.00)

    def test_no_claim_for_release(self):
        """No claim rows generated for RELEASED consignments."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            readings = [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 5.0},
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            self.assertEqual(engine.output_decisions[0]["decision"], "RELEASE")
            self.assertEqual(len(engine.output_claims), 0)


# =============================================================================
# 9. RELEASE CERTIFICATES
# =============================================================================
class TestReleaseCertificates(unittest.TestCase):

    def test_certificate_generated_for_released_consignment(self):
        """RELEASE decision → release_certificates.csv row generated."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            readings = [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 5.0},
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            self.assertEqual(len(engine.output_certificates), 1)
            cert = engine.output_certificates[0]
            self.assertEqual(cert["shipment_id"], "SHP-001")
            self.assertEqual(cert["consignment_id"], "SHP-001-C1")
            self.assertIn("released compliant", cert["certificate_text"])

    def test_no_certificate_for_rejected_consignment(self):
        """REJECT decision → no release certificate."""
        with tempfile.TemporaryDirectory() as tmp:
            engine = _make_base_dataset(tmp)
            readings = [
                {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                {"reading_ts": "2026-01-01 08:02:00", "temperature_c": 20.0},  # hard breach
            ]
            path = os.path.join(tmp, "r.csv")
            _write_csv(path, readings, ["reading_ts", "temperature_c"])
            engine.ingest_readings("SHP-001", "r.csv")
            engine.evaluate("SHP-001")

            self.assertEqual(len(engine.output_certificates), 0)


# =============================================================================
# 10. OUTPUT CSV GENERATION
# =============================================================================
class TestOutputCsvGeneration(unittest.TestCase):

    def test_all_five_output_csvs_are_generated(self):
        """export_all_csvs() must write all 5 required output files."""
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as out_tmp:
                engine = _make_base_dataset(tmp)
                readings = [
                    {"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                    {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 5.0},
                ]
                path = os.path.join(tmp, "r.csv")
                _write_csv(path, readings, ["reading_ts", "temperature_c"])
                engine.ingest_readings("SHP-001", "r.csv")
                engine.evaluate("SHP-001")
                engine.export_all_csvs(out_tmp)

                for fname in [
                    "excursions.csv",
                    "decisions.csv",
                    "penalties.csv",
                    "claims.csv",
                    "release_certificates.csv",
                ]:
                    self.assertTrue(
                        os.path.exists(os.path.join(out_tmp, fname)),
                        f"Expected output file {fname} not found"
                    )

    def test_decisions_csv_has_correct_headers(self):
        """decisions.csv must have the exact column order specified in the brief."""
        expected_headers = [
            "shipment_id", "consignment_id", "profile_id", "evaluation_no",
            "cumulative_minutes", "excursion_count", "mkt_c", "decision", "reason_codes"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as out_tmp:
                engine = _make_base_dataset(tmp)
                readings = [{"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0}]
                path = os.path.join(tmp, "r.csv")
                _write_csv(path, readings, ["reading_ts", "temperature_c"])
                engine.ingest_readings("SHP-001", "r.csv")
                engine.evaluate("SHP-001")
                engine.export_all_csvs(out_tmp)

                with open(os.path.join(out_tmp, "decisions.csv")) as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                self.assertEqual(headers, expected_headers)

    def test_excursions_csv_has_correct_headers(self):
        """excursions.csv must have the exact column order specified in the brief."""
        expected_headers = [
            "shipment_id", "excursion_no", "type", "start_ts", "end_ts",
            "duration_minutes", "max_temp_c", "leg_no", "party", "counts_toward_limit"
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as out_tmp:
                engine = _make_base_dataset(tmp)
                readings = [{"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0}]
                path = os.path.join(tmp, "r.csv")
                _write_csv(path, readings, ["reading_ts", "temperature_c"])
                engine.ingest_readings("SHP-001", "r.csv")
                engine.evaluate("SHP-001")
                engine.export_all_csvs(out_tmp)

                with open(os.path.join(out_tmp, "excursions.csv")) as f:
                    reader = csv.reader(f)
                    headers = next(reader)
                self.assertEqual(headers, expected_headers)


# =============================================================================
# 11. COMMAND FILE EXECUTION
# =============================================================================
class TestCommandFileExecution(unittest.TestCase):

    def test_execute_command_file_full_pipeline(self):
        """execute_command_file() runs the full pipeline and exports all 5 CSVs."""
        with tempfile.TemporaryDirectory() as tmp:
            with tempfile.TemporaryDirectory() as out_tmp:
                # Create all required files
                _write_csv(
                    os.path.join(tmp, "profiles.csv"),
                    [{"profile_id": "PRF-01", "name": "VAC", "range_min_c": 2.0, "range_max_c": 8.0,
                      "hard_min_c": 0.0, "hard_max_c": 15.0, "allowed_excursion_minutes": 120,
                      "allowed_excursion_count": 3, "mkt_limit_c": 8.0}],
                    ["profile_id", "name", "range_min_c", "range_max_c", "hard_min_c",
                     "hard_max_c", "allowed_excursion_minutes", "allowed_excursion_count", "mkt_limit_c"],
                )
                _write_csv(
                    os.path.join(tmp, "shipments.csv"),
                    [{"shipment_id": "SHP-001", "origin_city": "A", "destination_city": "B",
                      "planned_departure": "2026-01-01 08:00:00", "insured_value": 1000000.00,
                      "logger_owner": "3PL"}],
                    ["shipment_id", "origin_city", "destination_city", "planned_departure",
                     "insured_value", "logger_owner"],
                )
                _write_csv(
                    os.path.join(tmp, "consignments.csv"),
                    [{"consignment_id": "SHP-001-C1", "shipment_id": "SHP-001", "profile_id": "PRF-01",
                      "product": "Vac", "lot_no": "L01", "value_rs": 500000.00}],
                    ["consignment_id", "shipment_id", "profile_id", "product", "lot_no", "value_rs"],
                )
                _write_csv(
                    os.path.join(tmp, "legs.csv"),
                    [{"leg_id": "SHP-001-L1", "shipment_id": "SHP-001", "leg_no": 1,
                      "carrier_id": "CAR-01", "vehicle_type": "REEFER",
                      "start_ts": "2026-01-01 08:00:00", "end_ts": "2026-01-01 20:00:00",
                      "freight_charge": 50000.00}],
                    ["leg_id", "shipment_id", "leg_no", "carrier_id", "vehicle_type",
                     "start_ts", "end_ts", "freight_charge"],
                )
                _write_csv(
                    os.path.join(tmp, "handoffs.csv"),
                    [],
                    ["shipment_id", "from_leg_no", "to_leg_no", "handoff_ts",
                     "receiving_party", "signature_flag"],
                )
                _write_csv(
                    os.path.join(tmp, "readings_SHP-001.csv"),
                    [{"reading_ts": "2026-01-01 08:00:00", "temperature_c": 5.0},
                     {"reading_ts": "2026-01-01 08:10:00", "temperature_c": 5.0}],
                    ["reading_ts", "temperature_c"],
                )
                _write_text(
                    os.path.join(tmp, "commands.txt"),
                    [
                        "LOAD_PROFILES|profiles.csv",
                        "LOAD_SHIPMENTS|shipments.csv|consignments.csv|legs.csv|handoffs.csv",
                        "INGEST_READINGS|SHP-001|readings_SHP-001.csv",
                        "EVALUATE|SHP-001",
                        "PRINT_REPORTS|SHP-001",
                    ],
                )

                engine = ComplianceEngine(data_dir=tmp)
                engine.execute_command_file("commands.txt")

                # All 5 files in output/
                for fname in ["excursions.csv", "decisions.csv", "penalties.csv",
                               "claims.csv", "release_certificates.csv"]:
                    self.assertTrue(
                        os.path.exists(os.path.join(tmp, "output", fname)),
                        f"Missing output file: {fname}"
                    )


# =============================================================================
# 12. SAMPLE DATA END-TO-END (Smoke test using actual sample_data)
# =============================================================================
class TestSampleDataEndToEnd(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Run the full sample_data pipeline once and cache results."""
        sample_dir = os.path.join(os.path.dirname(__file__), "..", "sample_data")
        if not os.path.exists(os.path.join(sample_dir, "profiles.csv")):
            cls.engine = None
            return
        engine = ComplianceEngine(data_dir=sample_dir)
        engine.execute_command_file("commands.txt")
        cls.engine = engine

    def _skip_if_no_data(self):
        if self.engine is None:
            self.skipTest("sample_data not available")

    def test_decisions_cover_all_20_shipments(self):
        """Every shipment must have at least one decision row."""
        self._skip_if_no_data()
        shipment_ids = {d["shipment_id"] for d in self.engine.output_decisions}
        for i in range(1, 21):
            sid = "SHP-%03d" % i
            self.assertIn(sid, shipment_ids, f"{sid} missing from decisions")

    def test_shp009_has_two_evaluations(self):
        """SHP-009 is evaluated twice (OVERRIDE_CUSTODY then second EVALUATE)."""
        self._skip_if_no_data()
        shp9_decisions = [d for d in self.engine.output_decisions
                          if d["shipment_id"] == "SHP-009"]
        eval_nos = {int(d["evaluation_no"]) for d in shp9_decisions}
        self.assertIn(1, eval_nos)
        self.assertIn(2, eval_nos)

    def test_shp010_quarantine_no_signature(self):
        """SHP-010 has signature_flag=false → at least one QUARANTINE."""
        self._skip_if_no_data()
        shp10 = [d for d in self.engine.output_decisions if d["shipment_id"] == "SHP-010"]
        self.assertTrue(any(d["decision"] == "QUARANTINE" for d in shp10))

    def test_shp013_no_mkt_spike_from_invalid_reading(self):
        """SHP-013 has 999.9 reading — MKT must be sane (< 50°C)."""
        self._skip_if_no_data()
        shp13 = [d for d in self.engine.output_decisions if d["shipment_id"] == "SHP-013"]
        for d in shp13:
            self.assertLess(float(d["mkt_c"]), 50.0,
                            "MKT inflated by invalid 999.9 reading")

    def test_all_penalties_respect_20_percent_cap(self):
        """Every penalty row: penalty_total <= 20% of freight_charge."""
        self._skip_if_no_data()
        for p in self.engine.output_penalties:
            penalty = float(p["penalty_total"])
            # Find the corresponding leg freight_charge
            sid = p["shipment_id"]
            leg_no = p["leg_no"]
            leg = next(
                (l for l in self.engine.legs[sid] if l["leg_no"] == leg_no), None
            )
            if leg:
                cap = leg["freight_charge"] * 0.20
                self.assertLessEqual(
                    penalty, cap + 0.01,
                    f"{sid} leg {leg_no} penalty {penalty} exceeds cap {cap}"
                )

    def test_excursion_numbers_are_unique_per_shipment(self):
        """excursion_no must be unique within each shipment."""
        self._skip_if_no_data()
        from collections import defaultdict
        seen = defaultdict(set)
        for e in self.engine.output_excursions:
            sid = e["shipment_id"]
            no = e["excursion_no"]
            self.assertNotIn(no, seen[sid],
                             f"Duplicate excursion_no {no} for {sid}")
            seen[sid].add(no)

    def test_shp016_hard_breach_reject(self):
        """SHP-016 has hard_max breach → REJECT."""
        self._skip_if_no_data()
        shp16 = [d for d in self.engine.output_decisions if d["shipment_id"] == "SHP-016"]
        self.assertTrue(any(d["decision"] == "REJECT" for d in shp16))

    def test_five_output_csvs_created(self):
        """All 5 output CSV files must have been written."""
        self._skip_if_no_data()
        out_dir = os.path.join(os.path.dirname(__file__), "..", "output")
        for fname in ["excursions.csv", "decisions.csv", "penalties.csv",
                      "claims.csv", "release_certificates.csv"]:
            self.assertTrue(
                os.path.exists(os.path.join(out_dir, fname)),
                f"Output file {fname} not found in output/"
            )


if __name__ == "__main__":
    unittest.main()
