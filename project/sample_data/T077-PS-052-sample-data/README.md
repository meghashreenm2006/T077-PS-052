# PS-052 – Cold-Chain Shipment Temperature Compliance and Claims Engine — Sample Data Pack

Prepared by 10 SECONDS for Team T077.

Domain: Logistics — Cold Chain. Build the compliance back-end a pharma and frozen-food 3PL uses to track shipments through legs and hand-offs, ingest temperature logger readings, evaluate excursions against product profiles with allowed cumulative time-out-of-range, decide release or rejection of each consignment, and settle claims among shipper, carrier and 3PL. Quality managers use it to release stock with a full excursion record. Command-file driven; no UI.

## Files

| File | What it holds | Rows |
|---|---|---|
| `profiles.csv` | Product temperature profiles | 5 |
| `shipments.csv` | Shipments (20) | 20 |
| `consignments.csv` | Consignments per shipment (1–3), each with its own profile | 34 |
| `legs.csv` | Legs per shipment in order; a leg's end_ts is the next leg's start_ts | 57 |
| `handoffs.csv` | Hand-off records between consecutive legs | 37 |
| `readings_shp_001.csv` | Logger readings for SHP-001 (2-minute cadence) | 422 |
| `readings_shp_002.csv` | Logger readings for SHP-002 (2-minute cadence) | 468 |
| `readings_shp_003.csv` | Logger readings for SHP-003 (2-minute cadence) | 962 |
| `readings_shp_004.csv` | Logger readings for SHP-004 (2-minute cadence) | 451 |
| `readings_shp_005.csv` | Logger readings for SHP-005 (2-minute cadence) | 542 |
| `readings_shp_006.csv` | Logger readings for SHP-006 (2-minute cadence) | 241 |
| `readings_shp_007.csv` | Logger readings for SHP-007 (2-minute cadence) | 481 |
| `readings_shp_008.csv` | Logger readings for SHP-008 (2-minute cadence) | 421 |
| `readings_shp_009.csv` | Logger readings for SHP-009 (2-minute cadence) | 571 |
| `readings_shp_010.csv` | Logger readings for SHP-010 (2-minute cadence) | 661 |
| `readings_shp_011.csv` | Logger readings for SHP-011 (2-minute cadence) | 271 |
| `readings_shp_012.csv` | Logger readings for SHP-012 (2-minute cadence) | 781 |
| `readings_shp_013.csv` | Logger readings for SHP-013 (2-minute cadence) | 721 |
| `readings_shp_014.csv` | Logger readings for SHP-014 (2-minute cadence) | 1052 |
| `readings_shp_015.csv` | Logger readings for SHP-015 (2-minute cadence) | 271 |
| `readings_shp_016.csv` | Logger readings for SHP-016 (2-minute cadence) | 721 |
| `readings_shp_017.csv` | Logger readings for SHP-017 (2-minute cadence) | 661 |
| `readings_shp_018.csv` | Logger readings for SHP-018 (2-minute cadence) | 841 |
| `readings_shp_019.csv` | Logger readings for SHP-019 (2-minute cadence) | 601 |
| `readings_shp_020.csv` | Logger readings for SHP-020 (2-minute cadence) | 481 |
| `commands.txt` | Command file; process strictly in file order. | 65 |

Row counts exclude the header line (CSV) and comment lines (commands.txt).

## Column reference

Conventions: dates `YYYY-MM-DD`; timestamps `YYYY-MM-DD HH:MM:SS` (24h, IST, no timezone suffix); money in Rs as plain decimals with at most 2 decimals (no commas, no symbol); percentages as plain numbers (12.5 = 12.5%); booleans `true`/`false`; IDs uppercase with a fixed prefix.

### `profiles.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `profile_id` | string | PRF-nn |  | Primary key |
| `name` | string |  |  |  |
| `range_min_c` | decimal | deg C |  | Lower bound of the in-range band (inclusive) |
| `range_max_c` | decimal | deg C |  | Upper bound (inclusive): a reading equal to the bound is in range |
| `hard_min_c` | decimal | deg C |  | A reading strictly below this → REJECT |
| `hard_max_c` | decimal | deg C |  | A reading strictly above this → REJECT; equal is NOT beyond |
| `allowed_excursion_minutes` | integer | minutes | >0 | Cumulative allowance across all legs |
| `allowed_excursion_count` | integer | count | >0 | Qualifying (>= 5 min) excursions allowed |
| `mkt_limit_c` | decimal | deg C |  | Mean kinetic temperature limit; above → QUARANTINE |

### `shipments.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `shipment_id` | string | SHP-nnn |  | Primary key |
| `origin_city` | string |  |  |  |
| `destination_city` | string |  |  |  |
| `planned_departure` | timestamp |  |  | Equals leg 1 start |
| `insured_value` | decimal | Rs |  | Per-party liability cap (Rs 10 lakh) |
| `logger_owner` | enum |  | CARRIER/3PL | CARRIER → DATA_GAP minutes penalised at double rate |

### `consignments.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `consignment_id` | string | SHP-nnn-Cn |  | Primary key |
| `shipment_id` | string |  | shipments.csv | FK |
| `profile_id` | string |  | profiles.csv | FK |
| `product` | string |  |  |  |
| `lot_no` | string |  |  |  |
| `value_rs` | decimal | Rs | >0 | Claimed on REJECT |

### `legs.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `leg_id` | string | SHP-nnn-Ln |  | Primary key |
| `shipment_id` | string |  | shipments.csv | FK |
| `leg_no` | integer |  | 1..4 |  |
| `carrier_id` | string | CAR-nn |  | Party liable for the leg |
| `vehicle_type` | enum |  | REEFER/PASSIVE_BOX | Rs 50 / Rs 20 per minute |
| `start_ts` | timestamp |  |  | Leg window start (inclusive) |
| `end_ts` | timestamp |  |  | Leg window end (exclusive, = hand-off time) |
| `freight_charge` | decimal | Rs | >0 | Penalty cap = 20% of this |

### `handoffs.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `shipment_id` | string |  | shipments.csv | FK |
| `from_leg_no` | integer |  |  |  |
| `to_leg_no` | integer |  |  |  |
| `handoff_ts` | timestamp |  |  | Normally equals from-leg end_ts; the 10-minute window after it is attributed to the 3PL |
| `receiving_party` | string | CAR-nn |  | Carrier of the receiving leg |
| `signature_flag` | boolean |  | true/false | false → chain-of-custody QUARANTINE |

### `readings_shp_001.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_002.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_003.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_004.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_005.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_006.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_007.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_008.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_009.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_010.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_011.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_012.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_013.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_014.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_015.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_016.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_017.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_018.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_019.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### `readings_shp_020.csv`

| Column | Type | Units / format | Allowed values | Notes |
|---|---|---|---|---|
| `reading_ts` | timestamp | YYYY-MM-DD HH:MM:SS |  | Logger time; file may be unsorted and may contain duplicates |
| `temperature_c` | decimal | deg C, 1 decimal |  | One absurd value (999.9) planted; treat as invalid reading |

### General notes

- Where the brief is silent: readings are instantaneous; an excursion still open at the last reading closes at the last reading timestamp; MKT uses every valid reading of the shipment (including duplicates removed); money to 2 decimals, MKT to 2 decimals.

## Command file format

`commands.txt` holds one command per line in the form `COMMAND_NAME|arg1|arg2|...`. Commands MUST be processed strictly in file order. Lines starting with `#` are comments and blank lines are ignored. Every command used in this pack, with its argument order:

| Command | Arguments (in order) | Meaning |
|---|---|---|
| `LOAD_PROFILES` | `file` | Load profiles |
| `LOAD_SHIPMENTS` | `shipments|consignments|legs|handoffs` | Load shipment master files |
| `INGEST_READINGS` | `shipment_id|file` | Ingest the logger file (sort, de-duplicate, detect gaps) |
| `RE_ICE` | `shipment_id|handoff_ts` | Re-icing at the hand-off: resets the excursion counter for PASSIVE_BOX legs that follow |
| `EVALUATE` | `shipment_id` | Run excursion detection, decisions, penalties and claims for the shipment |
| `OVERRIDE_CUSTODY` | `shipment_id|reason` | Manual override of a chain-of-custody QUARANTINE |
| `PRINT_REPORTS` | `shipment_id` | Write the excursion report, release certificate and claim settlement rows for the shipment |

## Planted scenarios

Every edge case from the brief is planted at the location given. Line numbers count the header as line 1 for CSVs and count every physical line (including comments) for commands.txt.

- **EC1: Two readings at the same timestamp with different temperatures** — readings_shp_001.csv lines 62–63: both stamped 2026-10-01 12:00:00 with 5.0 then 9.0 C — keep the first (in range), so no excursion opens
- **EC2: Gap of exactly 15 minutes** — readings_shp_002.csv: reading at 2026-10-02 19:32:00 is followed by 2026-10-02 19:47:00 (exactly 15 min → NOT a DATA_GAP); later 2026-10-02 22:52:00 → 2026-10-02 23:08:00 (16 min → DATA_GAP of 16 minutes)
- **EC3: Excursion of exactly 5 minutes (count vs cumulative)** — readings_shp_003.csv: out-of-range at 2026-10-04 04:24:00, 2026-10-04 04:26:00, 2026-10-04 04:28:00; first in-range at 2026-10-04 04:29:00 → duration exactly 5 min (counts toward count AND minutes); contrast: 2026-10-04 07:44:00→2026-10-04 07:50:00 = 6 min
- **EC4: Reading exactly at the hard limit** — readings_shp_004.csv: 2026-10-05 09:36:00 reads exactly 15.0 C = hard_max_c of PRF-01 (not beyond → no REJECT; it is an ordinary excursion reading)
- **EC5: Excursion starting 1 second before hand-off time** — readings_shp_005.csv: reading at 2026-10-06 19:47:59 (1 s before hand-off 2026-10-06 19:48:00) opens an excursion that runs to 2026-10-06 20:08:00 → attribute the first second to leg 1, the next 10 min to the 3PL hand-off window, the rest to leg 2
- **EC6: Cumulative minutes exactly equal to allowance with MKT above limit** — SHP-006 (PRF-01, allowance 120 min): excursions 2026-10-08 00:00:00→2026-10-08 01:10:00 (70 min) and 2026-10-08 04:00:00→2026-10-08 04:50:00 (50 min) = exactly 120 min (passes minutes) but MKT ≈ 9.94 C > 8.0 limit → QUARANTINE
- **EC7: Liability split where one leg's cap is hit and remainder must be redistributed** — SHP-007 (PRF-02): hard breach at 2026-10-09 07:42:00 (-14.0 C) → REJECT; consignment SHP-007-C1 value 1800000.00; leg 1 carries 150 excursion minutes, leg 2 50 minutes (75/25) → leg 1 share 13,50,000 is capped at insured 10,00,000 and the 3,50,000 remainder is redistributed to leg 2 (4,50,000 + 3,50,000 = 8,00,000)
- **EC8: Shipment with one reefer leg and one passive-box leg with RE_ICE** — SHP-008: leg 1 REEFER with three 10-min excursions, hand-off at 2026-10-10 17:24:00 with RE_ICE at commands.txt line 19, then leg 2 PASSIVE_BOX with two 12-min excursions → counter resets to 0 at RE_ICE for the passive leg only; cumulative minutes (30 + 24 = 54) are not reset
- **Extra: hand-off recorded before previous leg's last reading** — handoffs.csv SHP-009 leg 1→2 handoff_ts is 12 minutes before leg 1 end_ts → QUARANTINE until OVERRIDE_CUSTODY at commands.txt line 23; the second EVALUATE re-decides
- **Extra: hand-off without receiving signature** — handoffs.csv SHP-010 leg 1→2 has signature_flag=false → QUARANTINE (no override is given)
- **Extra: insufficient pre-cool** — readings_shp_011.csv: leg 2 starts 2026-10-14 11:00:00 with out-of-range readings in its first 10 minutes → INSUFFICIENT_PRECOOL, flat Rs 2,000 to leg 2 carrier plus minute penalties
- **Extra: unsorted readings file** — readings_shp_012.csv lines 121–125 are 5 readings that belong 40 lines earlier; sort by time before evaluating
- **Extra: invalid temperature value** — readings_shp_013.csv line 72 reads 999.9 C → invalid reading: ignore it for excursions and MKT but treat the surrounding interval as a gap if > 15 min (here it is 4 min, so no gap)
- **Extra: exact duplicate line** — readings_shp_014.csv lines 52–53 are identical → keep the first
- **Extra: partial release** — SHP-015 has SHP-015-C1 (PRF-01, 120 min) and SHP-015-C2 (PRF-03, 90 min, count 2); the shared excursion 2026-10-19 14:08:00→2026-10-19 15:48:00 is 100 min → C1 RELEASE, C2 REJECT/QUARANTINE per your minutes rule (exceeds 90)
- **Extra: clear hard-limit breach** — readings_shp_016.csv: 2026-10-21 02:00:00 reads 10.5 C, above hard_max_c → REJECT regardless of duration
- **Extra: random short excursions** — Shipments without a special plant may contain one 8–30 minute excursion; every excursion must still be listed and attributed

## What is NOT in this pack

Expected outputs are not provided for this set. Validate your engine with your own test suite against the rules in your brief (BR-01 … BR-nn). A separate hidden input set with the same schema will be used at final evaluation; outputs are compared field-for-field, so follow the column formats above exactly in your own output.

## Output format expected at evaluation

Produce these files (CSV, header row, same conventions as above, rows in the order stated). Numeric columns must be plain decimals with exactly the decimals stated.

### `excursions.csv`

One row per excursion (including DATA_GAP and split parts), ordered by shipment_id then start_ts.

Columns in order: `shipment_id`, `excursion_no`, `type`, `start_ts`, `end_ts`, `duration_minutes`, `max_temp_c`, `leg_no`, `party`, `counts_toward_limit`

### `decisions.csv`

One row per consignment per EVALUATE, in command order.

Columns in order: `shipment_id`, `consignment_id`, `profile_id`, `evaluation_no`, `cumulative_minutes`, `excursion_count`, `mkt_c`, `decision`, `reason_codes`

### `penalties.csv`

Carrier penalties per leg.

Columns in order: `shipment_id`, `leg_no`, `carrier_id`, `attributed_minutes`, `minute_penalty`, `precool_penalty`, `cap_applied`, `penalty_total`

### `claims.csv`

Claim split per party for REJECTED consignments.

Columns in order: `shipment_id`, `consignment_id`, `claim_value`, `party`, `attributed_minutes`, `share_before_cap`, `share_after_cap`

### `release_certificates.csv`

One row per RELEASED consignment.

Columns in order: `shipment_id`, `consignment_id`, `released_at`, `cumulative_minutes`, `mkt_c`, `certificate_text`
