"""
FastAPI Application — Cold-Chain Shipment Temperature Compliance and Claims Engine.

Team ID:          T077
Problem Statement: PS-052

Endpoints (backward-compatible with the original api.py skeleton):
  POST   /api/run                                   Upload CSV files and execute evaluation
  GET    /api/runs/{run_id}/shipments               List evaluated shipments
  GET    /api/runs/{run_id}/shipments/{shipment_id} Shipment detail with decisions
  GET    /api/runs/{run_id}/outputs/{filename}      Download generated output CSV
  GET    /api/runs/{run_id}/audit                   Full audit information

New endpoints (Phase 5/6 — connected to real sample data):
  GET    /api/dashboard                             Live summary stats from the database
  GET    /api/shipments                             All shipments across all runs
  GET    /api/shipments/{shipment_id}/readings      Temperature readings for Chart.js
  GET    /api/shipments/{shipment_id}/detail        Full shipment detail from DB
  GET    /api/reports/excursions                    All excursion events
  GET    /api/reports/claims                        All claim rows
  GET    /api/reports/penalties                     All penalty rows
  GET    /api/reports/certificates                  All release certificates
  GET    /api/reports/quarantine                    Quarantine deviation report
  GET    /api/reports/claim-invoice/{shipment_id}   Claim invoice for one shipment
  GET    /                                          Serves the dashboard HTML

The compliance engine is fully independent of FastAPI and also runs from the CLI.
"""

import io
import os
import csv
import uuid
import shutil
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from src.compliance_engine import ComplianceEngine
from src.database import (
    init_db, get_session,
    DBRun, DBShipment, DBDecision, DBExcursion,
    DBPenalty, DBClaim, DBCertificate, DBReading,
)

logger = logging.getLogger("coldchain")

# =============================================================================
# App Setup
# =============================================================================

app = FastAPI(
    title="PS-052 Cold-Chain Compliance Engine",
    description="Cold-Chain Shipment Temperature Compliance and Claims Engine — Team T077",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (HTML/CSS/JS dashboard)
_STATIC_DIR = Path(__file__).parent / "static"
_STATIC_DIR.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# In-memory run store (for file download; DB holds permanent data)
RUNS: Dict[str, dict] = {}
RUNS_DIR = Path(os.getenv("RUNS_DIR", "runs"))
RUNS_DIR.mkdir(exist_ok=True)

# Sample data directory (always try both locations)
_SAMPLE_DATA_DIR = Path(__file__).parent.parent / "sample_data" / "T077-PS-052-sample-data"


# =============================================================================
# Pydantic Models (Phase 5)
# =============================================================================

class ExcursionRow(BaseModel):
    shipment_id: str
    excursion_no: int
    type: str
    start_ts: str
    end_ts: str
    duration_minutes: float
    max_temp_c: str
    leg_no: int
    party: str
    counts_toward_limit: str


class DecisionRow(BaseModel):
    shipment_id: str
    consignment_id: str
    profile_id: str
    evaluation_no: int
    cumulative_minutes: float
    excursion_count: int
    mkt_c: str
    decision: str
    reason_codes: str


class PenaltyRow(BaseModel):
    shipment_id: str
    leg_no: int
    carrier_id: str
    attributed_minutes: float
    minute_penalty: float
    precool_penalty: float
    cap_applied: str
    penalty_total: float


class ClaimRow(BaseModel):
    shipment_id: str
    consignment_id: str
    claim_value: float
    party: str
    attributed_minutes: float
    share_before_cap: float
    share_after_cap: float


class CertificateRow(BaseModel):
    shipment_id: str
    consignment_id: str
    released_at: str
    cumulative_minutes: float
    mkt_c: str
    certificate_text: str


class ShipmentSummary(BaseModel):
    shipment_id: str
    decisions: List[Dict[str, Any]] = Field(default_factory=list)
    excursion_count: int = 0
    penalty_total: float = 0.0
    claim_total: float = 0.0
    certificate_count: int = 0


class RunSummary(BaseModel):
    run_id: str
    created_at: str
    shipment_count: int
    total_excursions: int
    total_decisions: int
    total_penalties: int
    total_claims: int
    total_certificates: int
    status: str


class AuditResponse(BaseModel):
    run_id: str
    decisions: List[Dict[str, Any]]
    excursions: List[Dict[str, Any]]
    penalties: List[Dict[str, Any]]
    claims: List[Dict[str, Any]]
    certificates: List[Dict[str, Any]]


# =============================================================================
# Startup: initialise DB and auto-load sample data
# =============================================================================

SAMPLE_RUN_ID = "sample-run-T077-PS052"


@app.on_event("startup")
def startup_event():
    """
    Called once when the server starts.
    1. Creates the SQLite database tables (if they don't exist).
    2. Checks whether the sample data has already been loaded.
    3. If not, runs the compliance engine over all 20 sample shipments
       and stores every result in the database.
    """
    init_db()
    _ensure_sample_data_loaded()


def _ensure_sample_data_loaded():
    """Load sample data once into the database on first startup."""
    with get_session() as session:
        existing = session.get(DBRun, SAMPLE_RUN_ID)
        if existing:
            logger.info("Sample data already loaded — skipping.")
            return

    commands_path = _SAMPLE_DATA_DIR / "commands.txt"
    if not commands_path.exists():
        logger.warning(f"Sample commands.txt not found at {commands_path}")
        return

    logger.info("Loading sample data into database for the first time …")
    try:
        engine_obj = ComplianceEngine(data_dir=str(_SAMPLE_DATA_DIR))
        engine_obj.execute_command_file(str(commands_path))

        # Export CSVs to output/
        out_dir = Path(__file__).parent.parent / "output"
        engine_obj.export_all_csvs(str(out_dir))

        # Persist to DB
        _persist_run(SAMPLE_RUN_ID, "Sample Run — 20 Shipments", engine_obj)
        logger.info("Sample data loaded successfully.")
    except Exception as exc:
        logger.error(f"Failed to load sample data: {exc}", exc_info=True)


def _persist_run(run_id: str, label: str, engine_obj: ComplianceEngine):
    """Write all engine results into the SQLite database."""
    with get_session() as session:
        # Run record
        db_run = DBRun(run_id=run_id, label=label, created_at=datetime.utcnow(), status="complete")
        session.add(db_run)

        # Shipments
        for sid, s in engine_obj.shipments.items():
            session.add(DBShipment(
                run_id=run_id,
                shipment_id=sid,
                origin_city=s["origin_city"],
                destination_city=s["destination_city"],
                planned_departure=str(s["planned_departure"]),
                insured_value=s["insured_value"],
                logger_owner=s["logger_owner"],
            ))

        # Decisions
        for d in engine_obj.output_decisions:
            session.add(DBDecision(
                run_id=run_id,
                shipment_id=d["shipment_id"],
                consignment_id=d["consignment_id"],
                profile_id=d["profile_id"],
                evaluation_no=int(d["evaluation_no"]),
                cumulative_minutes=float(d["cumulative_minutes"]),
                excursion_count=int(d["excursion_count"]),
                mkt_c=float(d["mkt_c"]) if d["mkt_c"] != "N/A" else 0.0,
                decision=d["decision"],
                reason_codes=d["reason_codes"],
            ))

        # Excursions
        for e in engine_obj.output_excursions:
            session.add(DBExcursion(
                run_id=run_id,
                shipment_id=e["shipment_id"],
                excursion_no=int(e["excursion_no"]),
                type=e["type"],
                start_ts=e["start_ts"],
                end_ts=e["end_ts"],
                duration_minutes=float(e["duration_minutes"]),
                max_temp_c=str(e["max_temp_c"]),
                leg_no=int(e["leg_no"]),
                party=e["party"],
                counts_toward_limit=e["counts_toward_limit"],
            ))

        # Penalties
        for p in engine_obj.output_penalties:
            session.add(DBPenalty(
                run_id=run_id,
                shipment_id=p["shipment_id"],
                leg_no=int(p["leg_no"]),
                carrier_id=p["carrier_id"],
                attributed_minutes=float(p["attributed_minutes"]),
                minute_penalty=float(p["minute_penalty"]),
                precool_penalty=float(p["precool_penalty"]),
                cap_applied=p["cap_applied"],
                penalty_total=float(p["penalty_total"]),
            ))

        # Claims
        for c in engine_obj.output_claims:
            session.add(DBClaim(
                run_id=run_id,
                shipment_id=c["shipment_id"],
                consignment_id=c["consignment_id"],
                claim_value=float(c["claim_value"]),
                party=c["party"],
                attributed_minutes=float(c["attributed_minutes"]),
                share_before_cap=float(c["share_before_cap"]),
                share_after_cap=float(c["share_after_cap"]),
            ))

        # Certificates
        for cert in engine_obj.output_certificates:
            session.add(DBCertificate(
                run_id=run_id,
                shipment_id=cert["shipment_id"],
                consignment_id=cert["consignment_id"],
                released_at=cert["released_at"],
                cumulative_minutes=float(cert["cumulative_minutes"]),
                mkt_c=str(cert["mkt_c"]),
                certificate_text=cert["certificate_text"],
            ))

        # Temperature readings (for Chart.js graphs)
        for sid, reading_list in engine_obj.readings.items():
            for ts, temp in reading_list:
                if abs(temp - 999.9) > 0.01:  # skip invalid sentinel readings
                    session.add(DBReading(
                        run_id=run_id,
                        shipment_id=sid,
                        reading_ts=ts.strftime("%Y-%m-%d %H:%M:%S"),
                        temperature_c=temp,
                    ))

        session.commit()


# =============================================================================
# Helper
# =============================================================================

def _get_run(run_id: str) -> dict:
    if run_id not in RUNS:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return RUNS[run_id]


async def _save_upload(upload: UploadFile, dest_dir: Path) -> Path:
    dest = dest_dir / upload.filename
    contents = await upload.read()
    dest.write_bytes(contents)
    return dest


# =============================================================================
# Dashboard HTML — serves the frontend
# =============================================================================

@app.get("/", response_class=HTMLResponse, summary="Serve dashboard")
def serve_dashboard():
    html_path = _STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found. Check src/static/index.html</h1>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# =============================================================================
# Phase 6 — Dashboard summary API (uses real DB data)
# =============================================================================

@app.get("/api/dashboard", summary="Live dashboard summary stats")
def get_dashboard():
    """Returns aggregated stats for the main dashboard page."""
    with get_session() as session:
        from sqlalchemy import func, select

        total_shipments = session.query(DBShipment).filter(DBShipment.run_id == SAMPLE_RUN_ID).count()

        # Decision breakdown
        decisions = session.query(DBDecision).filter(DBDecision.run_id == SAMPLE_RUN_ID).all()
        decision_counts = {"RELEASE": 0, "QUARANTINE": 0, "REJECT": 0}
        for d in decisions:
            decision_counts[d.decision] = decision_counts.get(d.decision, 0) + 1

        # Excursions
        excursions = session.query(DBExcursion).filter(
            DBExcursion.run_id == SAMPLE_RUN_ID,
            DBExcursion.type != "DATA_GAP"
        ).all()
        total_excursions = len(excursions)
        total_excursion_minutes = sum(e.duration_minutes for e in excursions)

        # Penalties
        penalties = session.query(DBPenalty).filter(DBPenalty.run_id == SAMPLE_RUN_ID).all()
        total_penalty = sum(p.penalty_total for p in penalties)

        # Claims
        claims = session.query(DBClaim).filter(DBClaim.run_id == SAMPLE_RUN_ID).all()
        total_claim = sum(c.share_after_cap for c in claims)

        # Certificates
        total_certificates = session.query(DBCertificate).filter(
            DBCertificate.run_id == SAMPLE_RUN_ID
        ).count()

        # Data gaps
        data_gaps = session.query(DBExcursion).filter(
            DBExcursion.run_id == SAMPLE_RUN_ID,
            DBExcursion.type == "DATA_GAP"
        ).count()

        # Per-shipment summary for status cards
        shipments = session.query(DBShipment).filter(DBShipment.run_id == SAMPLE_RUN_ID).all()
        shipment_cards = []
        for shp in shipments:
            sid = shp.shipment_id
            shp_decisions = [d for d in decisions if d.shipment_id == sid]
            # Overall status = worst decision
            status = "RELEASE"
            for d in shp_decisions:
                if d.decision == "REJECT":
                    status = "REJECT"
                    break
                elif d.decision == "QUARANTINE":
                    status = "QUARANTINE"
            shp_excursions = [e for e in excursions if e.shipment_id == sid]
            shp_penalties = [p for p in penalties if p.shipment_id == sid]
            shipment_cards.append({
                "shipment_id": sid,
                "origin": shp.origin_city,
                "destination": shp.destination_city,
                "status": status,
                "excursion_count": len(shp_excursions),
                "penalty_total": sum(p.penalty_total for p in shp_penalties),
            })

        return {
            "total_shipments": total_shipments,
            "decision_counts": decision_counts,
            "total_excursions": total_excursion_minutes,
            "total_excursion_events": total_excursions,
            "total_data_gaps": data_gaps,
            "total_penalty_rs": round(total_penalty, 2),
            "total_claim_rs": round(total_claim, 2),
            "total_certificates": total_certificates,
            "shipment_cards": shipment_cards,
        }


# =============================================================================
# Phase 6 — Temperature readings for Chart.js
# =============================================================================

@app.get("/api/shipments/{shipment_id}/readings", summary="Temperature readings for a shipment")
def get_readings(shipment_id: str):
    """Returns time-series temperature data suitable for Chart.js line graphs."""
    with get_session() as session:
        rows = (
            session.query(DBReading)
            .filter(DBReading.run_id == SAMPLE_RUN_ID, DBReading.shipment_id == shipment_id)
            .order_by(DBReading.reading_ts)
            .all()
        )
        if not rows:
            raise HTTPException(status_code=404, detail=f"No readings for {shipment_id}")
        return {
            "shipment_id": shipment_id,
            "labels": [r.reading_ts for r in rows],
            "temperatures": [r.temperature_c for r in rows],
        }


# =============================================================================
# Phase 6 — Full shipment detail from DB
# =============================================================================

@app.get("/api/shipments/{shipment_id}/detail", summary="Full shipment detail from database")
def get_shipment_detail(shipment_id: str):
    """Returns everything about one shipment: decisions, excursions, penalties, claims, certificates."""
    with get_session() as session:
        shp = (
            session.query(DBShipment)
            .filter(DBShipment.run_id == SAMPLE_RUN_ID, DBShipment.shipment_id == shipment_id)
            .first()
        )
        if not shp:
            raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

        def _rows(cls, **filters):
            q = session.query(cls).filter(cls.run_id == SAMPLE_RUN_ID, cls.shipment_id == shipment_id)
            return [row.__dict__ for row in q.all()]

        decisions_raw = session.query(DBDecision).filter(
            DBDecision.run_id == SAMPLE_RUN_ID, DBDecision.shipment_id == shipment_id
        ).all()
        excursions_raw = session.query(DBExcursion).filter(
            DBExcursion.run_id == SAMPLE_RUN_ID, DBExcursion.shipment_id == shipment_id
        ).all()
        penalties_raw = session.query(DBPenalty).filter(
            DBPenalty.run_id == SAMPLE_RUN_ID, DBPenalty.shipment_id == shipment_id
        ).all()
        claims_raw = session.query(DBClaim).filter(
            DBClaim.run_id == SAMPLE_RUN_ID, DBClaim.shipment_id == shipment_id
        ).all()
        certs_raw = session.query(DBCertificate).filter(
            DBCertificate.run_id == SAMPLE_RUN_ID, DBCertificate.shipment_id == shipment_id
        ).all()

        def _to_dict(obj):
            d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
            d.pop("_sa_instance_state", None)
            return d

        # Overall status
        all_decisions = [d.decision for d in decisions_raw]
        if "REJECT" in all_decisions:
            status = "REJECT"
        elif "QUARANTINE" in all_decisions:
            status = "QUARANTINE"
        else:
            status = "RELEASE"

        return {
            "shipment_id": shp.shipment_id,
            "origin_city": shp.origin_city,
            "destination_city": shp.destination_city,
            "planned_departure": shp.planned_departure,
            "insured_value": shp.insured_value,
            "logger_owner": shp.logger_owner,
            "status": status,
            "decisions": [_to_dict(d) for d in decisions_raw],
            "excursions": [_to_dict(e) for e in excursions_raw],
            "penalties": [_to_dict(p) for p in penalties_raw],
            "claims": [_to_dict(c) for c in claims_raw],
            "certificates": [_to_dict(c) for c in certs_raw],
        }


# =============================================================================
# Phase 4 — Reports and Certificates
# =============================================================================

@app.get("/api/reports/excursions", summary="All excursion events across all shipments")
def report_excursions():
    with get_session() as session:
        rows = session.query(DBExcursion).filter(DBExcursion.run_id == SAMPLE_RUN_ID).all()
        return [
            {
                "shipment_id": r.shipment_id,
                "excursion_no": r.excursion_no,
                "type": r.type,
                "start_ts": r.start_ts,
                "end_ts": r.end_ts,
                "duration_minutes": r.duration_minutes,
                "max_temp_c": r.max_temp_c,
                "leg_no": r.leg_no,
                "party": r.party,
                "counts_toward_limit": r.counts_toward_limit,
            }
            for r in rows
        ]


@app.get("/api/reports/claims", summary="All claim liability rows")
def report_claims():
    with get_session() as session:
        rows = session.query(DBClaim).filter(DBClaim.run_id == SAMPLE_RUN_ID).all()
        return [
            {
                "shipment_id": r.shipment_id,
                "consignment_id": r.consignment_id,
                "claim_value": r.claim_value,
                "party": r.party,
                "attributed_minutes": r.attributed_minutes,
                "share_before_cap": r.share_before_cap,
                "share_after_cap": r.share_after_cap,
            }
            for r in rows
        ]


@app.get("/api/reports/penalties", summary="All carrier penalty rows")
def report_penalties():
    with get_session() as session:
        rows = session.query(DBPenalty).filter(DBPenalty.run_id == SAMPLE_RUN_ID).all()
        return [
            {
                "shipment_id": r.shipment_id,
                "leg_no": r.leg_no,
                "carrier_id": r.carrier_id,
                "attributed_minutes": r.attributed_minutes,
                "minute_penalty": r.minute_penalty,
                "precool_penalty": r.precool_penalty,
                "cap_applied": r.cap_applied,
                "penalty_total": r.penalty_total,
            }
            for r in rows
        ]


@app.get("/api/reports/certificates", summary="All release certificates")
def report_certificates():
    with get_session() as session:
        rows = session.query(DBCertificate).filter(DBCertificate.run_id == SAMPLE_RUN_ID).all()
        return [
            {
                "shipment_id": r.shipment_id,
                "consignment_id": r.consignment_id,
                "released_at": r.released_at,
                "cumulative_minutes": r.cumulative_minutes,
                "mkt_c": r.mkt_c,
                "certificate_text": r.certificate_text,
            }
            for r in rows
        ]


@app.get("/api/reports/quarantine", summary="Quarantine deviation report")
def report_quarantine():
    """Returns all shipments/consignments that received QUARANTINE or REJECT decisions."""
    with get_session() as session:
        rows = session.query(DBDecision).filter(
            DBDecision.run_id == SAMPLE_RUN_ID,
            DBDecision.decision.in_(["QUARANTINE", "REJECT"]),
        ).all()
        report = []
        for r in rows:
            shp = session.query(DBShipment).filter(
                DBShipment.run_id == SAMPLE_RUN_ID,
                DBShipment.shipment_id == r.shipment_id
            ).first()
            excursions = session.query(DBExcursion).filter(
                DBExcursion.run_id == SAMPLE_RUN_ID,
                DBExcursion.shipment_id == r.shipment_id,
                DBExcursion.type != "DATA_GAP",
            ).count()
            report.append({
                "shipment_id": r.shipment_id,
                "origin": shp.origin_city if shp else "?",
                "destination": shp.destination_city if shp else "?",
                "consignment_id": r.consignment_id,
                "profile_id": r.profile_id,
                "decision": r.decision,
                "reason_codes": r.reason_codes,
                "cumulative_excursion_minutes": r.cumulative_minutes,
                "excursion_events": excursions,
                "mkt_c": r.mkt_c,
            })
        return report


@app.get("/api/reports/claim-invoice/{shipment_id}", summary="Claim invoice for one shipment")
def report_claim_invoice(shipment_id: str):
    """Returns a claim invoice document for a rejected shipment."""
    with get_session() as session:
        shp = session.query(DBShipment).filter(
            DBShipment.run_id == SAMPLE_RUN_ID, DBShipment.shipment_id == shipment_id
        ).first()
        if not shp:
            raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

        claims = session.query(DBClaim).filter(
            DBClaim.run_id == SAMPLE_RUN_ID, DBClaim.shipment_id == shipment_id
        ).all()
        if not claims:
            return {
                "shipment_id": shipment_id,
                "message": "No claims raised for this shipment (no REJECT decisions).",
                "line_items": [],
                "total_claim_rs": 0.0,
            }

        line_items = [
            {
                "consignment_id": c.consignment_id,
                "responsible_party": c.party,
                "claim_value_rs": c.claim_value,
                "attributed_minutes": c.attributed_minutes,
                "share_before_cap_rs": c.share_before_cap,
                "share_after_cap_rs": c.share_after_cap,
            }
            for c in claims
        ]
        total = sum(c.share_after_cap for c in claims)
        return {
            "shipment_id": shipment_id,
            "origin": shp.origin_city,
            "destination": shp.destination_city,
            "insured_value_rs": shp.insured_value,
            "generated_at": datetime.utcnow().isoformat(),
            "line_items": line_items,
            "total_claim_rs": round(total, 2),
        }


# =============================================================================
# Original API endpoints (kept for backward compatibility)
# =============================================================================

@app.post("/api/run", response_model=RunSummary, summary="Upload CSV files and run evaluation")
async def run_evaluation(
    profiles: UploadFile = File(...),
    shipments: UploadFile = File(...),
    consignments: UploadFile = File(...),
    legs: UploadFile = File(...),
    handoffs: UploadFile = File(...),
    commands: UploadFile = File(...),
    readings: List[UploadFile] = File(default=[]),
):
    run_id = str(uuid.uuid4())
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True)

    try:
        for upload in [profiles, shipments, consignments, legs, handoffs, commands]:
            await _save_upload(upload, run_dir)
        for reading_file in readings:
            await _save_upload(reading_file, run_dir)

        eng = ComplianceEngine(data_dir=str(run_dir))
        eng.execute_command_file("commands.txt")

        out_dir = run_dir / "output"
        eng.export_all_csvs(str(out_dir))

        # Persist custom run to DB too
        _persist_run(run_id, f"Custom upload {run_id[:8]}", eng)

        RUNS[run_id] = {
            "run_id": run_id,
            "created_at": datetime.now().isoformat(),
            "engine": eng,
            "out_dir": str(out_dir),
            "status": "complete",
        }
        return RunSummary(
            run_id=run_id,
            created_at=RUNS[run_id]["created_at"],
            shipment_count=len(eng.shipments),
            total_excursions=len(eng.output_excursions),
            total_decisions=len(eng.output_decisions),
            total_penalties=len(eng.output_penalties),
            total_claims=len(eng.output_claims),
            total_certificates=len(eng.output_certificates),
            status="complete",
        )
    except Exception as exc:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc))


@app.get("/api/runs/{run_id}/shipments", response_model=List[ShipmentSummary])
def list_shipments(run_id: str):
    run = _get_run(run_id)
    engine: ComplianceEngine = run["engine"]
    summaries = {sid: ShipmentSummary(shipment_id=sid) for sid in engine.shipments}
    for d in engine.output_decisions:
        sid = d["shipment_id"]
        if sid in summaries:
            summaries[sid].decisions.append(d)
            summaries[sid].excursion_count += d["excursion_count"]
    for p in engine.output_penalties:
        sid = p["shipment_id"]
        if sid in summaries:
            summaries[sid].penalty_total += float(p["penalty_total"])
    for c in engine.output_claims:
        sid = c["shipment_id"]
        if sid in summaries:
            summaries[sid].claim_total += float(c["share_after_cap"])
    for cert in engine.output_certificates:
        sid = cert["shipment_id"]
        if sid in summaries:
            summaries[sid].certificate_count += 1
    return list(summaries.values())


@app.get("/api/runs/{run_id}/shipments/{shipment_id}")
def get_shipment(run_id: str, shipment_id: str):
    run = _get_run(run_id)
    engine: ComplianceEngine = run["engine"]
    if shipment_id not in engine.shipments:
        raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")
    return {
        "shipment": engine.shipments[shipment_id],
        "consignments": engine.consignments.get(shipment_id, []),
        "legs": engine.legs.get(shipment_id, []),
        "handoffs": engine.handoffs.get(shipment_id, []),
        "decisions": [d for d in engine.output_decisions if d["shipment_id"] == shipment_id],
        "excursions": [e for e in engine.output_excursions if e["shipment_id"] == shipment_id],
        "penalties": [p for p in engine.output_penalties if p["shipment_id"] == shipment_id],
        "claims": [c for c in engine.output_claims if c["shipment_id"] == shipment_id],
        "certificates": [c for c in engine.output_certificates if c["shipment_id"] == shipment_id],
    }


ALLOWED_OUTPUT_FILES = {
    "excursions.csv", "decisions.csv", "penalties.csv",
    "claims.csv", "release_certificates.csv",
}


@app.get("/api/runs/{run_id}/outputs/{filename}")
def download_output(run_id: str, filename: str):
    if filename not in ALLOWED_OUTPUT_FILES:
        raise HTTPException(status_code=400, detail=f"Unknown file '{filename}'")
    run = _get_run(run_id)
    file_path = Path(run["out_dir"]) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found for run {run_id}")

    def iter_file():
        with open(file_path, "rb") as f:
            yield from f

    return StreamingResponse(
        iter_file(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/runs/{run_id}/audit", response_model=AuditResponse)
def get_audit(run_id: str):
    run = _get_run(run_id)
    engine: ComplianceEngine = run["engine"]
    return AuditResponse(
        run_id=run_id,
        decisions=engine.output_decisions,
        excursions=engine.output_excursions,
        penalties=engine.output_penalties,
        claims=engine.output_claims,
        certificates=engine.output_certificates,
    )


@app.get("/api/health", summary="Health check")
def health():
    return {"status": "ok", "project": "PS-052", "team": "T077", "version": "2.0.0"}


# =============================================================================
# Entrypoint
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=False)
