"""
Excursion and Data Gap Detection for Temperature Logger Readings.

Detects out-of-spec temperature periods (including ongoing/trailing excursions)
and missing data transmission gaps.
"""

from datetime import datetime


def parse_reading(reading):
    """
    Safely validate and parse a single (timestamp, temperature) reading tuple.
    Accepts datetime objects or standard ISO timestamp strings.
    """
    if not isinstance(reading, (tuple, list)) or len(reading) < 2:
        raise ValueError(f"Invalid reading format; expected (timestamp, temperature): {reading}")

    ts, temp = reading[0], reading[1]

    if isinstance(ts, str):
        parsed = None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(ts, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            try:
                parsed = datetime.fromisoformat(ts)
            except Exception:
                raise ValueError(f"Cannot parse timestamp string: '{ts}'")
        ts = parsed
    elif not isinstance(ts, datetime):
        raise ValueError(f"Timestamp must be a datetime or valid date string, got: {type(ts)}")

    try:
        temp_float = float(temp)
    except (ValueError, TypeError):
        raise ValueError(f"Temperature reading must be numeric, got: '{temp}'")

    return ts, temp_float


def remove_duplicates(readings):
    """
    Safely validate and sort readings chronologically by timestamp.
    Keep the first reading when duplicate timestamps are encountered.
    Discards any conflicting later readings at the identical timestamp.
    """
    if not readings:
        return []

    parsed_readings = [parse_reading(r) for r in readings]
    sorted_readings = sorted(parsed_readings, key=lambda x: x[0])

    unique_readings = []
    seen = set()

    for timestamp, temperature in sorted_readings:
        if timestamp not in seen:
            unique_readings.append((timestamp, temperature))
            seen.add(timestamp)

    return unique_readings


def detect_excursions(readings, min_temp, max_temp):
    """
    Detect periods when temperature goes outside the permitted temperature range.

    Accurately captures both closed excursions and trailing excursions that
    persist through the final logger reading.

    Returns a list of excursion records:
    [
        {
            "start": datetime,
            "end": datetime,
            "duration_minutes": float,
            "type": "HIGH" | "LOW",
            "peak_temp": float,
            "reading_count": int,
            "ongoing": bool
        },
        ...
    ]
    """
    if not readings:
        return []

    cleaned = remove_duplicates(readings)
    if not cleaned:
        return []

    excursions = []
    start_time = None
    excursion_type = None
    peak_temp = None
    reading_count = 0

    for i, (timestamp, temperature) in enumerate(cleaned):
        is_high = temperature > max_temp
        is_low = temperature < min_temp
        outside_range = is_high or is_low

        if outside_range:
            current_type = "HIGH" if is_high else "LOW"

            if start_time is None:
                start_time = timestamp
                excursion_type = current_type
                peak_temp = temperature
                reading_count = 1
            elif excursion_type != current_type:
                # Direct switch between high and low excursion
                duration = (timestamp - start_time).total_seconds() / 60.0
                excursions.append({
                    "start": start_time,
                    "end": timestamp,
                    "duration_minutes": duration,
                    "type": excursion_type,
                    "peak_temp": peak_temp,
                    "reading_count": reading_count,
                    "ongoing": False
                })
                start_time = timestamp
                excursion_type = current_type
                peak_temp = temperature
                reading_count = 1
            else:
                reading_count += 1
                if excursion_type == "HIGH":
                    peak_temp = max(peak_temp, temperature)
                else:
                    peak_temp = min(peak_temp, temperature)

        elif start_time is not None:
            # Temperature returned to compliant range
            duration = (timestamp - start_time).total_seconds() / 60.0
            excursions.append({
                "start": start_time,
                "end": timestamp,
                "duration_minutes": duration,
                "type": excursion_type,
                "peak_temp": peak_temp,
                "reading_count": reading_count,
                "ongoing": False
            })
            start_time = None
            excursion_type = None
            peak_temp = None
            reading_count = 0

    # FIX: Capture ongoing excursion trailing at the end of the logger series
    if start_time is not None and cleaned:
        final_timestamp = cleaned[-1][0]
        duration = (final_timestamp - start_time).total_seconds() / 60.0
        excursions.append({
            "start": start_time,
            "end": final_timestamp,
            "duration_minutes": duration,
            "type": excursion_type,
            "peak_temp": peak_temp,
            "reading_count": reading_count,
            "ongoing": True
        })

    return excursions


def detect_data_gaps(readings, max_gap_minutes=15.0):
    """
    Detect missing data periods where the interval between consecutive
    readings exceeds max_gap_minutes.

    Safely handles duplicate timestamps, out-of-order readings, and irregular sampling.
    """
    if max_gap_minutes <= 0:
        raise ValueError(f"max_gap_minutes must be strictly positive, got {max_gap_minutes}")

    if not readings or len(readings) < 2:
        return []

    cleaned = remove_duplicates(readings)
    if len(cleaned) < 2:
        return []

    gaps = []
    for i in range(1, len(cleaned)):
        prev_time = cleaned[i - 1][0]
        curr_time = cleaned[i][0]

        interval_minutes = (curr_time - prev_time).total_seconds() / 60.0
        if interval_minutes > max_gap_minutes:
            gaps.append({
                "start": prev_time,
                "end": curr_time,
                "duration_minutes": round(interval_minutes, 2)
            })

    return gaps
