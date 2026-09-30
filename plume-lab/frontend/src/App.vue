<template>
  <div class="app">
    <header class="topbar">
      <h1> plume-lab · 高斯烟羽情景实验</h1>
      <span class="tag">Vue 3 + MapLibre</span>
      <span class="tag">FastAPI + NumPy</span>
      <span class="tag">PostgreSQL/PostGIS</span>
      <span class="tag">离线 · 无外部瓦片</span>
      <span class="spacer"></span>
      <span class="disclaimer-mini">教学演示：不得用于事故预警或法规达标判定</span>
    </header>

    <ControlPanel
      ref="controlRef"
      :sources="sources" :met="met" :config="config"
      :loading="loading" :error="error"
      @calculate="calculate"
      @check-wind="checkWind"
    />

    <MapPanel :result="result" :show-samples="ui.showSamples"
              :show-invalid="ui.showInvalid" />

    <ResultsPanel ref="resultsRef" :result="result" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api } from './api'
import ControlPanel from './components/ControlPanel.vue'
import MapPanel from './components/MapPanel.vue'
import ResultsPanel from './components/ResultsPanel.vue'

const sources = ref([])
const met = ref([])
const config = ref(null)
const result = ref(null)
const loading = ref(false)
const error = ref(null)
const controlRef = ref(null)
const resultsRef = ref(null)

const ui = reactive({ showSamples: false, showInvalid: false })

onMounted(async () => {
  ;[sources.value, met.value, config.value] = await Promise.all([
    api.sources(), api.met(), api.config(),
  ])
  api.health().then((h) => {
    // 健康信息可在控制台检查
    console.info('[plume-lab] backend:', h.postgis, '| sources:',
                h.sources, '| met:', h.met_scenarios)
  })
})

async function calculate() {
  const s = controlRef.value.state
  ui.showSamples = s.showSamples
  ui.showInvalid = s.showInvalid
  loading.value = true
  error.value = null
  try {
    result.value = await api.plume({
      source_id: s.sourceId,
      met_id: s.metId,
      grid_radius_m: s.radius,
      resolution_m: s.resolution,
      unit: s.unit,
    })
  } catch (e) {
    result.value = null
    error.value = { code: e.code, message: e.message }
  } finally {
    loading.value = false
  }
}

async function checkWind() {
  const s = controlRef.value.state
  const m = met.value.find((x) => x.id === s.metId)
  if (m && resultsRef.value) {
    resultsRef.value.tab = 'coord'
    await resultsRef.value.refreshWind(m.wind_from_deg)
  }
}
</script>
