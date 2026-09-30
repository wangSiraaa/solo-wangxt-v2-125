# -*- coding: utf-8 -*-
"""PostgreSQL/PostGIS 连接与仓储层（psycopg 3）。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg

DSN = os.environ.get(
    "PLUME_DSN",
    "postgresql://plume@/plume_lab?host=/tmp&port=55432",
)

SCHEMA_PATH = Path(__file__).with_name("schema.sql")


@contextmanager
def connect(dsn: str | None = None):
    conn = psycopg.connect(dsn or DSN, autocommit=False)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema(conn) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))
    # PostGIS 必须可用，否则直接失败而不是静默降级
    ver = conn.execute("SELECT postgis_version()").fetchone()[0]
    if not ver:
        raise RuntimeError("PostGIS 扩展未安装")


def is_seeded(conn) -> bool:
    n = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
    return n > 0


def seed(conn) -> dict:
    from .seed_data import SOURCES, MET_SCENARIOS

    if is_seeded(conn):
        return {"seeded": False, "reason": "already populated"}
    for s in SOURCES:
        conn.execute(
            """INSERT INTO sources
               (name, description, lon, lat, stack_height_m, plume_rise_m,
                emission_g_s, pollutant)
               VALUES (%(name)s, %(description)s, %(lon)s, %(lat)s,
                       %(stack_height_m)s, %(plume_rise_m)s,
                       %(emission_g_s)s, %(pollutant)s)""",
            s,
        )
    for m in MET_SCENARIOS:
        conn.execute(
            """INSERT INTO met_scenarios
               (name, description, wind_from_deg, wind_speed_10m_ms,
                stability_class, background_ug_m3, receptor_z_m)
               VALUES (%(name)s, %(description)s, %(wind_from_deg)s,
                       %(wind_speed_10m_ms)s, %(stability_class)s,
                       %(background_ug_m3)s, %(receptor_z_m)s)""",
            m,
        )
    return {"seeded": True, "sources": len(SOURCES), "met": len(MET_SCENARIOS)}


SOURCE_COLS = """id, name, description, lon, lat, stack_height_m,
                 plume_rise_m, emission_g_s, pollutant"""

MET_COLS = """id, name, description, wind_from_deg, wind_speed_10m_ms,
              stability_class, background_ug_m3, receptor_z_m"""


def list_sources(conn):
    rows = conn.execute(f"SELECT {SOURCE_COLS} FROM sources ORDER BY id").fetchall()
    keys = [c.strip().split()[0].strip(',') for c in SOURCE_COLS.split(',')]
    return [dict(zip(keys, r)) for r in rows]


def get_source(conn, source_id: int):
    row = conn.execute(
        f"SELECT {SOURCE_COLS} FROM sources WHERE id = %s", (source_id,)
    ).fetchone()
    if row is None:
        return None
    keys = [c.strip().split()[0].strip(',') for c in SOURCE_COLS.split(',')]
    return dict(zip(keys, row))


def list_met(conn):
    rows = conn.execute(f"SELECT {MET_COLS} FROM met_scenarios ORDER BY id").fetchall()
    keys = [c.strip().split()[0].strip(',') for c in MET_COLS.split(',')]
    return [dict(zip(keys, r)) for r in rows]


def get_met(conn, met_id: int):
    row = conn.execute(
        f"SELECT {MET_COLS} FROM met_scenarios WHERE id = %s", (met_id,)
    ).fetchone()
    if row is None:
        return None
    keys = [c.strip().split()[0].strip(',') for c in MET_COLS.split(',')]
    return dict(zip(keys, row))


def record_run(conn, *, source_id, met_id, grid_radius_m, resolution_m, unit,
               max_plume_ug_m3, warning) -> int:
    row = conn.execute(
        """INSERT INTO calc_runs
           (source_id, met_id, grid_radius_m, resolution_m, unit,
            max_plume_ug_m3, warning)
           VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        (source_id, met_id, grid_radius_m, resolution_m, unit,
         max_plume_ug_m3, warning),
    ).fetchone()
    return int(row[0])
