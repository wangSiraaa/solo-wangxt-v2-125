-- plume-lab 教学数据库模式（PostgreSQL/PostGIS）
-- 所有数据均为虚构，仅用于课堂演示，不代表真实设施或事故。

CREATE TABLE IF NOT EXISTS sources (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    lon             DOUBLE PRECISION NOT NULL,  -- WGS84 经度
    lat             DOUBLE PRECISION NOT NULL,  -- WGS84 纬度
    stack_height_m  DOUBLE PRECISION NOT NULL,  -- 烟囱几何高度 hs
    plume_rise_m    DOUBLE PRECISION NOT NULL DEFAULT 0,  -- 烟气抬升 Δh
    emission_g_s    DOUBLE PRECISION NOT NULL,  -- 源强 Q，单位 g/s
    pollutant       TEXT NOT NULL DEFAULT '示踪气体（虚构）',
    geom            GEOMETRY(Point, 3857),  -- 由触发器从 lon/lat 维护
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_lon_ck CHECK (lon BETWEEN -180 AND 180),
    CONSTRAINT sources_lat_ck CHECK (lat BETWEEN -90 AND 90),
    CONSTRAINT sources_hs_ck  CHECK (stack_height_m BETWEEN 1 AND 500),
    CONSTRAINT sources_dh_ck  CHECK (plume_rise_m BETWEEN 0 AND 500),
    CONSTRAINT sources_q_ck   CHECK (emission_g_s >= 0)
);

CREATE TABLE IF NOT EXISTS met_scenarios (
    id                 BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name               TEXT NOT NULL,
    description        TEXT NOT NULL DEFAULT '',
    wind_from_deg      DOUBLE PRECISION NOT NULL,  -- 气象风向：风从哪来，0=北、顺时针
    wind_speed_10m_ms  DOUBLE PRECISION NOT NULL,  -- 10 m 高度参考风速
    stability_class    CHAR(1) NOT NULL,           -- Pasquill A–F
    background_ug_m3   DOUBLE PRECISION NOT NULL DEFAULT 0,  -- 区域背景浓度 µg/m³
    receptor_z_m       DOUBLE PRECISION NOT NULL DEFAULT 2,  -- 受体/呼吸高度
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT met_dir_ck  CHECK (wind_from_deg BETWEEN 0 AND 360),
    CONSTRAINT met_u_ck    CHECK (wind_speed_10m_ms >= 0),
    CONSTRAINT met_cls_ck  CHECK (stability_class IN ('A','B','C','D','E','F')),
    CONSTRAINT met_bg_ck   CHECK (background_ug_m3 >= 0),
    CONSTRAINT met_z_ck    CHECK (receptor_z_m BETWEEN 0 AND 500)
);

-- 每次计算的参数留痕（网格分辨率 *不* 入库：它只影响展示采样，不是情景输入）
CREATE TABLE IF NOT EXISTS calc_runs (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id       BIGINT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    met_id          BIGINT NOT NULL REFERENCES met_scenarios(id) ON DELETE CASCADE,
    grid_radius_m   DOUBLE PRECISION NOT NULL,
    resolution_m    DOUBLE PRECISION NOT NULL,
    unit            TEXT NOT NULL,
    max_plume_ug_m3 DOUBLE PRECISION,
    warning         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sources_geom_gix ON sources USING GIST (geom);

-- ST_Transform 不是 IMMUTABLE（依赖 PROJ 状态），用触发器维护 Web Mercator 几何列
CREATE OR REPLACE FUNCTION sources_geom_sync() RETURNS trigger AS $$
BEGIN
    NEW.geom := ST_Transform(ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat), 4326), 3857);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS sources_geom_trg ON sources;
CREATE TRIGGER sources_geom_trg
    BEFORE INSERT OR UPDATE OF lon, lat ON sources
    FOR EACH ROW EXECUTE FUNCTION sources_geom_sync();

-- 经纬度 ↔ Web Mercator 双向投影核对视图（可在界面 / SQL 中直接检查）
CREATE OR REPLACE VIEW sources_coordinate_check AS
SELECT id,
       lon, lat,
       ST_X(geom) AS merc_x, ST_Y(geom) AS merc_y,
       ST_X(ST_Transform(geom, 4326)) AS back_lon,
       ST_Y(ST_Transform(geom, 4326)) AS back_lat
FROM sources;

