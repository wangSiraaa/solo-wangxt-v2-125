# -*- coding: utf-8 -*-
"""显式参数化：扩散系数与风廓线。

本模块把教学用高斯烟羽模型依赖的 *全部* 经验参数集中列出，
便于课堂检查，不藏在代码逻辑里。

参数来源（教科书级近似，非法规参数）：
- Briggs (1973) 乡村条件扩散系数公式，转引自 Turner / 常用大气扩散教材。
- 风速幂指数 p：乡村地形 Pasquill 稳定度对照表。

适用范围（超出只做外推并打标记，不声称有效）：
- 平坦乡村地形、地面粗糙度小
- 下风向距离 x ∈ [100, 10000] m
- 稳态风、定常排放
"""
from __future__ import annotations

import math

# 稳定度类别（Pasquill 1961），A=极不稳定 … F=较稳定
STABILITY_CLASSES = ("A", "B", "C", "D", "E", "F")

STABILITY_LABELS = {
    "A": "A 强不稳定",
    "B": "B 不稳定",
    "C": "C 弱不稳定",
    "D": "D 中性",
    "E": "E 较稳定",
    "F": "F 稳定",
}

# ---------------------------------------------------------------------------
# Briggs 乡村扩散系数（x 单位 m，σ 单位 m）
#
#   σy = a * x / (1 + b*x)**0.5
#   σz = c * x / (1 + d*x)**e
#
# 每个系数都是显式常数，便于逐条核对、逐条在界面上展示。
# ---------------------------------------------------------------------------
BRIGGS_RURAL: dict[str, dict[str, float]] = {
    #          a_sigmay  b_sigmay   c_sigmaz  d_sigmaz  e_sigmaz
    "A": dict(a=0.22, b=0.0001, c=0.20, d=0.0, e=1.0),
    "B": dict(a=0.16, b=0.0001, c=0.12, d=0.0, e=1.0),
    "C": dict(a=0.11, b=0.0001, c=0.08, d=0.0002, e=0.5),
    "D": dict(a=0.08, b=0.0001, c=0.06, d=0.0015, e=0.5),
    "E": dict(a=0.06, b=0.0001, c=0.03, d=0.0003, e=1.0),
    "F": dict(a=0.04, b=0.0001, c=0.016, d=0.0003, e=1.0),
}

# Briggs 曲线经验有效的下风向距离区间（m）
X_VALID_MIN = 100.0
X_VALID_MAX = 10_000.0

# 幂指数风廓线 u(H) = u_ref * (H / z_ref) ** p （乡村，z_ref = 10 m）
WIND_PROFILE_P = {
    "A": 0.15,
    "B": 0.15,
    "C": 0.20,
    "D": 0.25,
    "E": 0.30,
    "F": 0.30,
}
WIND_PROFILE_REF_HEIGHT_M = 10.0

# 模型硬性有效范围（界面与 API 共用，超出直接拒绝，不静默默认化）
WIND_SPEED_MIN = 0.5      # m/s，低于此按静风处理，拒绝计算
WIND_SPEED_MAX = 50.0     # m/s
STACK_HEIGHT_MIN = 1.0    # m
STACK_HEIGHT_MAX = 500.0  # m
PLUME_RISE_MIN = 0.0
PLUME_RISE_MAX = 500.0
EMISSION_RATE_MIN = 0.0   # g/s
EMISSION_RATE_MAX = 1.0e7
RECEPTOR_Z_MIN = 0.0
RECEPTOR_Z_MAX = 500.0

# 角度约定：气象风向 = 风 *吹来的方向*，0=北风，顺时针
WIND_FROM_MIN = 0.0
WIND_FROM_MAX = 360.0  # 允许 360.0，等价 0.0


def sigma_y(x, stability: str):
    """横向扩散系数 σy(x)，向量化。x: m（下风向距离），返回 m。"""
    t = BRIGGS_RURAL[stability]
    return t["a"] * x / (1.0 + t["b"] * x) ** 0.5


def sigma_z(x, stability: str):
    """垂直扩散系数 σz(x)，向量化。x: m，返回 m。"""
    t = BRIGGS_RURAL[stability]
    return t["c"] * x / (1.0 + t["d"] * x) ** t["e"]


def wind_speed_at_height(u_ref: float, height_m: float, stability: str) -> float:
    """幂指数风廓线：把参考高度（10 m）风速换算到给定高度。

    高度低于参考高度时不向下外推，直接取参考高度风速，
    避免对低矮源人为造风。
    """
    z_ref = WIND_PROFILE_REF_HEIGHT_M
    h = max(float(height_m), z_ref)
    return float(u_ref) * (h / z_ref) ** WIND_PROFILE_P[stability]


def normalise_wind_from(deg: float) -> float:
    """把风向归一化到 [0, 360)。"""
    d = float(deg) % 360.0
    return 0.0 if math.isclose(d, 360.0) else d
