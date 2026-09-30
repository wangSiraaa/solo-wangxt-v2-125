# -*- coding: utf-8 -*-
"""模型层解析/数值核对用例测试（不依赖数据库与网络）。"""
import math

import numpy as np
import pytest

from app import dispersion as disp
from app.gaussian import (ModelError, PlumeInputs, build_grid, concentration_g_m3,
                          evaluate_grid, local_offsets, transport_bearing_deg)


def make(**kw):
    base = dict(Q_g_s=100.0, hs_m=60.0, dh_m=20.0, u_ref_m_s=4.0,
                wind_from_deg=180.0, stability="D", receptor_z_m=2.0)
    base.update(kw)
    return PlumeInputs(**base)


class TestCalmWind:
    def test_calm_wind_rejected_with_explicit_code(self):
        p = make(u_ref_m_s=0.3)
        with pytest.raises(ModelError) as ei:
            concentration_g_m3(p, np.array([500.0]), np.array([0.0]))
        assert ei.value.code == "CALM_WIND"
        assert "静风" in ei.value.message

    def test_zero_wind_rejected(self):
        p = make(u_ref_m_s=0.0)
        with pytest.raises(ModelError) as ei:
            concentration_g_m3(p, np.array([500.0]), np.array([0.0]))
        assert ei.value.code == "CALM_WIND"

    def test_threshold_accepted_and_finite(self):
        p = make(u_ref_m_s=disp.WIND_SPEED_MIN)
        c = concentration_g_m3(p, np.array([500.0]), np.array([0.0]))
        assert np.all(np.isfinite(c))

    def test_grid_endpoint_also_rejects_calm(self):
        p = make(u_ref_m_s=0.1)
        with pytest.raises(ModelError) as ei:
            evaluate_grid(p, 1000.0, 50.0)
        assert ei.value.code == "CALM_WIND"


class TestAnalyticSymmetry:
    @pytest.mark.parametrize("stab", ["A", "C", "D", "E", "F"])
    def test_crosswind_mirror_equality(self, stab):
        p = make(stability=stab)
        xs = np.array([200.0, 800.0, 2500.0, 8000.0])
        for y in (12.5, 57.0, 133.0):
            cp = concentration_g_m3(p, xs, np.full_like(xs, y))
            cn = concentration_g_m3(p, xs, np.full_like(xs, -y))
            assert np.allclose(cp, cn, rtol=1e-12, atol=0.0)

    def test_axis_is_crosswind_maximum(self):
        p = make()
        x = np.full(11, 1000.0)
        ys = np.linspace(-300, 300, 11)
        c = concentration_g_m3(p, x, ys)
        assert c[5] == pytest.approx(c.max())


class TestDownwindDecay:
    def test_far_field_monotone_decay(self):
        p = make()
        xs = np.linspace(2000.0, 10000.0, 200)
        c = concentration_g_m3(p, xs, np.zeros_like(xs))
        assert np.all(np.diff(c) < 0)

    def test_elevated_source_rises_then_falls(self):
        p = make(hs_m=80.0, dh_m=0.0)
        xs = np.linspace(100.0, 10000.0, 900)
        c = concentration_g_m3(p, xs, np.zeros_like(xs))
        i = int(np.argmax(c))
        assert 0 < i < len(c) - 1
        assert c[0] < c[i] and c[-1] < c[i]

    def test_upwind_is_zero_not_negative(self):
        p = make()
        c = concentration_g_m3(p, np.array([-500.0, -1.0]), np.zeros(2))
        assert np.all(c == 0.0)


class TestStackHeight:
    @pytest.mark.parametrize("stab", ["D", "F"])
    def test_higher_stack_lower_ground_max(self, stab):
        xs = np.linspace(100.0, 10000.0, 1000)
        peaks_c, peaks_x = [], []
        for hs in (30.0, 60.0, 120.0):
            p = make(hs_m=hs, dh_m=0.0, stability=stab)
            c = concentration_g_m3(p, xs, np.zeros_like(xs))
            i = int(np.argmax(c))
            peaks_c.append(c[i])
            peaks_x.append(xs[i])
        assert peaks_c[0] > peaks_c[1] > peaks_c[2]
        assert peaks_x[0] < peaks_x[1] < peaks_x[2]

    def test_emission_linearity(self):
        # 线性模型：源强加倍，浓度加倍
        xs = np.array([300.0, 1200.0, 5000.0])
        c1 = concentration_g_m3(make(Q_g_s=100.0), xs, np.zeros(3))
        c2 = concentration_g_m3(make(Q_g_s=200.0), xs, np.zeros(3))
        assert np.allclose(c2, 2 * c1, rtol=1e-12)

    def test_wind_speed_effect(self):
        # 风速越大，整体浓度越低（1/u 依赖）
        xs = np.array([500.0, 2000.0])
        c_slow = concentration_g_m3(make(u_ref_m_s=2.0), xs, np.zeros(2))
        c_fast = concentration_g_m3(make(u_ref_m_s=8.0), xs, np.zeros(2))
        assert np.all(c_slow > c_fast)


class TestStability:
    def test_stable_narrower_plume_near_axis(self):
        # 稳定 F 的横向衰减比不稳定 A 更陡
        x = np.full(11, 1000.0)
        ys = np.linspace(0, 400, 11)
        cF = concentration_g_m3(make(stability="F"), x, ys)
        cA = concentration_g_m3(make(stability="A"), x, ys)
        ratioF = cF[-1] / cF[0]
        ratioA = cA[-1] / cA[0]
        assert ratioF < ratioA


class TestWindGeometry:
    @pytest.mark.parametrize("frm,to", [(0, 180), (90, 270), (180, 0),
                                        (270, 90), (360, 180), (450, 270)])
    def test_bearing_opposite(self, frm, to):
        assert transport_bearing_deg(frm) == pytest.approx(to % 360 or 0.0)

    def test_local_offsets_roundtrip_at_equator(self):
        east, north = local_offsets(np.array([0.001]), np.array([0.0]), 0.0, 0.0)
        assert east[0] == pytest.approx(math.radians(0.001) * 6_371_000)
        assert north[0] == pytest.approx(0.0, abs=1e-6)


class TestGrid:
    def test_resolution_changes_sampling_not_inputs(self):
        p = make()
        c50, *_ = evaluate_grid(p, 1500.0, 50.0)
        c25, *_ = evaluate_grid(p, 1500.0, 25.0)
        # 峰值来自同一模型，细化网格不应改变物理结果超过离散误差
        assert np.nanmax(c25) == pytest.approx(np.nanmax(c50), rel=0.05)
        assert c25.size > c50.size

    def test_oob_cells_are_nan_and_counted(self):
        # 50 m 分辨率才能采样到 (0,100) m 的近源无效带
        p = make()
        c, xd, yc, info = evaluate_grid(p, 6000.0, 50.0)
        assert info["n_out_of_range_nan"] > 0
        # 距源 <100 m 的正下风向单元必须是 NaN（不是巨大数字）
        near = c[(xd > 0) & (xd < 100.0)]
        assert near.size > 0
        assert np.all(np.isnan(near))

    def test_grid_size_limits(self):
        with pytest.raises(ModelError) as ei:
            build_grid(6000.0, 25.0)  # 481 点，超 251 上限
        assert ei.value.code == "GRID_TOO_LARGE"

    def test_too_fine_rejected(self):
        with pytest.raises(ModelError) as ei:
            build_grid(500.0, 5.0)
        assert ei.value.code in {"GRID_TOO_LARGE", "GRID_TOO_FINE"}


class TestBriggsCoefficients:
    """对显式参数做直接数值核对，防止公式被悄悄改动。"""
    def test_sigma_growth_with_x(self):
        for stab in disp.STABILITY_CLASSES:
            s1 = disp.sigma_y(np.array([200.0]), stab)[0]
            s2 = disp.sigma_y(np.array([2000.0]), stab)[0]
            assert s2 > s1 > 0

    def test_unstable_grows_faster_than_stable(self):
        x = np.array([1000.0])
        assert (disp.sigma_z(x, "A")[0] > disp.sigma_z(x, "F")[0])
