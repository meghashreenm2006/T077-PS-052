"""
SQLAlchemy Database Layer — Cold-Chain Compliance Engine.

Team ID: T077  |  Problem Statement: PS-052

This module creates a local SQLite database (coldchain.db) that stores
all shipment runs, decisions, excursions, penalties, and claims
so the dashboard always has real data to display.
"""

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Integer, Float, Boolean,
    DateTime, Text, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session

# ---------------------------------------------------------------------------
# Engine — stored right inside the project folder for easy demonstration
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "coldchain.db")
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class DBRun(Base):
    """One execution of the compliance engine over a dataset."""
    __tablename__ = "runs"

    run_id      = Column(String, primary_key=True)
    label       = Column(String, default="")
    created_at  = Column(DateTime, default=datetime.utcnow)
    status      = Column(String, default="complete")

    shipments    = relationship("DBShipment",   back_populates="run", cascade="all, delete-orphan")
    decisions    = relationship("DBDecision",   back_populates="run", cascade="all, delete-orphan")
    excursions   = relationship("DBExcursion",  back_populates="run", cascade="all, delete-orphan")
    penalties    = relationship("DBPenalty",    back_populates="run", cascade="all, delete-orphan")
    claims       = relationship("DBClaim",      back_populates="run", cascade="all, delete-orphan")
    certificates = relationship("DBCertificate",back_populates="run", cascade="all, delete-orphan")


class DBShipment(Base):
    """One shipment row from shipments.csv."""
    __tablename__ = "shipments"
    __table_args__ = (UniqueConstraint("run_id", "shipment_id"),)

    id               = Column(Integer, primary_key=True, autoincrement=True)
    run_id           = Column(String, ForeignKey("runs.run_id"))
    shipment_id      = Column(String)
    origin_city      = Column(String)
    destination_city = Column(String)
    planned_departure= Column(String)
    insured_value    = Column(Float)
    logger_owner     = Column(String)

    run = relationship("DBRun", back_populates="shipments")


class DBDecision(Base):
    """One compliance decision row (one per consignment per evaluation)."""
    __tablename__ = "decisions"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String, ForeignKey("runs.run_id"))
    shipment_id        = Column(String)
    consignment_id     = Column(String)
    profile_id         = Column(String)
    evaluation_no      = Column(Integer)
    cumulative_minutes = Column(Float)
    excursion_count    = Column(Integer)
    mkt_c              = Column(Float)
    decision           = Column(String)   # RELEASE / QUARANTINE / REJECT
    reason_codes       = Column(String)

    run = relationship("DBRun", back_populates="decisions")


class DBExcursion(Base):
    """One temperature excursion or data-gap event."""
    __tablename__ = "excursions"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    run_id              = Column(String, ForeignKey("runs.run_id"))
    shipment_id         = Column(String)
    excursion_no        = Column(Integer)
    type                = Column(String)   # HIGH / LOW / DATA_GAP
    start_ts            = Column(String)
    end_ts              = Column(String)
    duration_minutes    = Column(Float)
    max_temp_c          = Column(String)
    leg_no              = Column(Integer)
    party               = Column(String)
    counts_toward_limit = Column(String)

    run = relationship("DBRun", back_populates="excursions")


class DBPenalty(Base):
    """Carrier penalty per transport leg."""
    __tablename__ = "penalties"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String, ForeignKey("runs.run_id"))
    shipment_id        = Column(String)
    leg_no             = Column(Integer)
    carrier_id         = Column(String)
    attributed_minutes = Column(Float)
    minute_penalty     = Column(Float)
    precool_penalty    = Column(Float)
    cap_applied        = Column(String)
    penalty_total      = Column(Float)

    run = relationship("DBRun", back_populates="penalties")


class DBClaim(Base):
    """Claim liability allocation row."""
    __tablename__ = "claims"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    run_id            = Column(String, ForeignKey("runs.run_id"))
    shipment_id       = Column(String)
    consignment_id    = Column(String)
    claim_value       = Column(Float)
    party             = Column(String)
    attributed_minutes= Column(Float)
    share_before_cap  = Column(Float)
    share_after_cap   = Column(Float)

    run = relationship("DBRun", back_populates="claims")


class DBCertificate(Base):
    """Release certificate (only generated for RELEASE decisions)."""
    __tablename__ = "certificates"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    run_id             = Column(String, ForeignKey("runs.run_id"))
    shipment_id        = Column(String)
    consignment_id     = Column(String)
    released_at        = Column(String)
    cumulative_minutes = Column(Float)
    mkt_c              = Column(String)
    certificate_text   = Column(Text)

    run = relationship("DBRun", back_populates="certificates")


class DBReading(Base):
    """Temperature readings per shipment (for Chart.js graphs)."""
    __tablename__ = "readings"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    run_id       = Column(String, ForeignKey("runs.run_id"))
    shipment_id  = Column(String)
    reading_ts   = Column(String)
    temperature_c= Column(Float)


# ---------------------------------------------------------------------------
# Create all tables (safe to call multiple times)
# ---------------------------------------------------------------------------
def init_db():
    Base.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
