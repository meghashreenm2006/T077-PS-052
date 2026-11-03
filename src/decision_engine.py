"""
Decision Engine for Cold-Chain Shipment Compliance.

Evaluates temperature readings, excursions, data gaps, MKT, and chain of custody
against configured product temperature profiles to render auditable RELEASE,
QUARANTINE, or REJECT decisions.
"""

from src.mkt_calculator import validate_mkt


class DecisionResult(str):
    """
    Result of a shipment compliance evaluation.

    Inherits from str so that direct equality comparisons:
        result == "RELEASE"
        result == "QUARANTINE"
        result == "REJECT"
    continue to work seamlessly.

    Also supports attribute access:
        result.decision
        result.reasons
        result.audit_trail
        result.is_release / result.is_quarantine / result.is_reject

    And dictionary-style key access:
        result["decision"]
        result["reasons"]
        result.get("decision")
    """
    def __new__(cls, decision, reasons=None, audit_trail=None):
        instance = super().__new__(cls, decision)
        instance.decision = str(decision)
        instance.reasons = list(reasons or [])
        instance.audit_trail = dict(audit_trail or {})
        return instance

    @property
    def is_release(self):
        return self.decision == "RELEASE"

    @property
    def is_quarantine(self):
        return self.decision == "QUARANTINE"

    @property
    def is_reject(self):
        return self.decision == "REJECT"

    def __getitem__(self, item):
        if isinstance(item, str):
            if item == "decision":
                return self.decision
            elif item == "reasons":
                return self.reasons
            elif item == "audit_trail":
                return self.audit_trail
            raise KeyError(f"Invalid key on DecisionResult: {item}")
        return super().__getitem__(item)

    def get(self, item, default=None):
        if item == "decision":
            return self.decision
        elif item == "reasons":
            return self.reasons
        elif item == "audit_trail":
            return self.audit_trail
        return default

    def __contains__(self, item):
        if item in ("decision", "reasons", "audit_trail"):
            return True
        return super().__contains__(item)

    def to_dict(self):
        return {
            "decision": self.decision,
            "reasons": self.reasons,
            "audit_trail": self.audit_trail
        }


def evaluate_shipment(
    excursions,
    readings,
    profile,
    mkt=None,
    chain_custody_valid=True,
    data_gaps=None
):
    """
    Decide whether a shipment can be released, must be quarantined, or must be rejected.

    Rules priority:
    1. REJECT: Any temperature reading violating hard_min or hard_max limits.
    2. QUARANTINE:
       - Chain of custody invalid or unverified.
       - MKT exceeding max_mkt or below min_mkt.
       - Missing data gaps exceeding allowable tolerances.
       - Cumulative excursion duration exceeding allowed_minutes.
       - Number of qualifying excursions (>= 5 min) exceeding allowed_excursions.
    3. RELEASE: All conditions within compliant thresholds.
    """
    reasons = []
    hard_limit_breached = False

    # Extract thresholds with defaults
    hard_min = profile.get("hard_min", profile.get("min_temp"))
    hard_max = profile.get("hard_max", profile.get("max_temp"))
    min_temp = profile.get("min_temp")
    max_temp = profile.get("max_temp")
    allowed_minutes = profile.get("allowed_minutes", 0)
    allowed_excursions = profile.get("allowed_excursions", 0)
    min_mkt = profile.get("min_mkt", min_temp)
    max_mkt = profile.get("max_mkt", max_temp)
    allowed_gap_minutes = profile.get("allowed_gap_minutes", 30.0)
    single_gap_limit = profile.get("single_gap_limit_minutes", 30.0)
    min_excursion_duration_to_count = profile.get("min_excursion_duration_to_count", 5.0)

    # 1. Rule: Hard Limits check (causes REJECT priority)
    hard_violations = []
    for timestamp, temperature in readings:
        if temperature < hard_min:
            hard_violations.append((timestamp, temperature, "below", hard_min))
        elif temperature > hard_max:
            hard_violations.append((timestamp, temperature, "above", hard_max))

    if hard_violations:
        hard_limit_breached = True
        for ts, temp, direction, limit in hard_violations:
            reasons.append(
                f"Critical hard temperature limit breached: {temp:.1f}°C {direction} hard threshold {limit:.1f}°C at {ts}."
            )

    # 2. Rule: Chain of custody validation
    if not chain_custody_valid:
        reasons.append("Invalid or unverified chain of custody during transit.")

    # 3. Rule: MKT Validation (Upper & Lower limits)
    mkt_validation = validate_mkt(mkt, min_mkt=min_mkt, max_mkt=max_mkt)
    if not mkt_validation["valid"]:
        reasons.append(mkt_validation["reason"])

    # 4. Rule: Missing Data Gaps validation
    total_gap_minutes = 0.0
    if data_gaps:
        total_gap_minutes = sum(gap.get("duration_minutes", 0.0) for gap in data_gaps)
        if total_gap_minutes > allowed_gap_minutes:
            reasons.append(
                f"Total missing data gap duration ({total_gap_minutes:.1f} min) exceeds allowed tolerance ({allowed_gap_minutes:.1f} min)."
            )

        for gap in data_gaps:
            gap_duration = gap.get("duration_minutes", 0.0)
            if gap_duration > single_gap_limit:
                reasons.append(
                    f"Single logger data gap of {gap_duration:.1f} min ({gap.get('start')} to {gap.get('end')}) exceeds single gap limit ({single_gap_limit:.1f} min)."
                )

    # 5. Rule: Cumulative excursion duration
    total_excursion_minutes = sum(
        excursion.get("duration_minutes", 0.0)
        for excursion in excursions
    )
    if total_excursion_minutes > allowed_minutes:
        reasons.append(
            f"Total cumulative excursion duration ({total_excursion_minutes:.1f} min) exceeds permitted limit ({allowed_minutes:.1f} min)."
        )

    # 6. Rule: Qualifying excursion count
    qualifying_excursions = [
        excursion for excursion in excursions
        if excursion.get("duration_minutes", 0.0) >= min_excursion_duration_to_count
    ]
    if len(qualifying_excursions) > allowed_excursions:
        reasons.append(
            f"Number of qualifying excursions ({len(qualifying_excursions)}) exceeds allowed count ({allowed_excursions})."
        )

    # Build Audit Trail
    audit_trail = {
        "total_readings": len(readings),
        "total_excursions": len(excursions),
        "total_excursion_minutes": round(total_excursion_minutes, 2),
        "qualifying_excursions": len(qualifying_excursions),
        "mkt_celsius": round(mkt, 2) if mkt is not None else None,
        "mkt_valid": mkt_validation["valid"],
        "data_gaps_count": len(data_gaps) if data_gaps else 0,
        "total_gap_minutes": round(total_gap_minutes, 2),
        "chain_custody_valid": chain_custody_valid,
        "hard_limit_breached": hard_limit_breached
    }

    # Priority determination
    if hard_limit_breached:
        final_decision = "REJECT"
    elif reasons:
        final_decision = "QUARANTINE"
    else:
        final_decision = "RELEASE"
        reasons.append("Shipment temperatures and chain of custody fully comply with product specifications.")

    return DecisionResult(final_decision, reasons=reasons, audit_trail=audit_trail)
