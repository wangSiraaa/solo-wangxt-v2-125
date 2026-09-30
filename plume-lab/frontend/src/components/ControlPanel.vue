<template>
  <div class="panel">
    <h2>情景选择（虚构数据）</h2>
    <label class="field">
      <span class="n">排放源</span>
      <select v-model="state.sourceId" @change="emitChange">
        <option v-for="s in sources" :key="s.id" :value="s.id">
          #{{ s.id }} {{ s.name }}
        </option>
      </select>
    </label>
    <div class="box dim" v-if="selectedSource" style="font-size:12px">
      {{ selectedSource.description }}
    </div>

    <label class="field">
      <span class="n">气象情景</span>
      <select v-model="state.metId" @change="onMetChange">
        <option v-for="m in met" :key="m.id" :value="m.id">
          #{{ m.id }} {{ m.name }}
        </option>
      </select>
    </label>
    <div class="box dim" v-if="selectedMet" style="font-size:12px">
      {{ selectedMet.description }}
    </div>

    <div v-if="selectedMet && selectedMet.wind_speed_10m_ms < calmThreshold"
         class="warn-box">
      ⚠ 该情景为静风（{{ selectedMet.wind_speed_10m_ms }} m/s &lt;
      {{ calmThreshold }} m/s）。点击计算时后端会拒绝，
      因为稳态烟羽公式在风速趋零时发散——这不是"无限浓度"，而是模型失效。
    </div>

    <h2>采样网格（只影响展示，不改变输入）</h2>
    <div class="row2">
      <label class="field">
        <span class="n">采样半径 (m)</span>
        <input type="number" v-model.number="state.radius" min="200" max="10000"
               step="100" />
      </label>
      <label class="field">
        <span class="n">分辨率 (m)</span>
        <input type="number" v-model.number="state.resolution" min="10"
               max="500" step="5" />
      </label>
    </div>
    <div class="dim" style="font-size:11px">
      有效经验距离区间：x = 100–10000 m。范围外格点不做外推。<br />
      单边格点上限 251；分辨率最小 10 m。
    </div>

    <h2>显示浓度单位</h2>
    <label class="field">
      <select v-model="state.unit" @change="emitChange">
        <option value="ug/m3">µg/m³</option>
        <option value="mg/m3">mg/m³</option>
        <option value="g/m3">g/m³</option>
      </select>
    </label>

    <label class="field checkline">
      <input type="checkbox" v-model="state.showSamples" @change="emitChange" />
      显示采样格点中心（明确分辨率）
    </label>
    <label class="field checkline">
      <input type="checkbox" v-model="state.showInvalid" @change="emitChange" />
      高亮有效距离外格点（不计值）
    </label>

    <button class="primary" :disabled="loading" @click="$emit('calculate')">
      {{ loading ? '计算中…' : '计算浓度场' }}
    </button>

    <div v-if="error" class="error-box">
      <b v-if="error.code === 'CALM_WIND'">静风，已拒绝计算</b>
      <b v-else>请求失败（{{ error.code || 'ERROR' }}）</b>
      <div style="margin-top:4px">{{ error.message }}</div>
    </div>

    <h2>风向坐标核对</h2>
    <button class="primary" style="background:var(--panel-2);color:var(--text);
            border:1px solid var(--line);margin-top:0"
            @click="$emit('checkWind')">
      检查当前情景风向转换
    </button>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  sources: { type: Array, default: () => [] },
  met: { type: Array, default: () => [] },
  config: Object,
  loading: Boolean,
  error: Object,
})
const emit = defineEmits(['calculate', 'checkWind', 'update'])

const state = reactive({
  sourceId: null, metId: null, radius: 2000, resolution: 50,
  unit: 'ug/m3', showSamples: false, showInvalid: false,
})

watch(() => props.sources, (list) => {
  if (state.sourceId == null && list.length) state.sourceId = list[0].id
}, { immediate: true })
watch(() => props.met, (list) => {
  if (state.metId == null && list.length) state.metId = list[0].id
}, { immediate: true })

const selectedSource = computed(() =>
  props.sources.find((s) => s.id === state.sourceId))
const selectedMet = computed(() =>
  props.met.find((m) => m.id === state.metId))
const calmThreshold = computed(() => props.config?.calm_wind_policy?.threshold_m_s ?? 0.5)

function emitChange() { emit('update', { ...state }) }
function onMetChange() { emitChange() }

defineExpose({ state })
</script>
