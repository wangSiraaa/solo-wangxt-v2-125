# -*- coding: utf-8 -*-
"""Pydantic API 模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    id: int
    name: str
    description: str
    lon: float
    lat: float
    stack_height_m: float
    plume_rise_m: float
    emission_g_s: float
    pollutant: str


class MetOut(BaseModel):
    id: int
    name: str
    description: str
    wind_from_deg: float
    wind_speed_10m_ms: float
    stability_class: str
    background_ug_m3: float
    receptor_z_m: float


class PlumeRequest(BaseModel):
    source_id: int
    met_id: int
    grid_radius_m: float = Field(2000.0, gt=0)
    resolution_m: float = Field(50.0, gt=0)
    unit: Literal["ug/m3", "mg/m3", "g/m3"] = "ug/m3"
