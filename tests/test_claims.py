"""Regression tests for BR-08 claim allocation and insurance caps."""
import os
import tempfile
import unittest

from src.compliance_engine import ComplianceEngine


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestClaimsAllocation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = ComplianceEngine(data_dir=os.path.join(PROJECT_ROOT, "sample_data"))
        cls.engine.execute_command_file(os.path.join(PROJECT_ROOT, "sample_data", "commands.txt"))

    def test_party_cap_is_cumulative_across_consignment_claims(self):
        rows = [r for r in self.engine.output_claims if r["shipment_id"] == "SHP-007"]
        by_party = {}
        for row in rows:
            if row["party"] != "UNALLOCATED":
                by_party[row["party"]] = by_party.get(row["party"], 0.0) + float(row["share_after_cap"])
        self.assertTrue(by_party)
        self.assertLessEqual(max(by_party.values()), 1_000_000.00)
        self.assertAlmostEqual(by_party["CAR-01"], 1_000_000.00, places=2)

    def test_excess_after_all_party_caps_is_explicitly_unallocated(self):
        rows = [r for r in self.engine.output_claims if r["shipment_id"] == "SHP-007"]
        unallocated = [r for r in rows if r["party"] == "UNALLOCATED"]
        self.assertTrue(unallocated)
        self.assertTrue(all(float(r["share_after_cap"]) == 0.0 for r in unallocated))
        self.assertTrue(all(float(r["attributed_minutes"]) == 0.0 for r in unallocated))

    def test_no_party_with_zero_attributed_minutes_receives_liability(self):
        for row in self.engine.output_claims:
            if row["party"] != "UNALLOCATED" and float(row["attributed_minutes"]) == 0.0:
                self.assertEqual(float(row["share_after_cap"]), 0.0)

    def test_excess_is_redistributed_to_another_attributable_party(self):
        allocated = {"CAR-A": 900.0, "CAR-B": 0.0}
        before, after, unallocated = ComplianceEngine._allocate_claim_shares(
            1000.0, {"CAR-A": 90.0, "CAR-B": 10.0}, allocated, 1000.0
        )
        self.assertAlmostEqual(before["CAR-A"], 900.0)
        self.assertAlmostEqual(before["CAR-B"], 100.0)
        self.assertAlmostEqual(after["CAR-A"], 100.0)
        self.assertAlmostEqual(after["CAR-B"], 900.0)
        self.assertAlmostEqual(unallocated, 0.0)

    def test_handoff_window_is_attributed_to_3pl(self):
        handoff = self.engine.handoffs["SHP-001"][0]
        leg_no, party = self.engine._attribute_time("SHP-001", handoff["handoff_ts"])
        self.assertEqual(party, "3PL")
        self.assertEqual(leg_no, handoff["from_leg_no"])


if __name__ == "__main__":
    unittest.main()
