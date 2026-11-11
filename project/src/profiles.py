"""
Product Temperature Profiles for Cold-Chain Monitoring.

Defines permitted temperature ranges, hard thresholds, excursion tolerances,
MKT boundaries, and data gap limits for cold-chain products.
"""

from copy import deepcopy

DEFAULT_PROFILES = {
    "VACCINE_2_8": {
        "min_temp": 2.0,
        "max_temp": 8.0,
        "hard_min": 0.0,
        "hard_max": 15.0,
        "allowed_minutes": 30.0,
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
        "max_temp": -15.0,
        "hard_min": -30.0,
        "hard_max": -10.0,
        "allowed_minutes": 20.0,
        "allowed_excursions": 3,
        "min_mkt": -25.0,
        "max_mkt": -15.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    },
    "AMBIENT": {
        "min_temp": 15.0,
        "max_temp": 25.0,
        "hard_min": 10.0,
        "hard_max": 30.0,
        "allowed_minutes": 60.0,
        "allowed_excursions": 3,
        "min_mkt": 15.0,
        "max_mkt": 25.0,
        "max_gap_minutes": 15.0,
        "allowed_gap_minutes": 30.0,
        "single_gap_limit_minutes": 30.0,
        "min_excursion_duration_to_count": 5.0
    }
}

# Active profiles registry
PROFILES = deepcopy(DEFAULT_PROFILES)


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
