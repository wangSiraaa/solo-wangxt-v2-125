<template>
  <div class="map-wrap">
    <div id="map" ref="el"></div>

    <div class="map-overlay">
      <div class="ttl">采样区域等值面</div>
      <div class="dim" v-if="!result">选择源与气象情景后点击「计算浓度场」。</div>
      <div v-else>
        <div class="kv"><span class="k">烟羽峰值（不含背景）</span>
          <span class="v">{{ fmt(maxPlume) }} {{ unitLabel }}</span></div>
        <div class="kv"><span class="k">背景值</span>
          <span class="v">{{ fmt(maxPlume != null ? background : null) }} {{ unitLabel }}</span></div>
        <div class="kv"><span class="k">峰值处总量</span>
          <span class="v">{{ fmt(maxPlume != null ? maxPlume + background : null) }} {{ unitLabel }}</span></div>
        <div class="kv"><span class="k">输送方位（去向）</span>
          <span class="v">{{ result.wind.transport_bearing_deg.toFixed(0) }}°</span></div>
      </div>
    </div>

    <div class="legend" v-if="result">
      <div class="dim" style="font-size:11px">烟羽贡献等级（{{ unitLabel }}，不含背景）</div>
      <div class="bar"></div>
      <div class="ends"><span>{{ legendLo }}</span><span>{{ legendHi }}</span></div>
    </div>

    <div class="north-arrow">N↑</div>
    <div class="scale-note">
      采样 {{ gridLabel }} · 格点 {{ nLabels }}<br />
      离线底图（自绘经纬网，非瓦片地图）
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import maplibregl from 'maplibre-gl'
import {
  buildContourGeoJson, buildExtentGeoJson, buildInvalidPointsGeoJson,
  buildSamplePointsGeoJson, buildWindArrowGeoJson,
} from '../geo'
import { convertFromUg, PLUME_STEPS_UG, UNIT_LABEL } from '../api'

const props = defineProps({
  result: { type: Object, default: null },
  showSamples: Boolean,
  showInvalid: Boolean,
})

const el = ref(null)
let map = null
const maxPlume = ref(null)
const background = ref(0)
const unitLabel = ref('µg/m³')
const gridLabel = ref('—')
const nLabels = ref('—')
const legendLo = ref('')
const legendHi = ref('')

function fmt(v) {
  if (v == null || Number.isNaN(v)) return '—'
  if (v >= 100) return v.toFixed(0)
  if (v >= 1) return v.toFixed(1)
  return v.toFixed(2)
}

// 9 级教学色带（与样式 legend 对应）
const FILL = [
  'match', ['get', 'level'],
  5, '#2c7bb6', 10, '#00a6ca', 20, '#00ccbc', 40, '#90eb9d',
  80, '#ffff8c', 160, '#f9d057', 320, '#f29e2e', 640, '#e76818',
  1280, '#d7191c', 'rgba(150,150,150,0.25)',
]

function graticule(center) {
  // 以源为中心生成等经纬度网格线（离线底图，不依赖任何瓦片）
  const feats = []
  const span = 0.25
  const step = 0.025
  let i = 0
  for (let d = -span; d <= span + 1e-9; d += step, i += 1) {
    const major = i % 4 === 0
    feats.push({
      type: 'Feature',
      properties: { major: major ? 1 : 0 },
      geometry: { type: 'LineString',
        coordinates: [[center[0] + d, center[1] - span], [center[0] + d, center[1] + span]] },
    })
    feats.push({
      type: 'Feature',
      properties: { major: major ? 1 : 0 },
      geometry: { type: 'LineString',
        coordinates: [[center[0] - span, center[1] + d], [center[0] + span, center[1] + d]] },
    })
  }
  return { type: 'FeatureCollection', features: feats }
}

onMounted(() => {
  map = new maplibregl.Map({
    container: el.value,
    style: {
      version: 8,
      // 无 glyphs：不渲染文本瓦片，全部标签用 HTML overlay，保证完全离线
      sources: {
        grat: { type: 'geojson', data: graticule([116.39, 39.905]) },
        empty: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
      },
      layers: [
        { id: 'bg', type: 'background', paint: { 'background-color': '#0b101a' } },
        { id: 'grat-line', type: 'line', source: 'grat',
          paint: { 'line-color': '#22304a', 'line-width': 0.6 } },
        { id: 'grat-major', type: 'line', source: 'grat',
          filter: ['==', ['get', 'major'], 1],
          paint: { 'line-color': '#2c4064', 'line-width': 1 } },
      ],
    },
    center: [116.39, 39.905],
    zoom: 12.2,
    attributionControl: false,
  })
  map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right')
  map.on('load', () => {
    for (const [id, type, source, paint, extra = {}] of [
      ['extent-fill', 'fill', 'empty',
       { 'fill-color': '#4da3ff', 'fill-opacity': 0.0 }],
      ['extent-line', 'line', 'empty',
       { 'line-color': '#93a3bb', 'line-width': 1.4, 'line-dash-array': [4, 3] }],
      ['contours', 'fill', 'empty',
       { 'fill-color': FILL, 'fill-opacity': 0.55 }],
      ['invalid-pts', 'circle', 'empty',
       { 'circle-radius': 1.6, 'circle-color': '#55627a',
         'circle-stroke-color': '#55627a', 'circle-stroke-width': 0.4,
         'circle-opacity': 0.5 }],
      ['sample-pts', 'circle', 'empty',
       { 'circle-radius': 1.1, 'circle-color': '#dce6f5', 'circle-opacity': 0.35 }],
      ['wind-arrow', 'line', 'empty',
       { 'line-color': '#4da3ff', 'line-width': 2.6 }],
      ['sources', 'circle', 'empty',
       { 'circle-radius': 5, 'circle-color': '#ff6b6b',
         'circle-stroke-color': '#fff', 'circle-stroke-width': 1.5 }],
    ]) {
      map.addSource(id, { type: 'geojson', data: source === 'empty'
        ? { type: 'FeatureCollection', features: [] } : source })
      map.addLayer({ id, type, source: id, paint, ...extra })
    }
    map.setLayoutProperty('sample-pts', 'visibility', 'none')
    map.setLayoutProperty('invalid-pts', 'visibility', 'none')

    // 载入所有虚构源
    fetch('/api/sources/geojson').then((r) => r.json()).then((gj) => {
      map.getSource('sources').setData(gj)
      gj.features.forEach((f) => {
        new maplibregl.Popup({ closeOnClick: false, offset: 12 })
          .setHTML(`<b>${f.properties.name}</b><br/>`
            + `hs=${f.properties.stack_height_m} m · `
            + `Δh=${f.properties.plume_rise_m} m<br/>`
            + `Q=${f.properties.emission_g_s} g/s`)
          .setLngLat(f.geometry.coordinates)
          .addTo(map)
      })
    })
  })
})

function render(result) {
  if (!map || !result) return
  if (!map.isStyleLoaded()) {
    map.once('load', () => render(result))
    return
  }
  const g = result.grid
  const valuesUg = g.values_ug_m3
  const contour = buildContourGeoJson(g, PLUME_STEPS_UG, valuesUg)
  map.getSource('contours').setData(contour)
  map.getSource('extent-fill').setData(buildExtentGeoJson(g))
  map.getSource('extent-line').setData(buildExtentGeoJson(g))
  map.getSource('wind-arrow').setData(buildWindArrowGeoJson(result.source, result.wind))
  map.getSource('sample-pts').setData(buildSamplePointsGeoJson(g, valuesUg))
  map.getSource('invalid-pts').setData(buildInvalidPointsGeoJson(g, valuesUg))

  const unit = result.concentration.display_unit_requested
  unitLabel.value = UNIT_LABEL[unit]
  const m = result.concentration.max_plume_ug_m3
  maxPlume.value = m == null ? null : convertFromUg(m, unit)
  background.value = convertFromUg(result.concentration.background_ug_m3, unit)
  gridLabel.value = `${g.resolution_m} m / 半径 ${g.radius_m} m`
  nLabels.value = `${g.nrows}×${g.ncols}`
  legendLo.value = `${convertFromUg(PLUME_STEPS_UG[0], unit)}`
  legendHi.value = `≥${convertFromUg(PLUME_STEPS_UG[PLUME_STEPS_UG.length - 1], unit)}`

  const c = g.corner_lonlat
  const bounds = new maplibregl.LngLatBounds(c.corner_sw, c.corner_ne)
  map.fitBounds(bounds, { padding: 60, animate: false, maxZoom: 14.5 })
}

watch(() => props.result, (r) => render(r), { immediate: false })
watch(() => props.showSamples, (v) => {
  if (map) map.setLayoutProperty('sample-pts', 'visibility', v ? 'visible' : 'none')
})
watch(() => props.showInvalid, (v) => {
  if (map) map.setLayoutProperty('invalid-pts', 'visibility', v ? 'visible' : 'none')
})
</script>
