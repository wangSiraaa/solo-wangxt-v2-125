# -*- coding: utf-8 -*-
"""FastAPI 入口：离线高斯烟羽教学应用后端。

启动时自动建表（需要 PostGIS）并写入虚构数据。
所有结果明确标注为教学用途，不得用于事故预警或合规判定。
"""
from __future__ import annotations

import math
import os
from contextlib import asynccontextmanager
from pathlib import Path

import numpy as np
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import db, dispersion as disp, verification
from .gaussian import (EARTH_RADIUS_M, ModelError, PlumeInputs, evaluate_grid,
                       transport_bearing_deg)
from .models_api import PlumeRequest

DISCLAIMER = (
    "本结果为平坦地形、稳态风假设下的教学演示，使用虚构源项与气象参数，"
    "采用教科书级 Briggs 乡村扩散系数；仅用于课堂理解烟囱高度、风速与稳定度"
    "对地面浓度的影响。不得用于真实事故应急预警，也不得用于法规达标判定。"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db.connect() as conn:
        db.init_schema(conn)
        db.seed(conn)
    yield


app = FastAPI(title="plume-lab 离线高斯烟羽教学应用", version="1.0.0",
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


@app.exception_handler(ModelError)
async def model_error_handler(request: Request, exc: ModelError):
    return JSONResponse(status_code=422,
                        content={"error_code": exc.code,
                                 "message": exc.message,
                                 "details": exc.extra})


# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    with db.connect() as conn:
        pg = conn.execute("SELECT version()").fetchone()[0]
        postgis = conn.execute("SELECT postgis_version()").fetchone()[0]
        n_s = conn.execute("SELECT count(*) FROM sources").fetchone()[0]
        n_m = conn.execute("SELECT count(*) FROM met_scenarios").fetchone()[0]
    return {"status": "ok", "postgresql": pg, "postgis": postgis,
            "sources": n_s, "met_scenarios": n_m,
            "disclaimer": DISCLAIMER}


@app.get("/api/config")
def config():
    return {
        "stability_classes": list(disp.STABILITY_CLASSES),
        "stability_labels": disp.STABILITY_LABELS,
        "briggs_rural_coefficients": disp.BRIGGS_RURAL,
        "wind_profile_p_rural": disp.WIND_PROFILE_P,
        "wind_profile_ref_height_m": disp.WIND_PROFILE_REF_HEIGHT_M,
        "valid_ranges": {
            "wind_speed_10m_m_s": [disp.WIND_SPEED_MIN, disp.WIND_SPEED_MAX],
            "stack_height_m": [disp.STACK_HEIGHT_MIN, disp.STACK_HEIGHT_MAX],
            "plume_rise_m": [disp.PLUME_RISE_MIN, disp.PLUME_RISE_MAX],
            "emission_g_s": [disp.EMISSION_RATE_MIN, disp.EMISSION_RATE_MAX],
            "receptor_z_m": [disp.RECEPTOR_Z_MIN, disp.RECEPTOR_Z_MAX],
            "x_downwind_m": [disp.X_VALID_MIN, disp.X_VALID_MAX],
        },
        "grid": {
            "min_resolution_m": 10.0,
            "max_radius_m": 10_000.0,
            "max_cells_per_side": 251,
            "note": "分辨率只改变展示采样密度，不改变任何输入参数与模型公式。",
        },
        "concentration_units": [
            {"id": "ug/m3", "label": "µg/m³", "factor_from_g_m3": 1e6},
            {"id": "mg/m3", "label": "mg/m³", "factor_from_g_m3": 1e3},
            {"id": "g/m3", "label": "g/m³", "factor_from_g_m3": 1.0},
        ],
        "wind_convention": {
            "wind_from_deg": "气象风向=风的来向，0=北风，顺时针增加",
            "transport_bearing_deg": "输送方位=风吹去的方向=来向+180°（mod 360）",
            "x_downwind": "沿输送方向为正；上风向 x≤0，浓度为零",
            "y_crosswind": "面向下风向时左侧为正",
        },
        "calm_wind_policy": {
            "threshold_m_s": disp.WIND_SPEED_MIN,
            "rule": f"10 m 风速低于 {disp.WIND_SPEED_MIN} m/s 判定为静风，"
                    "拒绝计算并返回 CALM_WIND；绝不用近零风速产生虚假的巨大浓度。",
        },
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/sources")
def sources():
    with db.connect() as conn:
        return db.list_sources(conn)


@app.get("/api/met")
def met():
    with db.connect() as conn:
        return db.list_met(conn)


@app.get("/api/sources/geojson")
def sources_geojson():
    """由 PostGIS 直接输出 GeoJSON（3857 几何转回 4326 经纬度）。"""
    sql = """
        SELECT row_to_json(fc) FROM (
          SELECT 'FeatureCollection' AS type,
                 COALESCE(json_agg(feat), '[]'::json) AS features
          FROM (
            SELECT 'Feature' AS type,
                   ST_AsGeoJSON(ST_Transform(s.geom, 4326))::json AS geometry,
                   json_build_object(
                     'id', s.id, 'name', s.name,
                     'stack_height_m', s.stack_height_m,
                     'plume_rise_m', s.plume_rise_m,
                     'emission_g_s', s.emission_g_s,
                     'pollutant', s.pollutant) AS properties
            FROM sources s ORDER BY s.id
          ) feat
        ) fc;"""
    with db.connect() as conn:
        return conn.execute(sql).fetchone()[0]


@app.get("/api/coordinate-check")
def coordinate_check():
    """经纬度→Web Mercator→经纬度往返一致性，供课堂检查坐标转换。"""
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT id, lon, lat, merc_x, merc_y, back_lon, back_lat,
                      ABS(lon-back_lon) AS dlon_err, ABS(lat-back_lat) AS dlat_err
               FROM sources_coordinate_check ORDER BY id""").fetchall()
    keys = ["id", "lon", "lat", "merc_x", "merc_y", "back_lon", "back_lat",
            "dlon_err", "dlat_err"]
    return [dict(zip(keys, r)) for r in rows]


@app.get("/api/wind-geometry")
def wind_geometry(wind_from_deg: float):
    """单步检查风向转换：来向→输送方位，并给出 4 个检查点的 x/y。"""
    if not 0 <= wind_from_deg <= 360:
        raise ModelError("BAD_WIND_DIR", "风向须在 0–360 度之间")
    bearing = transport_bearing_deg(wind_from_deg)
    T = math.radians(bearing)
    checks = []
    # 以输送方位为基准的四个罗盘方向点（北/东/南/西由方位旋转判定）
    for label, east, north in [
        ("沿输送方向 500 m", 500.0 * math.sin(T), 500.0 * math.cos(T)),
        ("逆输送方向 500 m", -500.0 * math.sin(T), -500.0 * math.cos(T)),
        ("横风向左 500 m", -500.0 * math.cos(T), 500.0 * math.sin(T)),
        ("横风向右 500 m", 500.0 * math.cos(T), -500.0 * math.sin(T)),
    ]:
        xd = east * math.sin(T) + north * math.cos(T)
        yc = north * math.sin(T) - east * math.cos(T)
        checks.append({"label": label, "east_m": east, "north_m": north,
                       "x_downwind_m": xd, "y_crosswind_m": yc})
    return {"wind_from_deg": disp.normalise_wind_from(wind_from_deg),
            "transport_bearing_deg": bearing,
            "convention": "风向=来向，0=北，顺时针；输送方位=去向",
            "check_points": checks}


# ---------------------------------------------------------------------------
def _grid_geo_origin(lon0, lat0, radius_m, n):
    """返回网格四个角与角点经纬度（行序：北→南，列序：西→东）。"""
    lat0r = math.radians(lat0)
    half = radius_m

    def to_lonlat(east, north):
        lon = lon0 + math.degrees(east / (EARTH_RADIUS_M * math.cos(lat0r)))
        lat = lat0 + math.degrees(north / EARTH_RADIUS_M)
        return [lon, lat]

    return {
        "corner_nw": to_lonlat(-half, half),
        "corner_ne": to_lonlat(half, half),
        "corner_sw": to_lonlat(-half, -half),
        "corner_se": to_lonlat(half, -half),
    }


@app.post("/api/plume")
def plume(req: PlumeRequest):
    with db.connect() as conn:
        src = db.get_source(conn, req.source_id)
        met = db.get_met(conn, req.met_id)
    if src is None:
        raise ModelError("SOURCE_NOT_FOUND", f"排放源 id={req.source_id} 不存在")
    if met is None:
        raise ModelError("MET_NOT_FOUND", f"气象情景 id={req.met_id} 不存在")

    p = PlumeInputs(
        Q_g_s=src["emission_g_s"],
        hs_m=src["stack_height_m"],
        dh_m=src["plume_rise_m"],
        u_ref_m_s=met["wind_speed_10m_ms"],
        wind_from_deg=met["wind_from_deg"],
        stability=met["stability_class"],
        receptor_z_m=met["receptor_z_m"],
    )
    # 静风在此被显式拒绝（CALM_WIND），不会进入数值计算
    c_ug, xd, yc, grid_info = evaluate_grid(p, req.grid_radius_m, req.resolution_m)

    finite = c_ug[np.isfinite(c_ug)]
    imax = int(np.argmax(np.where(np.isfinite(c_ug), c_ug, -np.inf)))
    rmax, cmax = divmod(imax, c_ug.shape[1])

    # 网格角点经纬度与采样范围（前端画"采样范围框"，明确不是无限精度）
    n = c_ug.shape[0]
    extent = _grid_geo_origin(src["lon"], src["lat"], req.grid_radius_m, n)
    lat0r = math.radians(src["lat"])
    # [row,col] 中心经纬度辅助量
    m_per_deg_lat = EARTH_RADIUS_M
    m_per_deg_lon = EARTH_RADIUS_M * math.cos(lat0r)

    values = [None if not math.isfinite(v) else float(v)
              for v in c_ug.reshape(-1)]

    # 下风向轴线剖面（固定采样，供曲线核对，不随网格分辨率变化）
    xs = np.linspace(disp.X_VALID_MIN, disp.X_VALID_MAX, 180)
    prof = p  # noqa
    from .gaussian import concentration_g_m3
    profile_vals = concentration_g_m3(p, xs, np.zeros_like(xs)) * 1e6

    warning = None
    if finite.size == 0:
        warning = "采样范围内没有落在模型有效距离区间的单元"
    elif xd[rmax, cmax] > 0.9 * disp.X_VALID_MAX:
        warning = "浓度峰值接近有效距离上限，扩大采样半径也不会使结果更精确"

    run_payload = dict(
        source_id=src["id"], met_id=met["id"],
        grid_radius_m=req.grid_radius_m, resolution_m=req.resolution_m,
        unit=req.unit,
        max_plume_ug_m3=float(np.nanmax(c_ug)) if finite.size else None,
        warning=warning,
    )
    try:
        with db.connect() as conn:
            run_id = db.record_run(conn, **run_payload)
    except Exception:
        run_id = None

    return {
        "run_id": run_id,
        "source": src,
        "met": met,
        "source_term": {
            "Q_g_s": src["emission_g_s"],
            "Q_g_h": src["emission_g_s"] * 3600.0,
            "Q_kg_day": src["emission_g_s"] * 86.4,
            "pollutant": src["pollutant"],
            "stack_height_hs_m": src["stack_height_m"],
            "plume_rise_dh_m": src["plume_rise_m"],
            "effective_height_H_m": p.H_m,
        },
        "wind": {
            "wind_from_deg": met["wind_from_deg"],
            "transport_bearing_deg": p.transport_bearing_deg,
            "u_ref_10m_m_s": met["wind_speed_10m_ms"],
            "profile_exponent_p": disp.WIND_PROFILE_P[p.stability],
            "u_at_H_m_s": p.u_effective_m_s,
            "stability": p.stability,
            "stability_label": disp.STABILITY_LABELS[p.stability],
            "calm_threshold_m_s": disp.WIND_SPEED_MIN,
        },
        "concentration": {
            "canonical_unit": "ug/m3",
            "plume_only_ug_m3": "见 grid.values（仅烟羽贡献，不含背景）",
            "background_ug_m3": met["background_ug_m3"],
            "total_rule": "total = max(plume,0) + background；三部分在界面分开展示",
            "display_unit_requested": req.unit,
            "factor_from_ug_m3": {"ug/m3": 1.0, "mg/m3": 1e-3, "g/m3": 1e-6}[req.unit],
            "max_plume_ug_m3": run_payload["max_plume_ug_m3"],
            "max_total_ug_m3": (run_payload["max_plume_ug_m3"]
                                + met["background_ug_m3"])
            if run_payload["max_plume_ug_m3"] is not None else None,
        },
        "grid": {
            "nrows": int(c_ug.shape[0]),
            "ncols": int(c_ug.shape[1]),
            "resolution_m": req.resolution_m,
            "radius_m": req.grid_radius_m,
            "row_order": "north_to_south",
            "col_order": "west_to_east",
            "source_lonlat": [src["lon"], src["lat"]],
            "meters_per_degree": {"lat": m_per_deg_lat, "lon": m_per_deg_lon},
            "corner_lonlat": extent,
            "valid_x_range_m": [disp.X_VALID_MIN, disp.X_VALID_MAX],
            "sampling": {
                **grid_info,
                "nan_meaning": "该格点中心距源的下风向距离超出经验曲线有效区间 "
                               "[100,10000] m，按无效处理而非外推",
            },
            "values_ug_m3": values,
        },
        "centerline_profile": {
            "x_m": xs.tolist(),
            "plume_ug_m3": profile_vals.tolist(),
            "background_ug_m3": met["background_ug_m3"],
        },
        "model_validity": {
            "terrain": "平坦地形（局部平面近似）",
            "wind": "稳态、定常风向风速",
            "reflection": "地面全反射、无沉降无化学转化",
            "dispersion": "Briggs 乡村系数，x ∈ [100, 10000] m",
        },
        "warning": warning,
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/verification")
def verification_cases():
    return {"cases": verification.run_all(), "disclaimer": DISCLAIMER}


# 生产模式：托管前端构建产物（若存在）
_STATIC = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _STATIC.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="ui")
