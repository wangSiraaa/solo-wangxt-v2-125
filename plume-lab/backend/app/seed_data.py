# -*- coding: utf-8 -*-
"""虚构教学数据：3 个排放源 + 6 个气象情景（每种稳定度一类）。"""

SOURCES = [
    {
        "name": "示范厂 1 号烟囱（虚构）",
        "description": "低矮热排放源，用于展示源高对地面最大浓度的影响。",
        "lon": 116.3900, "lat": 39.9050,
        "stack_height_m": 45.0,
        "plume_rise_m": 15.0,
        "emission_g_s": 50.0,
        "pollutant": "示踪气体 A（虚构）",
    },
    {
        "name": "示范厂 2 号烟囱（虚构）",
        "description": "高架源；与 1 号同源强，便于直接比较烟囱高度效应。",
        "lon": 116.4200, "lat": 39.9200,
        "stack_height_m": 120.0,
        "plume_rise_m": 30.0,
        "emission_g_s": 50.0,
        "pollutant": "示踪气体 A（虚构）",
    },
    {
        "name": "示范厂 3 号烟囱（虚构）",
        "description": "高源强中等高度源，用于观察稳定层结下的窄烟羽。",
        "lon": 116.3550, "lat": 39.8850,
        "stack_height_m": 80.0,
        "plume_rise_m": 20.0,
        "emission_g_s": 200.0,
        "pollutant": "示踪气体 B（虚构）",
    },
]

MET_SCENARIOS = [
    {
        "name": "中性 D · 4 m/s 南风（虚构）",
        "description": "阴天常见的中性层结，基准情景。",
        "wind_from_deg": 180.0, "wind_speed_10m_ms": 4.0,
        "stability_class": "D", "background_ug_m3": 20.0, "receptor_z_m": 2.0,
    },
    {
        "name": "强不稳定 A · 5 m/s（虚构）",
        "description": "盛夏晴午，强湍流，烟羽快速扩散、落地近。",
        "wind_from_deg": 225.0, "wind_speed_10m_ms": 5.0,
        "stability_class": "A", "background_ug_m3": 10.0, "receptor_z_m": 2.0,
    },
    {
        "name": "稳定 F · 2.5 m/s 夜间（虚构）",
        "description": "晴夜逆温，垂直扩散弱，地面浓度带狭长；注意风速仍高于静风阈值。",
        "wind_from_deg": 90.0, "wind_speed_10m_ms": 2.5,
        "stability_class": "F", "background_ug_m3": 30.0, "receptor_z_m": 2.0,
    },
    {
        "name": "弱不稳定 C · 6 m/s（虚构）",
        "description": "有云天中等湍流。",
        "wind_from_deg": 270.0, "wind_speed_10m_ms": 6.0,
        "stability_class": "C", "background_ug_m3": 15.0, "receptor_z_m": 2.0,
    },
    {
        "name": "微风 0.3 m/s（静风反例，虚构）",
        "description": "故意构造的静风情景：应用必须拒绝计算并解释原因。",
        "wind_from_deg": 135.0, "wind_speed_10m_ms": 0.3,
        "stability_class": "F", "background_ug_m3": 30.0, "receptor_z_m": 2.0,
    },
    {
        "name": "较稳定 E · 3.5 m/s 傍晚（虚构）",
        "description": "日落前后稳定层结。",
        "wind_from_deg": 315.0, "wind_speed_10m_ms": 3.5,
        "stability_class": "E", "background_ug_m3": 25.0, "receptor_z_m": 2.0,
    },
]
