# -*- coding: utf-8 -*-
"""API 端到端测试（需要 PostgreSQL/PostGIS，使用测试库）。"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault(
    "PLUME_DSN", "postgresql://plume@/plume_lab_test?host=/tmp&port=55432")

# 测试库若不存在则创建
import psycopg


def _ensure_test_db():
    try:
        adm = psycopg.connect("postgresql://plume@/postgres?host=/tmp&port=55432")
        adm.autocommit = True
        exists = adm.execute(
            "SELECT 1 FROM pg_database WHERE datname='plume_lab_test'").fetchone()
        if not exists:
            adm.execute("CREATE DATABASE plume_lab_test")
            with psycopg.connect(os.environ["PLUME_DSN"]) as c:
                c.execute("CREATE EXTENSION postgis")
                c.commit()
        adm.close()
    except Exception as e:
        pytest.skip(f"测试数据库不可用: {e}")


_ensure_test_db()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_postgis(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    j = r.json()
    assert j["status"] == "ok"
    assert "3.3" in j["postgis"]
    assert j["sources"] >= 3 and j["met_scenarios"] >= 6


def test_seed_idempotent(client):
    # lifespan 已播种；再次启动不应重复插入
    with TestClient(app) as c:
        n1 = c.get("/api/health").json()["sources"]
    with TestClient(app) as c:
        n2 = c.get("/api/health").json()["sources"]
    assert n1 == n2


def test_config_exposes_parameters(client):
    j = client.get("/api/config").json()
    assert set(j["briggs_rural_coefficients"]) == set("ABCDEF")
    assert j["calm_wind_policy"]["threshold_m_s"] == 0.5


def test_sources_and_geojson(client):
    sources = client.get("/api/sources").json()
    assert len(sources) == 3
    gj = client.get("/api/sources/geojson").json()
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) == 3
    g = gj["features"][0]["geometry"]
    assert g["type"] == "Point"
    assert len(g["coordinates"]) == 2


def test_coordinate_check_roundtrip(client):
    rows = client.get("/api/coordinate-check").json()
    assert len(rows) == 3
    for r in rows:
        assert abs(r["dlon_err"]) < 1e-9
        assert abs(r["dlat_err"]) < 1e-9


def test_wind_geometry(client):
    j = client.get("/api/wind-geometry", params={"wind_from_deg": 180}).json()
    assert j["transport_bearing_deg"] == 0.0
    down = j["check_points"][0]
    up = j["check_points"][1]
    assert down["x_downwind_m"] == pytest.approx(500.0)
    assert up["x_downwind_m"] == pytest.approx(-500.0)


def test_plume_normal_run(client):
    met = client.get("/api/met").json()
    neutral = next(m for m in met if m["stability_class"] == "D")
    r = client.post("/api/plume", json={
        "source_id": 1, "met_id": neutral["id"],
        "grid_radius_m": 2000, "resolution_m": 50})
    assert r.status_code == 200
    j = r.json()
    assert j["grid"]["nrows"] == j["grid"]["ncols"] == 81
    assert j["grid"]["nrows"] * j["grid"]["ncols"] == len(j["grid"]["values_ug_m3"])
    assert j["concentration"]["max_plume_ug_m3"] > 0
    # 三个浓度部分分别存在
    assert j["concentration"]["background_ug_m3"] >= 0
    assert j["concentration"]["max_total_ug_m3"] == pytest.approx(
        j["concentration"]["max_plume_ug_m3"]
        + j["concentration"]["background_ug_m3"])
    # 部分单元是 NaN（源附近 <100 m）
    assert j["grid"]["sampling"]["n_out_of_range_nan"] > 0
    assert any(v is None for v in j["grid"]["values_ug_m3"])


def test_plume_resolution_does_not_change_inputs(client):
    met = client.get("/api/met").json()
    neutral = next(m for m in met if m["stability_class"] == "D")
    out = []
    for res in (100.0, 50.0, 25.0):
        r = client.post("/api/plume", json={
            "source_id": 1, "met_id": neutral["id"],
            "grid_radius_m": 2000, "resolution_m": res})
        j = r.json()
        out.append((j["concentration"]["max_plume_ug_m3"], j["grid"]["nrows"],
                    j["wind"]["u_at_H_m_s"], j["source_term"]["effective_height_H_m"]))
        # 输入项不随分辨率改变
        assert j["source_term"]["Q_g_s"] == 50.0
    peaks = [o[0] for o in out]
    assert peaks[1] == pytest.approx(peaks[0], rel=0.05)
    assert peaks[2] == pytest.approx(peaks[0], rel=0.05)
    assert out[0][1] < out[1][1] < out[2][1]  # 格点更密
    # 风速换算与有效源高在三种分辨率下完全一致
    assert len({o[2] for o in out}) == 1
    assert len({o[3] for o in out}) == 1


def test_calm_wind_http_422(client):
    met = client.get("/api/met").json()
    calm = next(m for m in met if m["wind_speed_10m_ms"] < 0.5)
    r = client.post("/api/plume", json={
        "source_id": 1, "met_id": calm["id"],
        "grid_radius_m": 2000, "resolution_m": 50})
    assert r.status_code == 422
    j = r.json()
    assert j["error_code"] == "CALM_WIND"
    assert "静风" in j["message"]


def test_verification_cases_all_pass(client):
    j = client.get("/api/verification").json()
    assert len(j["cases"]) == 4
    for case in j["cases"]:
        assert case["passed"] is True, case["key"]


def test_stack_height_comparison_via_api(client):
    """源 1（45+15 m）与源 2（120+30 m）同 Q=50：高源地面峰值更低、更远。"""
    met = client.get("/api/met").json()
    neutral = next(m for m in met if m["stability_class"] == "D")

    def peak(sid):
        j = client.post("/api/plume", json={
            "source_id": sid, "met_id": neutral["id"],
            "grid_radius_m": 8000, "resolution_m": 100}).json()
        return j["concentration"]["max_plume_ug_m3"]

    assert peak(1) > peak(2)
