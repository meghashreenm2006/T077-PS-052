"""
Product Temperature Profiles for Cold-Chain Monitoring.

Defines permitted temperature ranges, hard thresholds, excursion tolerances,
MKT boundaries, and data gap limits for cold-chain products.

Two naming conventions are supported:
  - Canonical names (VACCINE_2_8, FROZEN, AMBIENT) used by the CLI and unit tests.
  - CSV profile IDs (PRF-01 … PRF-05) loaded from profiles.csv by ComplianceEngine.

Both registries are kept in sync when load_profiles_from_csv() is called.
"""

import csv
import os
from copy import deepcopy

# ---------------------------------------------------------------------------
# Built-in profiles — used by CLI (src/main.py) and unit tests (tests/).
# Values must stay consistent with profiles.csv so both paths agree.
# ---------------------------------------------------------------------------
DEFAULT_PROFILES = {
    "VACCINE_2_8": {
        "min_temp": 2.0,
        "max_temp": 8.0,
        "hard_min": 0.0,
        "hard_max": 15.0,
        "allowed_minutes": 120.0,     # matches PRF-01 in profiles.csv
        "allowed_excursions": 3,
        "min_mkt": 2.0,
        "max_mkt": 8.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "FROZEN": {
        "min_temp": -25.0,
        "max_temp": -18.0,            # matches PRF-02 (FROZEN_MINUS18) in profiles.csv
        "hard_min": -30.0,
        "hard_max": -15.0,
        "allowed_minutes": 60.0,
        "allowed_excursions": 3,
        "min_mkt": -25.0,
        "max_mkt": -18.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "AMBIENT": {
        "min_temp": 15.0,
        "max_temp": 25.0,
        "hard_min": 8.0,              # matches PRF-05 (CRT_15_25) in profiles.csv
        "hard_max": 30.0,
        "allowed_minutes": 240.0,
        "allowed_excursions": 4,
        "min_mkt": 15.0,
        "max_mkt": 25.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    # Aliases that match profiles.csv profile names exactly
    "FROZEN_MINUS18": {
        "min_temp": -25.0,
        "max_temp": -18.0,
        "hard_min": -30.0,
        "hard_max": -15.0,
        "allowed_minutes": 60.0,
        "allowed_excursions": 3,
        "min_mkt": -25.0,
        "max_mkt": -18.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "INSULIN_2_8_STRICT": {
        "min_temp": 2.0,
        "max_temp": 8.0,
        "hard_min": 0.0,
        "hard_max": 12.0,
        "allowed_minutes": 90.0,
        "allowed_excursions": 2,
        "min_mkt": 2.0,
        "max_mkt": 8.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "CHILLED_FOOD_0_4": {
        "min_temp": 0.0,
        "max_temp": 4.0,
        "hard_min": -2.0,
        "hard_max": 10.0,
        "allowed_minutes": 180.0,
        "allowed_excursions": 3,
        "min_mkt": 0.0,
        "max_mkt": 5.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "CRT_15_25": {
        "min_temp": 15.0,
        "max_temp": 25.0,
        "hard_min": 8.0,
        "hard_max": 30.0,
        "allowed_minutes": 240.0,
        "allowed_excursions": 4,
        "min_mkt": 15.0,
        "max_mkt": 25.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
}

# Active profiles registry
PROFILES = deepcopy(DEFAULT_PROFILES)

# ---------------------------------------------------------------------------
# CSV → canonical profile field mapping
# ---------------------------------------------------------------------------
_CSV_FIELD_MAP = {
    # csv column          : profiles.py key
    "range_min_c":          "min_temp",
    "range_max_c":          "max_temp",
    "hard_min_c":           "hard_min",
    "hard_max_c":           "hard_max",
    "allowed_excursion_minutes": "allowed_minutes",
    "allowed_excursion_count":   "allowed_excursions",
    "mkt_limit_c":          "max_mkt",   # used as upper MKT limit
}

# Map from CSV profile_id  →  canonical name used by unit-test path
_CSV_ID_TO_NAME = {
    "PRF-01": "VACCINE_2_8",
    "PRF-02": "FROZEN_MINUS18",
    "PRF-03": "INSULIN_2_8_STRICT",
    "PRF-04": "CHILLED_FOOD_0_4",
    "PRF-05": "CRT_15_25",
}


def validate_profile(profile_data):
    """
    Validate that temperature and tolerance thresholds are logically consistent.
    """
    required_keys = ["min_temp", "max_temp", "hard_min", "hard_max", "allowed_minutes", "allowed_excursions"]
    for key in required_keys:
        if key not in profile_data:
            raise ValueError(f"Profile configuration missing required key: '{key}'")

    hard_min = profile_data["hard_min"]
    min_temp = profile_data["min_temp"]
    max_temp = profile_data["max_temp"]
    hard_max = profile_data["hard_max"]

    if not (hard_min <= min_temp <= max_temp <= hard_max):
        raise ValueError(
            f"Invalid temperature hierarchy: must satisfy hard_min ({hard_min}) <= "
            f"min_temp ({min_temp}) <= max_temp ({max_temp}) <= hard_max ({hard_max})"
        )

    min_mkt = profile_data.get("min_mkt", min_temp)
    max_mkt = profile_data.get("max_mkt", max_temp)
    if min_mkt > max_mkt:
        raise ValueError(f"min_mkt ({min_mkt}) cannot be greater than max_mkt ({max_mkt})")

    if profile_data.get("allowed_minutes", 0) < 0:
        raise ValueError("allowed_minutes cannot be negative")

    if profile_data.get("allowed_excursions", 0) < 0:
        raise ValueError("allowed_excursions cannot be negative")


def get_profile(profile_name):
    """
    Retrieve temperature profile configuration by name with full defaults applied.
    """
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown temperature profile: {profile_name}")

    profile = deepcopy(PROFILES[profile_name])

    # Populate optional defaults if missing
    profile.setdefault("min_mkt", profile["min_temp"])
    profile.setdefault("max_mkt", profile["max_temp"])
    profile.setdefault("max_gap_minutes", 15.0)
    profile.setdefault("allowed_gap_minutes", 30.0)
    profile.setdefault("single_gap_limit_minutes", 30.0)
    profile.setdefault("min_excursion_duration_to_count", 5.0)

    return profile


def register_profile(profile_name, profile_data):
    """
    Register a new product temperature profile or update an existing one.
    """
    if not profile_name or not isinstance(profile_name, str):
        raise ValueError("Profile name must be a non-empty string.")

    validate_profile(profile_data)
    new_profile = deepcopy(profile_data)
    new_profile.setdefault("min_mkt", new_profile["min_temp"])
    new_profile.setdefault("max_mkt", new_profile["max_temp"])
    new_profile.setdefault("max_gap_minutes", 15.0)
    new_profile.setdefault("allowed_gap_minutes", 30.0)
    new_profile.setdefault("single_gap_limit_minutes", 30.0)
    new_profile.setdefault("min_excursion_duration_to_count", 5.0)

    PROFILES[profile_name] = new_profile
    return new_profile


def list_profiles():
    """
    Return a list of all registered profile names.
    """
    return list(PROFILES.keys())


def reset_profiles():
    """
    Reset profiles registry to built-in defaults.
    """
    global PROFILES
    PROFILES = deepcopy(DEFAULT_PROFILES)


def load_profiles_from_csv(csv_path):
    """
    Load temperature profiles from a CSV file (profiles.csv) and register them
    in PROFILES under both their CSV profile_id (PRF-01 …) and their canonical
    name (VACCINE_2_8 …) so both the production engine and the CLI/tests can
    resolve profiles without confusion.

    Existing entries are updated; nothing is deleted.
    """
    with open(csv_path, mode="r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            pid = row["profile_id"].strip()
            name = row["name"].strip()

            # Build a canonical profile dict from CSV columns
            profile = {
                "min_temp":    float(row["range_min_c"]),
                "max_temp":    float(row["range_max_c"]),
                "hard_min":    float(row["hard_min_c"]),
                "hard_max":    float(row["hard_max_c"]),
                "allowed_minutes":    float(row["allowed_excursion_minutes"]),
                "allowed_excursions": int(row["allowed_excursion_count"]),
                "min_mkt":     float(row["range_min_c"]),   # lower bound = range_min
                "max_mkt":     float(row["mkt_limit_c"]),
                "max_gap_minutes":             15.0,
                "allowed_gap_minutes":         30.0,
                "single_gap_limit_minutes":    30.0,
                "min_excursion_duration_to_count": 5.0,
            }

            # Register under the CSV profile_id  (PRF-01, PRF-02, …)
            PROFILES[pid] = deepcopy(profile)

            # Also register under the CSV display name  (VACCINE_2_8, …)
            if name:
                PROFILES[name] = deepcopy(profile)

            # Also register under the canonical alias table, if known
            canonical = _CSV_ID_TO_NAME.get(pid)
            if canonical and canonical != name:
                PROFILES[canonical] = deepcopy(profile)

    return list(PROFILES.keys())


def get_profile_ids():
    """Return all registered profile IDs/names."""
    return list(PROFILES.keys())
