// 采样网格 → GeoJSON（等值面 + 采样范围 + 格点）。
//
// 明确原则：图上画的是 *离散采样* 的结果。
//  - 等值面由 d3-contour（marching squares）在有限格点上生成；
//  - 同时提供"采样范围框"和可选"格点"图层，避免暗示无限精度；
//  - 无效格点（NaN：下风向距离超出 100–10000 m）不参与等值面生成。
import { contours as d3contours } from 'd3-contour'

// 局部平面米坐标 → WGS84 经纬度（与后端同一等矩形近似，参数由后端给出）
export function metersToLonLat(east, north, origin, metersPerDegree) {
  return [
    origin[0] + east / metersPerDegree.lon,
    origin[1] + north / metersPerDegree.lat,
  ]
}

function ringToLonLat(ring, origin, mpd, cellM, n) {
  // d3-contour 的坐标单位是格点索引（col=x, row=y），原点在左上角。
  // 格点 (col,row) 对应的平面东向/北向（m）：
  const half = (n - 1) / 2
  return ring.map(([col, row]) => {
    const east = (col - half) * cellM
    const north = (half - row) * cellM // 行序北→南
    return metersToLonLat(east, north, origin, mpd)
  })
}

export function buildContourGeoJson(grid, steps, values) {
  const nrows = grid.nrows
  const arr = Float64Array.from(values, (v) => (v === null || Number.isNaN(v) ? NaN : v))

  const gen = d3contours()
    .size([grid.ncols, nrows])
    .smooth(false) // 不平滑：如实展示离散格点间的线性插值，不伪装精度
    .thresholds(steps)

  const multipolygons = gen(arr)
  const features = multipolygons
    .filter((mp) => mp.coordinates.length > 0)
    .map((mp) => ({
      type: 'Feature',
      properties: { level: mp.value },
      geometry: {
        type: 'MultiPolygon',
        coordinates: mp.coordinates.map((poly) =>
          poly.map((ring) =>
            ringToLonLat(
              ring,
              grid.source_lonlat,
              grid.meters_per_degree,
              grid.resolution_m,
              nrows,
            ),
          ),
        ),
      },
    }))

  return { type: 'FeatureCollection', features }
}

export function buildExtentGeoJson(grid) {
  // 格点中心范围为 ±radius；marching-squares 单元角点可到 ±(radius+Δ/2)，
  // 采样框按单元覆盖范围绘制，与等值面外边缘严格一致。
  const halfCell = grid.resolution_m / 2
  const c = grid.corner_lonlat
  const o = grid.source_lonlat
  const dLon = halfCell / grid.meters_per_degree.lon
  const dLat = halfCell / grid.meters_per_degree.lat
  const nw = [c.corner_nw[0] - dLon, c.corner_nw[1] + dLat]
  const ne = [c.corner_ne[0] + dLon, c.corner_ne[1] + dLat]
  const se = [c.corner_se[0] + dLon, c.corner_se[1] - dLat]
  const sw = [c.corner_sw[0] - dLon, c.corner_sw[1] - dLat]
  const ring = [nw, ne, se, sw, nw]
  return {
    type: 'Feature',
    geometry: { type: 'Polygon', coordinates: [ring] },
    properties: {
      resolution_m: grid.resolution_m,
      radius_m: grid.radius_m,
      center_extent_m: grid.radius_m,
      cell_edge_extent_m: grid.radius_m + halfCell,
      origin_lonlat: o,
    },
  }
}

// 格点中心（仅在用户勾选时显示，直观表达"采样分辨率"）
export function buildSamplePointsGeoJson(grid, values, maxPoints = 2600) {
  const n = grid.nrows
  const half = (n - 1) / 2
  const coords = []
  const stride = Math.max(1, Math.ceil(n / Math.sqrt(maxPoints)))
  for (let row = 0; row < n; row += stride) {
    for (let col = 0; col < n; col += stride) {
      const v = values[row * n + col]
      if (v === null || Number.isNaN(v)) continue
      const east = (col - half) * grid.resolution_m
      const north = (half - row) * grid.resolution_m
      const [lon, lat] = metersToLonLat(
        east,
        north,
        grid.source_lonlat,
        grid.meters_per_degree,
      )
      coords.push({ lon, lat, v })
    }
  }
  return {
    type: 'FeatureCollection',
    features: coords.map((p) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
      properties: { v: p.v },
    })),
  }
}

// 无效格点（NaN）位置，用空心点表示"模型有效范围之外"
export function buildInvalidPointsGeoJson(grid, values, maxPoints = 1200) {
  const n = grid.nrows
  const half = (n - 1) / 2
  const coords = []
  const stride = Math.max(1, Math.ceil(n / Math.sqrt(maxPoints)))
  for (let row = 0; row < n; row += stride) {
    for (let col = 0; col < n; col += stride) {
      const v = values[row * n + col]
      if (v !== null && !Number.isNaN(v)) continue
      const east = (col - half) * grid.resolution_m
      const north = (half - row) * grid.resolution_m
      const [lon, lat] = metersToLonLat(
        east,
        north,
        grid.source_lonlat,
        grid.meters_per_degree,
      )
      coords.push([lon, lat])
    }
  }
  return {
    type: 'FeatureCollection',
    features: coords.map((c) => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: c },
      properties: {},
    })),
  }
}

export function buildWindArrowGeoJson(source, wind) {
  // 从源指向输送去向（不是来向），与界面文字相互核对
  const T = (wind.transport_bearing_deg * Math.PI) / 180
  const len = Math.min(0.012, 0.004 + wind.u_at_H_m_s * 0.0012)
  const lat0 = source.lat
  const dLon = (len * Math.sin(T)) / Math.cos((lat0 * Math.PI) / 180)
  const dLat = len * Math.cos(T)
  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: {
          type: 'LineString',
          coordinates: [
            [source.lon, source.lat],
            [source.lon + dLon, source.lat + dLat],
          ],
        },
        properties: { bearing: wind.transport_bearing_deg },
      },
    ],
  }
}
