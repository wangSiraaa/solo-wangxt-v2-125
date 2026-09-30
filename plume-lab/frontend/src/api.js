// 后端 API 封装。全部请求指向同源 /api（开发期由 Vite 代理）。
async function get(path) {
  const r = await fetch(path)
  if (!r.ok) throw new Error(`GET ${path} → ${r.status}`)
  return r.json()
}

async function post(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const j = await r.json().catch(() => ({}))
  if (!r.ok) {
    const err = new Error(j.message || `POST ${path} → ${r.status}`)
    err.code = j.error_code
    err.details = j.details
    throw err
  }
  return j
}

export const api = {
  health: () => get('/api/health'),
  config: () => get('/api/config'),
  sources: () => get('/api/sources'),
  met: () => get('/api/met'),
  sourcesGeoJson: () => get('/api/sources/geojson'),
  coordinateCheck: () => get('/api/coordinate-check'),
  windGeometry: (deg) => get(`/api/wind-geometry?wind_from_deg=${deg}`),
  verification: () => get('/api/verification'),
  plume: (body) => post('/api/plume', body),
}

// 浓度单位换算因子（相对 µg/m³）
export const UNIT_TO_UG = {
  'ug/m3': 1.0,
  'mg/m3': 1e3,
  'g/m3': 1e0, // g 用独立标签，下面按 factor_from_ug 处理
}

export function convertFromUg(value, unit) {
  const f = { 'ug/m3': 1, 'mg/m3': 1e-3, 'g/m3': 1e-6 }[unit] ?? 1
  return value * f
}

export const UNIT_LABEL = { 'ug/m3': 'µg/m³', 'mg/m3': 'mg/m³', 'g/m3': 'g/m³' }

// 固定的教学等值面色带（µg/m³，plume-only），与"非无限精度"原则一致：
// 等级有限且明确标注，不渲染成看似连续无误差的图。
export const PLUME_STEPS_UG = [5, 10, 20, 40, 80, 160, 320, 640, 1280]
