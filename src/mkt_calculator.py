"""
Mean Kinetic Temperature (MKT) Calculator.

Calculates MKT based on the Haynes equation (Arrhenius reaction kinetics)
recommended by USP <1079> and FDA guidelines, and validates against
product-specific lower and upper MKT specifications.
"""

import math

GAS_CONSTANT = 8.314  # J/(mol·K)
ACTIVATION_ENERGY = 83144  # J/mol (~83.144 kJ/mol standard activation energy for pharmaceuticals)


def calculate_mkt(temperatures_celsius, weights=None):
    """
    Calculate Mean Kinetic Temperature (MKT) in Celsius.

    Input:
        temperatures_celsius: List of temperature readings in Celsius.
        weights: Optional list of interval durations (e.g., minutes) corresponding
                 to each reading for time-weighted MKT calculation.

    Output:
        MKT in Celsius as a float.
    """
    if not temperatures_celsius:
        raise ValueError("Temperature readings cannot be empty.")

    kelvin_values = []
    for idx, t in enumerate(temperatures_celsius):
        try:
            temp_float = float(t)
        except (ValueError, TypeError):
            raise ValueError(f"Reading at index {idx} ({t}) is not a valid numeric temperature.")

        k = temp_float + 273.15
        if k <= 0:
            raise ValueError(f"Temperature {t}°C is below or at absolute zero.")
        kelvin_values.append(k)

    exponent_factor = -ACTIVATION_ENERGY / GAS_CONSTANT

    if weights is not None:
        if len(weights) != len(kelvin_values):
            raise ValueError("Length of weights must match length of temperatures.")

        validated_weights = []
        for idx, w in enumerate(weights):
            try:
                w_val = float(w)
            except (ValueError, TypeError):
                raise ValueError(f"Weight at index {idx} ({w}) is not a valid number.")
            if w_val < 0:
                raise ValueError(f"Weight at index {idx} ({w}) cannot be negative.")
            validated_weights.append(w_val)

        total_weight = sum(validated_weights)
        if total_weight <= 0:
            raise ValueError("Total weight must be strictly positive.")

        mean_value = sum(
            w * math.exp(exponent_factor / temp_k)
            for w, temp_k in zip(validated_weights, kelvin_values)
        ) / total_weight
    else:
        mean_value = sum(
            math.exp(exponent_factor / temp_k)
            for temp_k in kelvin_values
        ) / len(kelvin_values)

    if mean_value <= 0:
        raise ValueError("Mathematical domain error in MKT calculation.")

    mkt_kelvin = exponent_factor / math.log(mean_value)
    return mkt_kelvin - 273.15


def validate_mkt(mkt_celsius, min_mkt=None, max_mkt=None):
    """
    Validate that an MKT value complies with upper and lower temperature specifications.

    Returns:
        dict with validation results:
        {
            "valid": bool,
            "mkt": float,
            "min_mkt": float or None,
            "max_mkt": float or None,
            "violation": "EXCEEDED_MAX" | "SUB_MIN" | None,
            "reason": str or None
        }
    """
    if mkt_celsius is None:
        return {
            "valid": True,
            "mkt": None,
            "min_mkt": min_mkt,
            "max_mkt": max_mkt,
            "violation": None,
            "reason": None
        }

    try:
        mkt_val = float(mkt_celsius)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid MKT value: {mkt_celsius}")

    if max_mkt is not None and mkt_val > max_mkt:
        return {
            "valid": False,
            "mkt": round(mkt_val, 2),
            "min_mkt": min_mkt,
            "max_mkt": max_mkt,
            "violation": "EXCEEDED_MAX",
            "reason": f"MKT of {mkt_val:.2f}°C exceeds maximum permitted limit ({max_mkt:.2f}°C)."
        }

    if min_mkt is not None and mkt_val < min_mkt:
        return {
            "valid": False,
            "mkt": round(mkt_val, 2),
            "min_mkt": min_mkt,
            "max_mkt": max_mkt,
            "violation": "SUB_MIN",
            "reason": f"MKT of {mkt_val:.2f}°C is below minimum permitted limit ({min_mkt:.2f}°C)."
        }

    return {
        "valid": True,
        "mkt": round(mkt_val, 2),
        "min_mkt": min_mkt,
        "max_mkt": max_mkt,
        "violation": None,
        "reason": None
    }
