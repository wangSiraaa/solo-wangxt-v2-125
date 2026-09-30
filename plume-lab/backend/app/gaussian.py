# -*- coding: utf-8 -*-
"""稳态高斯烟羽模型（平坦地形、教学用途的显式参数化）。

公式（地面或任意受体高度 z，单一点源、全反射地面）：

    C(x, y, z) = Q / (2π u σy σz)
                 · exp( -y² / (2 σy²) )
                 · [ exp( -(z-H)² / (2 σz²) )      ← 烟羽本体
                   + exp( -(z+H)² / (2 σz²) ) ]    ← 地面全反射像源

约定（均可在 API 返回的 wind_geometry 中逐点检查）：
- x：下风向距离（沿风的输送方向），m，仅 x>0 有烟羽
- y：横风向距离（面向下风向时左侧为正），m
- z：受体离地高度，m
- H = 烟囱几何高度 hs + 烟气抬升高度 Δh，m
- u：H 高度处风速，由 10 m 参考风速按幂指数廓线换算
- Q：源强 g/s；浓度原生单位 g/m³

明确限制：
- 静风（u10 < 0.5 m/s）不做计算：稳态烟羽公式在 u→0 时发散，
  这不是物理上的"无限浓度"，而是模型失效，调用方会收到 CALM_WIND 错误。
- x 落在 Briggs 乡村曲线有效区间 [100, 10000] m 之外的网格单元不赋值
  （输出 NaN），而不是静默外推成看似精确的数字。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from . import dispersion as disp

EARTH_RADIUS_M = 6_371_000.0

# 网格规模上限，防止浏览器/API 被超大矩阵拖垮
MAX_GRID_CELLS_PER_SIDE = 251
MIN_GID_RESOLUTION_M = 10.0
MAX_GRID_RADIUS_M = 10_000.0


class ModelError(ValueError):
    """带错误代码的模型错误，便于前端按代码区分提示。"""

    def __init__(self, code: str, message: str, **extra):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


def require_wind_speed(u_ref: float) -> float:
    """风速合法性：拒绝静风，绝不以接近零的风速硬算。"""
    u = float(u_ref)
    if not math.isfinite(u):
        raise ModelError("BAD_INPUT", "风速必须是有限数值")
    if u < disp.WIND_SPEED_MIN:
        raise ModelError(
            "CALM_WIND",
            f"静风条件：10 m 风速 {u:g} m/s 低于模型下限 "
            f"{disp.WIND_SPEED_MIN:g} m/s。稳态高斯烟羽公式在风速趋零时发散，"
            "该情景应改用烟团/静风扩散模型（本应用不提供），不得用近零风速硬算浓度。",
            wind_speed_ref_m_s=u,
            wind_speed_min_m_s=disp.WIND_SPEED_MIN,
        )
    if u > disp.WIND_SPEED_MAX:
        raise ModelError(
            "WIND_TOO_HIGH",
            f"风速 {u:g} m/s 超出有效范围上限 {disp.WIND_SPEED_MAX:g} m/s。",
        )
    return u


def transport_bearing_deg(wind_from_deg: float) -> float:
    """气象风向（风从哪来，0=北、顺时针）→ 输送方位角（风吹向哪去）。"""
    return disp.normalise_wind_from(float(wind_from_deg) + 180.0)


def local_offsets(lon: np.ndarray, lat: np.ndarray,
                  lon0: float, lat0: float) -> tuple[np.ndarray, np.ndarray]:
    """WGS84 经纬度 → 以源为原点的局部平面东向/北向位移（m）。

    采用等矩形局部近似（平坦地形假设的一部分）：
        E = (λ-λ0) · R · cos φ0
        N = (φ-φ0) · R
    """
    lat0r = math.radians(lat0)
    east = np.radians(lon - lon0) * EARTH_RADIUS_M * math.cos(lat0r)
    north = np.radians(lat - lat0) * EARTH_RADIUS_M
    return east, north


@dataclass
class PlumeInputs:
    Q_g_s: float          # 源强
    hs_m: float           # 烟囱几何高度
    dh_m: float          # 烟气抬升高度
    u_ref_m_s: float      # 10 m 参考风速
    wind_from_deg: float  # 气象风向
    stability: str        # Pasquill 稳定度 A-F
    receptor_z_m: float = 0.0

    @property
    def H_m(self) -> float:
        return self.hs_m + self.dh_m

    @property
    def transport_bearing_deg(self) -> float:
        return transport_bearing_deg(self.wind_from_deg)

    @property
    def u_effective_m_s(self) -> float:
        return disp.wind_speed_at_height(self.u_ref_m_s, self.H_m, self.stability)


def validate_inputs(p: PlumeInputs) -> None:
    """对源项与气象做硬性范围校验（集中一处，API 与测试共用）。"""
    require_wind_speed(p.u_ref_m_s)
    if not disp.STACK_HEIGHT_MIN <= p.hs_m <= disp.STACK_HEIGHT_MAX:
        raise ModelError("BAD_STACK_HEIGHT",
                         f"烟囱高度须在 {disp.STACK_HEIGHT_MIN}–{disp.STACK_HEIGHT_MAX} m 之间")
    if not disp.PLUME_RISE_MIN <= p.dh_m <= disp.PLUME_RISE_MAX:
        raise ModelError("BAD_PLUME_RISE",
                         f"抬升高度须在 {disp.PLUME_RISE_MIN}–{disp.PLUME_RISE_MAX} m 之间")
    if not disp.EMISSION_RATE_MIN <= p.Q_g_s <= disp.EMISSION_RATE_MAX:
        raise ModelError("BAD_EMISSION", "源强超出允许范围（g/s）")
    if p.stability not in disp.STABILITY_CLASSES:
        raise ModelError("BAD_STABILITY", f"稳定度须为 {disp.STABILITY_CLASSES} 之一")
    if not disp.WIND_FROM_MIN <= p.wind_from_deg <= disp.WIND_FROM_MAX:
        raise ModelError("BAD_WIND_DIR", "风向须在 0–360 度之间")
    if not disp.RECEPTOR_Z_MIN <= p.receptor_z_m <= disp.RECEPTOR_Z_MAX:
        raise ModelError("BAD_RECEPTOR_Z",
                         f"受体高度须在 {disp.RECEPTOR_Z_MIN}–{disp.RECEPTOR_Z_MAX} m 之间")


def concentration_g_m3(p: PlumeInputs, x_down: np.ndarray, y_cross: np.ndarray,
                       z_m: float | None = None) -> np.ndarray:
    """任意下风向/横风向坐标处的浓度（g/m³），向量化。

    x_down <= 0（源的上风向）返回 0；调用方负责对经验曲线有效区间做掩码。
    """
    validate_inputs(p)
    x = np.asarray(x_down, dtype=float)
    y = np.asarray(y_cross, dtype=float)
    z = p.receptor_z_m if z_m is None else z_m
    H = p.H_m
    u = p.u_effective_m_s

    sy = disp.sigma_y(np.maximum(x, 1e-9), p.stability)
    sz = disp.sigma_z(np.maximum(x, 1e-9), p.stability)

    cross = np.exp(-(y ** 2) / (2.0 * sy ** 2))
    vertical = (np.exp(-((z - H) ** 2) / (2.0 * sz ** 2))
                + np.exp(-((z + H) ** 2) / (2.0 * sz ** 2)))
    c = p.Q_g_s / (2.0 * math.pi * u * sy * sz) * cross * vertical
    return np.where(x > 0, c, 0.0)


def build_grid(radius_m: float, resolution_m: float) -> tuple[np.ndarray, np.ndarray]:
    """构造以源为中心、边长 2R 的正方形采样网格的 E/N 坐标（m）。"""
    if radius_m > MAX_GRID_RADIUS_M or radius_m <= 0:
        raise ModelError("BAD_GRID_RADIUS",
                         f"采样半径须在 (0, {MAX_GRID_RADIUS_M}] m 之间")
    if resolution_m < MIN_GID_RESOLUTION_M:
        raise ModelError("GRID_TOO_FINE",
                         f"网格分辨率不得细于 {MIN_GID_RESOLUTION_M} m（教学演示用）")
    n = int(round(2 * radius_m / resolution_m)) + 1
    if n > MAX_GRID_CELLS_PER_SIDE:
        raise ModelError(
            "GRID_TOO_LARGE",
            f"单方向格点数 {n} 超过上限 {MAX_GRID_CELLS_PER_SIDE}，"
            f"请加大分辨率或减小采样半径。",
        )
    axis = (np.arange(n) - (n - 1) / 2.0) * resolution_m
    east, north = np.meshgrid(axis, axis)  # 行=北方向，列=东方向
    return east, north


def evaluate_grid(p: PlumeInputs, radius_m: float, resolution_m: float):
    """在采样网格上评估烟羽，返回浓度场与逐单元有效性掩码。

    返回 (C_ug_m3(含 NaN), info)。
    注意：分辨率只改变 *采样* 密度，不改变任何输入参数与模型本身。
    """
    east, north = build_grid(radius_m, resolution_m)
    T = math.radians(p.transport_bearing_deg)
    sinT, cosT = math.sin(T), math.cos(T)
    x_down = east * sinT + north * cosT
    y_cross = north * sinT - east * cosT

    c = concentration_g_m3(p, x_down, y_cross) * 1.0e6  # g/m³ → µg/m³

    # 三类格点显式区分，不做静默外推：
    #   上风向 (x≤0)      → 严格 0
    #   有效距离内        → 模型浓度
    #   0<x<100 或 x>10km → NaN（经验曲线有效区间之外）
    valid = ((x_down >= disp.X_VALID_MIN)
             & (x_down <= disp.X_VALID_MAX))
    upwind = x_down <= 0
    out_of_range = ~(valid | upwind)

    c_masked = np.where(valid, c, np.nan)
    c_masked = np.where(upwind, 0.0, c_masked)

    info = {
        "n_cells": int(c.size),
        "n_valid": int(valid.sum()),
        "n_upwind_zero": int(upwind.sum()),
        "n_out_of_range_nan": int(out_of_range.sum()),
        "x_down_min": float(x_down.min()),
        "x_down_max": float(x_down.max()),
    }
    return c_masked.astype(float), x_down, y_cross, info


# 供 API/界面展示的换算关系（显式列出，避免单位歧义）
UNIT_FACTORS_FROM_G_M3 = {
    "g/m3": 1.0,
    "mg/m3": 1.0e3,
    "ug/m3": 1.0e6,
}


def convert_concentration(c_g_m3, unit: str):
    if unit not in UNIT_FACTORS_FROM_G_M3:
        raise ModelError("BAD_UNIT", f"未知浓度单位 {unit}")
    return c_g_m3 * UNIT_FACTORS_FROM_G_M3[unit]
