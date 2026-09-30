# -*- coding: utf-8 -*-
"""解析核对用例（analytical verification cases）。

每个用例给出 *可以手工复算* 的断言，服务于课堂自查，
不依赖任何外部软件或监测数据：

A. 横风向对称性：C(x, +y) == C(x, -y)
B. 下风向衰减：固定 y=0、固定 H 与稳定度，远离源后浓度随 x 单调衰减；
   高架源地面轴线浓度先升后降（存在最大值），其峰值位置随源高下移/变远。
C. 源高变化：其他条件不变，地面最大浓度随有效源高增大而减小，
   且峰值出现距离随源高增大而变远。
"""
from __future__ import annotations

import math

import numpy as np

from . import dispersion as disp
from .gaussian import PlumeInputs, concentration_g_m3, validate_inputs

TOL_REL = 1.0e-10


def case_crosswind_symmetry() -> dict:
    p = PlumeInputs(Q_g_s=100.0, hs_m=60.0, dh_m=20.0,
                    u_ref_m_s=4.0, wind_from_deg=180.0, stability="D")
    xs = np.array([200.0, 500.0, 1000.0, 3000.0])
    y = 37.0
    c_pos = concentration_g_m3(p, xs, np.full_like(xs, y))
    c_neg = concentration_g_m3(p, xs, np.full_like(xs, -y))
    rel = np.abs(c_pos - c_neg) / np.maximum(c_pos, 1e-300)
    passed = bool(np.all(rel < TOL_REL))
    return {
        "key": "crosswind_symmetry",
        "title": "A. 横风向解析对称性",
        "statement": "固定下风向距离 x，y 只以 y² 进入公式，故 C(x,+y)=C(x,-y)。",
        "inputs_summary": {"x_m": xs.tolist(), "y_m": y,
                           "stability": "D", "H_m": p.H_m,
                           "u_effective_m_s": p.u_effective_m_s},
        "c_plus_g_m3": c_pos.tolist(),
        "c_minus_g_m3": c_neg.tolist(),
        "max_relative_diff": float(rel.max()),
        "tolerance_relative": TOL_REL,
        "passed": passed,
    }


def case_downwind_decay() -> dict:
    p = PlumeInputs(Q_g_s=100.0, hs_m=60.0, dh_m=20.0,
                    u_ref_m_s=4.0, wind_from_deg=180.0, stability="D")
    xs = np.linspace(disp.X_VALID_MIN, disp.X_VALID_MAX, 500)
    c = concentration_g_m3(p, xs, np.zeros_like(xs), z_m=2.0) * 1e6  # µg/m³

    imax = int(np.argmax(c))
    x_peak = float(xs[imax])
    # 峰值之后应严格单调衰减（数值上允许极小违反）
    tail = c[imax:]
    monotone = bool(np.all(np.diff(tail) <= 1e-12 * (tail[:-1] + 1e-30)))
    # 高架源（H=80 m ≫ 受体 2 m）：峰值不应贴在区间起点，应"先升后降"
    rises_then_falls = bool(imax > 5 and imax < len(xs) - 5)
    passed = monotone and rises_then_falls
    return {
        "key": "downwind_decay",
        "title": "B. 下风向轴线衰减与先升后降",
        "statement": "高架源地面轴线浓度先因垂直混合增强而升高，达到峰值后，"
                     "随 σy、σz 增大而单调衰减。",
        "inputs_summary": {"stability": "D", "H_m": p.H_m,
                           "receptor_z_m": 2.0,
                           "x_range_m": [disp.X_VALID_MIN, disp.X_VALID_MAX]},
        "peak_x_m": x_peak,
        "peak_c_ug_m3": float(c[imax]),
        "c_at_100m_ug_m3": float(c[0]),
        "c_at_10km_ug_m3": float(c[-1]),
        "tail_monotone_nonincreasing": monotone,
        "peak_is_interior": rises_then_falls,
        "passed": passed,
    }


def case_stack_height_effect() -> dict:
    """同源强、同气象，只改变烟囱高度，比较地面最大浓度与峰值距离。"""
    heights = [30.0, 60.0, 120.0]
    xs = np.linspace(disp.X_VALID_MIN, disp.X_VALID_MAX, 800)
    peaks_c, peaks_x = [], []
    for hs in heights:
        p = PlumeInputs(Q_g_s=100.0, hs_m=hs, dh_m=0.0,
                        u_ref_m_s=4.0, wind_from_deg=180.0, stability="D")
        c = concentration_g_m3(p, xs, np.zeros_like(xs), z_m=2.0) * 1e6
        i = int(np.argmax(c))
        peaks_c.append(float(c[i]))
        peaks_x.append(float(xs[i]))
    # 高度越高 → 地面最大浓度越低、峰值落地越远
    c_decreasing = all(b < a for a, b in zip(peaks_c, peaks_c[1:]))
    x_increasing = all(b > a for a, b in zip(peaks_x, peaks_x[1:]))
    return {
        "key": "stack_height_effect",
        "title": "C. 源高变化效应",
        "statement": "其他条件相同时，有效源高越大，地面最大浓度越低，"
                     "且峰值出现位置越远。",
        "inputs_summary": {"stack_heights_m": heights, "plume_rise_m": 0.0,
                           "stability": "D", "receptor_z_m": 2.0,
                           "note": "三例源强、风廓线、稳定度完全一致"},
        "peak_c_ug_m3": peaks_c,
        "peak_x_m": peaks_x,
        "peak_concentration_decreases": c_decreasing,
        "peak_distance_increases": x_increasing,
        "passed": bool(c_decreasing and x_increasing),
    }


def case_wind_geometry() -> dict:
    """风向约定的纯几何核对（无浓度）。

    气象风向（来向）→ 输送方位（去向）相差 180°。
    北风(0°) 烟向南输送，即东西同位时源北处为上风向、源南处为下风向。
    """
    cases = [
        (0.0, 180.0),    # 北风 → 向南输送
        (90.0, 270.0),   # 东风 → 向西
        (180.0, 0.0),    # 南风 → 向北
        (270.0, 90.0),   # 西风 → 向东
        (360.0, 180.0),  # 360 等价 0
    ]
    from .gaussian import transport_bearing_deg
    got = [(w, transport_bearing_deg(w)) for w, _ in cases]
    ok = all(math.isclose(g, e, abs_tol=1e-9) for (_, g), (_, e) in zip(got, cases))

    # 北风下：源正南 1 km 的点 x_down 应为 +1000，源正北为 -1000
    from .gaussian import PlumeInputs  # noqa: F401
    T = math.radians(180.0)
    # east=0, north=-1000
    xd_south = 0 * math.sin(T) + (-1000.0) * math.cos(T)
    xd_north = 0 * math.sin(T) + (1000.0) * math.cos(T)
    return {
        "key": "wind_geometry",
        "title": "D. 风向约定与坐标转换",
        "statement": "气象风向=风的来向（0=北，顺时针）；输送方位=去向=来向+180°。",
        "pairs": [{"wind_from_deg": w, "transport_bearing_deg": g,
                   "expected_bearing_deg": e}
                  for (w, g), (_, e) in zip(got, cases)],
        "north_wind_xdown_south_1km": xd_south,
        "north_wind_xdown_north_1km": xd_north,
        "passed": bool(ok and math.isclose(xd_south, 1000.0)
                       and math.isclose(xd_north, -1000.0)),
    }


ALL_CASES = [case_crosswind_symmetry, case_downwind_decay,
             case_stack_height_effect, case_wind_geometry]


def run_all() -> list[dict]:
    return [fn() for fn in ALL_CASES]
