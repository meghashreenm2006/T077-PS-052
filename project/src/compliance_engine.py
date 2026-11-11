"""
Compliance, Claims, and Command Engine for PS-052.

Implements all business rules (BR-01 to BR-nn) and planted edge cases (EC1 to EC8):
- Multi-modal legs, carriers, and 3PL hand-off transfer windows (10-minute window).
- Re-icing excursion counter resets.
- Data gap detection and double-penalty for carrier-owned loggers.
- 20% freight charge penalty caps.
- Claim liability allocation and redistribution when the insurance cap is reached.
- Exact generation of excursions.csv, decisions.csv, penalties.csv, claims.csv, and release_certificates.csv.
"""

import os
import csv
import math
from datetime import datetime, timedelta
from collections import defaultdict

from src.mkt_calculator import calculate_mkt


class ComplianceEngine:
    def __init__(self, data_dir="sample_data"):
        self.data_dir = data_dir
        self.profiles = {}       # profile_id -> dict
        self.shipments = {}      # shipment_id -> dict
        self.consignments = defaultdict(list) # shipment_id -> list of dicts
        self.legs = defaultdict(list)         # shipment_id -> list of dicts (ordered)
        self.handoffs = defaultdict(list)    # shipment_id -> list of dicts
        self.readings = {}       # shipment_id -> list of (datetime, float)
        self.custody_overrides = defaultdict(list) # shipment_id -> list of reason strings
        self.re_ice_events = defaultdict(list) # shipment_id -> list of timestamps
        self.evaluation_counts = defaultdict(int) # shipment_id -> int

        # Outputs
        self.output_excursions = [] # list of dicts for excursions.csv
        self.output_decisions = []  # list of dicts for decisions.csv
        self.output_penalties = []  # list of dicts for penalties.csv
        self.output_claims = []     # list of dicts for claims.csv
        self.output_certificates = [] # list of dicts for release_certificates.csv

    def _resolve_path(self, filename):
        # Checks if file exists directly, or inside data_dir, or subfolder
        if os.path.exists(filename):
            return filename
        p1 = os.path.join(self.data_dir, filename)
        if os.path.exists(p1):
            return p1
        p2 = os.path.join(self.data_dir, "T077-PS-052-sample-data", filename)
        if os.path.exists(p2):
            return p2
        raise FileNotFoundError(f"Cannot find input file: {filename}")

    # =========================================================================
    # 1. COMMAND: LOAD_PROFILES
    # =========================================================================
    def load_profiles(self, filename):
        filepath = self._resolve_path(filename)
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row["profile_id"].strip()
                self.profiles[pid] = {
                    "profile_id": pid,
                    "name": row["name"].strip(),
                    "range_min_c": float(row["range_min_c"]),
                    "range_max_c": float(row["range_max_c"]),
                    "hard_min_c": float(row["hard_min_c"]),
                    "hard_max_c": float(row["hard_max_c"]),
                    "allowed_excursion_minutes": int(row["allowed_excursion_minutes"]),
                    "allowed_excursion_count": int(row["allowed_excursion_count"]),
                    "mkt_limit_c": float(row["mkt_limit_c"])
                }

    # =========================================================================
    # 2. COMMAND: LOAD_SHIPMENTS
    # =========================================================================
    def load_shipments(self, shipments_file, consignments_file, legs_file, handoffs_file):
        # 1. Shipments
        with open(self._resolve_path(shipments_file), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = row["shipment_id"].strip()
                self.shipments[sid] = {
                    "shipment_id": sid,
                    "origin_city": row["origin_city"].strip(),
                    "destination_city": row["destination_city"].strip(),
                    "planned_departure": datetime.strptime(row["planned_departure"].strip(), "%Y-%m-%d %H:%M:%S"),
                    "insured_value": float(row["insured_value"]),
                    "logger_owner": row["logger_owner"].strip()
                }

        # 2. Consignments
        with open(self._resolve_path(consignments_file), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = row["shipment_id"].strip()
                self.consignments[sid].append({
                    "consignment_id": row["consignment_id"].strip(),
                    "shipment_id": sid,
                    "profile_id": row["profile_id"].strip(),
                    "product": row["product"].strip(),
                    "lot_no": row["lot_no"].strip(),
                    "value_rs": float(row["value_rs"])
                })

        # 3. Legs
        with open(self._resolve_path(legs_file), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = row["shipment_id"].strip()
                self.legs[sid].append({
                    "leg_id": row["leg_id"].strip(),
                    "shipment_id": sid,
                    "leg_no": int(row["leg_no"]),
                    "carrier_id": row["carrier_id"].strip(),
                    "vehicle_type": row["vehicle_type"].strip(),
                    "start_ts": datetime.strptime(row["start_ts"].strip(), "%Y-%m-%d %H:%M:%S"),
                    "end_ts": datetime.strptime(row["end_ts"].strip(), "%Y-%m-%d %H:%M:%S"),
                    "freight_charge": float(row["freight_charge"])
                })
        for sid in self.legs:
            self.legs[sid].sort(key=lambda x: x["leg_no"])

        # 4. Handoffs
        with open(self._resolve_path(handoffs_file), mode="r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sid = row["shipment_id"].strip()
                self.handoffs[sid].append({
                    "shipment_id": sid,
                    "from_leg_no": int(row["from_leg_no"]),
                    "to_leg_no": int(row["to_leg_no"]),
                    "handoff_ts": datetime.strptime(row["handoff_ts"].strip(), "%Y-%m-%d %H:%M:%S"),
                    "receiving_party": row["receiving_party"].strip(),
                    "signature_flag": row["signature_flag"].strip().lower() == "true"
                })

    # =========================================================================
    # 3. COMMAND: INGEST_READINGS
    # =========================================================================
    def ingest_readings(self, shipment_id, filename):
        filepath = self._resolve_path(filename)
        raw_readings = []
        with open(filepath, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.strptime(row["reading_ts"].strip(), "%Y-%m-%d %H:%M:%S")
                temp = float(row["temperature_c"].strip())
                raw_readings.append((ts, temp))

        # Sort chronologically (EC: unsorted file)
        sorted_readings = sorted(raw_readings, key=lambda x: x[0])

        # Deduplicate: if duplicate timestamp, keep first (EC1, EC: exact duplicate line)
        cleaned = []
        seen_ts = set()
        for ts, temp in sorted_readings:
            if ts not in seen_ts:
                cleaned.append((ts, temp))
                seen_ts.add(ts)

        self.readings[shipment_id] = cleaned

    # =========================================================================
    # 4. COMMAND: RE_ICE & OVERRIDE_CUSTODY
    # =========================================================================
    def re_ice(self, shipment_id, handoff_ts_str):
        ts = datetime.strptime(handoff_ts_str.strip(), "%Y-%m-%d %H:%M:%S")
        self.re_ice_events[shipment_id].append(ts)

    def override_custody(self, shipment_id, reason):
        self.custody_overrides[shipment_id].append(reason)

    # =========================================================================
    # Helper: Attribute a timestamp or interval to Leg / Carrier / 3PL
    # =========================================================================
    def _attribute_time(self, shipment_id, timestamp):
        """
        Determines the leg_no and responsible party ('CAR-nn' or '3PL') for a given timestamp.
        Rule: The 10-minute window immediately after handoff_ts is attributed to '3PL'.
        """
        legs = self.legs[shipment_id]
        handoffs = self.handoffs[shipment_id]

        # Check if timestamp falls in 3PL hand-off window (handoff_ts to handoff_ts + 10 min)
        for h in handoffs:
            h_start = h["handoff_ts"]
            h_end = h_start + timedelta(minutes=10)
            if h_start <= timestamp < h_end:
                return h["from_leg_no"], "3PL"

        # Otherwise find matching leg
        for leg in legs:
            # start_ts inclusive, end_ts exclusive
            if leg["start_ts"] <= timestamp < leg["end_ts"]:
                return leg["leg_no"], leg["carrier_id"]

        # If at or after last leg end
        if legs and timestamp >= legs[-1]["end_ts"]:
            return legs[-1]["leg_no"], legs[-1]["carrier_id"]

        # Default to first leg if before
        if legs:
            return legs[0]["leg_no"], legs[0]["carrier_id"]
        return 1, "UNKNOWN"

    # =========================================================================
    # 5. COMMAND: EVALUATE
    # =========================================================================
    def evaluate(self, shipment_id):
        self.evaluation_counts[shipment_id] += 1
        eval_no = self.evaluation_counts[shipment_id]

        shipment = self.shipments[shipment_id]
        consignments = self.consignments[shipment_id]
        legs = self.legs[shipment_id]
        handoffs = self.handoffs[shipment_id]
        readings = self.readings.get(shipment_id, [])

        # Filter out invalid readings (999.9 C) for MKT and excursions, but track timestamps
        valid_readings = [(ts, temp) for ts, temp in readings if abs(temp - 999.9) > 0.01]

        # Calculate MKT using every valid reading
        mkt_c = None
        if valid_readings:
            temps = [temp for _, temp in valid_readings]
            mkt_c = round(calculate_mkt(temps), 2)

        # Check chain-of-custody validity
        custody_valid = True
        custody_reason = None

        # 1. Check hand-off timing vs previous leg end_ts
        for h in handoffs:
            from_leg = next((l for l in legs if l["leg_no"] == h["from_leg_no"]), None)
            if from_leg and h["handoff_ts"] < from_leg["end_ts"]:
                custody_valid = False
                custody_reason = "HANDOFF_BEFORE_LEG_END"

        # 2. Check receiving party signature
        for h in handoffs:
            if not h["signature_flag"]:
                custody_valid = False
                custody_reason = "MISSING_RECEIVING_SIGNATURE"

        # Check if custody issue is overridden
        if not custody_valid and self.custody_overrides.get(shipment_id):
            custody_valid = True
            custody_reason = None

        # Detect Data Gaps (> 15 minutes)
        # Note: 15 minutes exactly is NOT a gap (EC2)
        data_gaps = []
        for i in range(1, len(valid_readings)):
            prev_ts = valid_readings[i - 1][0]
            curr_ts = valid_readings[i][0]
            interval_min = (curr_ts - prev_ts).total_seconds() / 60.0
            if interval_min > 15.0:
                data_gaps.append((prev_ts, curr_ts, interval_min))

        # Check Insufficient Pre-cool on each leg
        precool_flags = {} # leg_no -> bool
        # "leg starts with out-of-range readings in its first 10 minutes -> INSUFFICIENT_PRECOOL"
        # We check against the first consignment's profile
        ref_profile = self.profiles[consignments[0]["profile_id"]] if consignments else None
        for leg in legs:
            l_start = leg["start_ts"]
            l_precool_end = l_start + timedelta(minutes=10)
            precool_readings = [temp for ts, temp in valid_readings if l_start <= ts < l_precool_end]
            has_precool_excursion = False
            if ref_profile and precool_readings:
                for temp in precool_readings:
                    if temp < ref_profile["range_min_c"] or temp > ref_profile["range_max_c"]:
                        has_precool_excursion = True
                        break
            precool_flags[leg["leg_no"]] = has_precool_excursion

        # Evaluate per consignment
        excursions_by_profile = {} # profile_id -> list of raw excursions
        excursions_recorded_for_shipment = False

        excursion_counter = 1
        shipment_excursion_rows = []

        # Track penalties across legs for this evaluation
        leg_minutes = defaultdict(float)      # leg_no -> minutes
        party_minutes = defaultdict(float)    # party -> minutes
        gap_penalty_minutes = defaultdict(float) # party -> minutes

        for cons in consignments:
            pid = cons["profile_id"]
            prof = self.profiles[pid]

            # Detect excursions for this profile
            raw_excursions = []
            curr_start = None
            curr_temps = []
            curr_type = None

            for i, (ts, temp) in enumerate(valid_readings):
                is_out = (temp < prof["range_min_c"] or temp > prof["range_max_c"])
                if is_out:
                    if curr_start is None:
                        curr_start = ts
                        curr_temps = [temp]
                        curr_type = "HIGH" if temp > prof["range_max_c"] else "LOW"
                    else:
                        curr_temps.append(temp)
                else:
                    if curr_start is not None:
                        # Closed excursion: duration = first in-range timestamp - start timestamp
                        dur = (ts - curr_start).total_seconds() / 60.0
                        raw_excursions.append({
                            "type": curr_type,
                            "start_ts": curr_start,
                            "end_ts": ts,
                            "duration_minutes": dur,
                            "max_temp_c": max(curr_temps) if curr_type == "HIGH" else min(curr_temps)
                        })
                        curr_start = None
                        curr_temps = []
                        curr_type = None

            # Trailing excursion closes at last reading
            if curr_start is not None and valid_readings:
                final_ts = valid_readings[-1][0]
                dur = (final_ts - curr_start).total_seconds() / 60.0
                raw_excursions.append({
                    "type": curr_type,
                    "start_ts": curr_start,
                    "end_ts": final_ts,
                    "duration_minutes": dur,
                    "max_temp_c": max(curr_temps) if curr_type == "HIGH" else min(curr_temps)
                })

            excursions_by_profile[pid] = raw_excursions

            # Cumulative excursion minutes
            cumulative_minutes = sum(e["duration_minutes"] for e in raw_excursions)

            # Qualifying excursion count (>= 5 min)
            # Re-ice logic (EC8): resets excursion counter for PASSIVE_BOX legs following re_ice_ts
            excursion_count = 0
            re_ice_ts_list = self.re_ice_events.get(shipment_id, [])

            for e in raw_excursions:
                if e["duration_minutes"] >= 5.0:
                    # Check if this excursion occurred after a re-icing on a passive-box leg
                    is_post_reice_passive = False
                    e_leg_no, _ = self._attribute_time(shipment_id, e["start_ts"])
                    e_leg = next((l for l in legs if l["leg_no"] == e_leg_no), None)
                    if e_leg and e_leg["vehicle_type"] == "PASSIVE_BOX":
                        for r_ts in re_ice_ts_list:
                            if e["start_ts"] >= r_ts:
                                is_post_reice_passive = True
                                break
                    if not is_post_reice_passive:
                        excursion_count += 1
                    else:
                        # Resets count for passive leg after re-ice
                        pass

            # Check Hard limits (strictly below hard_min_c or strictly above hard_max_c)
            # Note: Equal to hard limit is NOT a hard breach (EC4)
            hard_breach = False
            for ts, temp in valid_readings:
                if temp < prof["hard_min_c"] or temp > prof["hard_max_c"]:
                    hard_breach = True
                    break

            # Evaluate Decision
            decision = "RELEASE"
            reasons = []

            if hard_breach:
                decision = "REJECT"
                reasons.append("HARD_LIMIT_BREACH")
            elif not custody_valid:
                decision = "QUARANTINE"
                reasons.append(custody_reason or "CUSTODY_BREACH")
            elif cumulative_minutes > prof["allowed_excursion_minutes"]:
                decision = "QUARANTINE"
                reasons.append("EXCEEDED_ALLOWED_MINUTES")
            elif excursion_count > prof["allowed_excursion_count"]:
                decision = "QUARANTINE"
                reasons.append("EXCEEDED_EXCURSION_COUNT")
            elif mkt_c is not None and mkt_c > prof["mkt_limit_c"]:
                decision = "QUARANTINE"
                reasons.append("MKT_ABOVE_LIMIT")

            reason_codes_str = ";".join(reasons) if reasons else "COMPLIANT"

            self.output_decisions.append({
                "shipment_id": shipment_id,
                "consignment_id": cons["consignment_id"],
                "profile_id": pid,
                "evaluation_no": eval_no,
                "cumulative_minutes": f"{cumulative_minutes:.2f}",
                "excursion_count": excursion_count,
                "mkt_c": f"{mkt_c:.2f}" if mkt_c is not None else "0.00",
                "decision": decision,
                "reason_codes": reason_codes_str
            })

            # If released, prepare release certificate
            if decision == "RELEASE":
                self.output_certificates.append({
                    "shipment_id": shipment_id,
                    "consignment_id": cons["consignment_id"],
                    "released_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cumulative_minutes": f"{cumulative_minutes:.2f}",
                    "mkt_c": f"{mkt_c:.2f}",
                    "certificate_text": f"Consignment {cons['consignment_id']} released compliant with profile {pid}."
                })

            # If rejected, claim calculation will be performed
            if decision == "REJECT":
                # Will calculate claims based on attributed excursion minutes across parties
                pass

        # Excursion & Leg Splitting for excursions.csv & penalties.csv
        # Use primary profile (consignments[0]) for shipment-level excursions.csv
        primary_excursions = excursions_by_profile.get(consignments[0]["profile_id"], [])

        # Process each excursion: split if crossing legs or 3PL handoff window (EC5)
        for exc in primary_excursions:
            e_start = exc["start_ts"]
            e_end = exc["end_ts"]
            e_dur = exc["duration_minutes"]
            counts_toward = "true" if e_dur >= 5.0 else "false"

            # Check if this excursion crosses any hand-off
            splits = self._split_interval(shipment_id, e_start, e_end)
            for s_start, s_end, s_leg_no, s_party in splits:
                s_dur = (s_end - s_start).total_seconds() / 60.0
                if s_dur <= 0:
                    continue

                self.output_excursions.append({
                    "shipment_id": shipment_id,
                    "excursion_no": excursion_counter,
                    "type": exc["type"],
                    "start_ts": s_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_ts": s_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_minutes": f"{s_dur:.2f}",
                    "max_temp_c": f"{exc['max_temp_c']:.1f}",
                    "leg_no": s_leg_no,
                    "party": s_party,
                    "counts_toward_limit": counts_toward
                })
                excursion_counter += 1

                # Attribute minutes for penalties
                if s_party != "3PL":
                    leg_minutes[s_leg_no] += s_dur
                party_minutes[s_party] += s_dur

        # Also add DATA_GAP entries to excursions.csv
        for g_start, g_end, g_dur in data_gaps:
            g_leg_no, g_party = self._attribute_time(shipment_id, g_start)
            self.output_excursions.append({
                "shipment_id": shipment_id,
                "excursion_no": excursion_counter,
                "type": "DATA_GAP",
                "start_ts": g_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_ts": g_end.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_minutes": f"{g_dur:.2f}",
                "max_temp_c": "N/A",
                "leg_no": g_leg_no,
                "party": g_party,
                "counts_toward_limit": "false"
            })
            excursion_counter += 1

            # If logger_owner is CARRIER, gap minutes are penalised at double rate (EC2)
            if shipment["logger_owner"] == "CARRIER" and g_party != "3PL":
                gap_penalty_minutes[g_leg_no] += g_dur * 2.0
            elif g_party != "3PL":
                gap_penalty_minutes[g_leg_no] += g_dur

        # Calculate Carrier Penalties per leg
        for leg in legs:
            l_no = leg["leg_no"]
            cid = leg["carrier_id"]
            v_type = leg["vehicle_type"]
            f_charge = leg["freight_charge"]

            # Rate: REEFER = Rs 50 / min; PASSIVE_BOX = Rs 20 / min
            rate = 50.0 if v_type == "REEFER" else 20.0

            attr_mins = leg_minutes[l_no]
            gap_mins = gap_penalty_minutes[l_no]

            min_penalty = (attr_mins * rate) + (gap_mins * rate)
            precool_penalty = 2000.00 if precool_flags.get(l_no) else 0.00

            subtotal = min_penalty + precool_penalty
            cap = 0.20 * f_charge
            cap_applied = "true" if subtotal > cap else "false"
            penalty_total = min(subtotal, cap)

            self.output_penalties.append({
                "shipment_id": shipment_id,
                "leg_no": l_no,
                "carrier_id": cid,
                "attributed_minutes": f"{attr_mins:.2f}",
                "minute_penalty": f"{min_penalty:.2f}",
                "precool_penalty": f"{precool_penalty:.2f}",
                "cap_applied": cap_applied,
                "penalty_total": f"{penalty_total:.2f}"
            })

        # Calculate Claims for REJECTED consignments
        for cons in consignments:
            # Find decision for this consignment in current eval
            dec_entry = next(
                (d for d in self.output_decisions if d["consignment_id"] == cons["consignment_id"] and d["evaluation_no"] == eval_no),
                None
            )
            if dec_entry and dec_entry["decision"] == "REJECT":
                claim_val = cons["value_rs"]
                total_attr_mins = sum(leg_minutes.values())
                if total_attr_mins <= 0:
                    total_attr_mins = 1.0 # fallback

                # Liability split with redistribution if leg cap is hit (EC7)
                cap = shipment["insured_value"] # Rs 10 lakh per leg / party cap

                liable_legs = [l for l in legs if leg_minutes[l["leg_no"]] > 0]
                if not liable_legs and legs:
                    liable_legs = legs

                shares_before = {}
                for l in liable_legs:
                    l_no = l["leg_no"]
                    mins = leg_minutes[l_no]
                    shares_before[l_no] = claim_val * (mins / total_attr_mins)

                # Check caps and redistribute excess
                shares_after = {}
                excess_pool = 0.0
                non_capped_legs = []

                for l_no, share in shares_before.items():
                    if share > cap:
                        shares_after[l_no] = cap
                        excess_pool += (share - cap)
                    else:
                        shares_after[l_no] = share
                        non_capped_legs.append(l_no)

                # Redistribute excess to non-capped legs proportionally (EC7)
                if excess_pool > 0 and non_capped_legs:
                    non_capped_min_total = sum(leg_minutes[l_no] for l_no in non_capped_legs)
                    if non_capped_min_total > 0:
                        for l_no in non_capped_legs:
                            shares_after[l_no] += excess_pool * (leg_minutes[l_no] / non_capped_min_total)

                for l in liable_legs:
                    l_no = l["leg_no"]
                    self.output_claims.append({
                        "shipment_id": shipment_id,
                        "consignment_id": cons["consignment_id"],
                        "claim_value": f"{claim_val:.2f}",
                        "party": l["carrier_id"],
                        "attributed_minutes": f"{leg_minutes[l_no]:.2f}",
                        "share_before_cap": f"{shares_before[l_no]:.2f}",
                        "share_after_cap": f"{shares_after[l_no]:.2f}"
                    })

    def _split_interval(self, shipment_id, start_ts, end_ts):
        """
        Splits an interval [start_ts, end_ts] across leg boundaries and the 10-minute 3PL hand-off windows.
        Returns list of (seg_start, seg_end, leg_no, party).
        """
        handoffs = self.handoffs[shipment_id]
        legs = self.legs[shipment_id]

        # Critical boundary timestamps:
        # Leg start/ends and handoff start/ends (handoff_ts to handoff_ts + 10m)
        points = set([start_ts, end_ts])
        for leg in legs:
            if start_ts < leg["start_ts"] < end_ts:
                points.add(leg["start_ts"])
            if start_ts < leg["end_ts"] < end_ts:
                points.add(leg["end_ts"])
        for h in handoffs:
            h_start = h["handoff_ts"]
            h_end = h_start + timedelta(minutes=10)
            if start_ts < h_start < end_ts:
                points.add(h_start)
            if start_ts < h_end < end_ts:
                points.add(h_end)

        sorted_points = sorted(list(points))
        segments = []
        for i in range(len(sorted_points) - 1):
            s_a = sorted_points[i]
            s_b = sorted_points[i + 1]
            mid = s_a + (s_b - s_a) / 2
            leg_no, party = self._attribute_time(shipment_id, mid)
            segments.append((s_a, s_b, leg_no, party))

        return segments

    # =========================================================================
    # 6. COMMAND: PRINT_REPORTS & WRITE OUTPUT CSVS
    # =========================================================================
    def print_reports(self, shipment_id, out_dir="output"):
        os.makedirs(out_dir, exist_ok=True)
        # Note: We will write the aggregated evaluation CSVs at the end of all commands
        pass

    def export_all_csvs(self, out_dir="output"):
        os.makedirs(out_dir, exist_ok=True)

        # 1. excursions.csv
        with open(os.path.join(out_dir, "excursions.csv"), mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["shipment_id", "excursion_no", "type", "start_ts", "end_ts", "duration_minutes", "max_temp_c", "leg_no", "party", "counts_toward_limit"])
            for row in self.output_excursions:
                writer.writerow([row["shipment_id"], row["excursion_no"], row["type"], row["start_ts"], row["end_ts"], row["duration_minutes"], row["max_temp_c"], row["leg_no"], row["party"], row["counts_toward_limit"]])

        # 2. decisions.csv
        with open(os.path.join(out_dir, "decisions.csv"), mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["shipment_id", "consignment_id", "profile_id", "evaluation_no", "cumulative_minutes", "excursion_count", "mkt_c", "decision", "reason_codes"])
            for row in self.output_decisions:
                writer.writerow([row["shipment_id"], row["consignment_id"], row["profile_id"], row["evaluation_no"], row["cumulative_minutes"], row["excursion_count"], row["mkt_c"], row["decision"], row["reason_codes"]])

        # 3. penalties.csv
        with open(os.path.join(out_dir, "penalties.csv"), mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["shipment_id", "leg_no", "carrier_id", "attributed_minutes", "minute_penalty", "precool_penalty", "cap_applied", "penalty_total"])
            for row in self.output_penalties:
                writer.writerow([row["shipment_id"], row["leg_no"], row["carrier_id"], row["attributed_minutes"], row["minute_penalty"], row["precool_penalty"], row["cap_applied"], row["penalty_total"]])

        # 4. claims.csv
        with open(os.path.join(out_dir, "claims.csv"), mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["shipment_id", "consignment_id", "claim_value", "party", "attributed_minutes", "share_before_cap", "share_after_cap"])
            for row in self.output_claims:
                writer.writerow([row["shipment_id"], row["consignment_id"], row["claim_value"], row["party"], row["attributed_minutes"], row["share_before_cap"], row["share_after_cap"]])

        # 5. release_certificates.csv
        with open(os.path.join(out_dir, "release_certificates.csv"), mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["shipment_id", "consignment_id", "released_at", "cumulative_minutes", "mkt_c", "certificate_text"])
            for row in self.output_certificates:
                writer.writerow([row["shipment_id"], row["consignment_id"], row["released_at"], row["cumulative_minutes"], row["mkt_c"], row["certificate_text"]])

    # =========================================================================
    # 7. MAIN COMMAND FILE EXECUTION
    # =========================================================================
    def execute_command_file(self, command_file_path):
        filepath = self._resolve_path(command_file_path)
        with open(filepath, mode="r", encoding="utf-8") as f:
            for line_no, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split("|")
                cmd = parts[0].strip()

                if cmd == "LOAD_PROFILES":
                    self.load_profiles(parts[1].strip())
                elif cmd == "LOAD_SHIPMENTS":
                    self.load_shipments(parts[1].strip(), parts[2].strip(), parts[3].strip(), parts[4].strip())
                elif cmd == "INGEST_READINGS":
                    self.ingest_readings(parts[1].strip(), parts[2].strip())
                elif cmd == "RE_ICE":
                    self.re_ice(parts[1].strip(), parts[2].strip())
                elif cmd == "EVALUATE":
                    self.evaluate(parts[1].strip())
                elif cmd == "OVERRIDE_CUSTODY":
                    self.override_custody(parts[1].strip(), parts[2].strip())
                elif cmd == "PRINT_REPORTS":
                    self.print_reports(parts[1].strip())
                else:
                    raise ValueError(f"Unknown command at line {line_no}: {cmd}")

        # Automatically export all evaluation CSVs
        self.export_all_csvs()
