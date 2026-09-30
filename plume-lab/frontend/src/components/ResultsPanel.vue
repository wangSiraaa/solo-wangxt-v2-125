<template>
  <div class="panel">
    <div class="tabs">
      <button :class="{ active: tab === 'result' }" @click="tab = 'result'">结果分解</button>
      <button :class="{ active: tab === 'verify' }" @click="tab = 'verify'">解析核对</button>
      <button :class="{ active: tab === 'coord' }" @click="tab = 'coord'">坐标检查</button>
    </div>

    <template v-if="tab === 'result'">
      <template v-if="!result">
        <div class="dim">尚未计算。选择情景后点击「计算浓度场」。</div>
      </template>
      <template v-else>
        <h2>① 源项（与气象/背景分开）</h2>
        <div class="box">
          <div class="kv"><span class="k">排放物</span><span class="v">{{ st.pollutant }}</span></div>
          <div class="kv"><span class="k">源强 Q</span>
            <span class="v">{{ st.Q_g_s }} g/s</span></div>
          <div class="kv"><span class="k">　= 小时排放</span>
            <span class="v">{{ fmt(st.Q_g_h) }} g/h</span></div>
          <div class="kv"><span class="k">　= 日排放</span>
            <span class="v">{{ fmt(st.Q_kg_day) }} kg/d</span></div>
          <div class="kv"><span class="k">烟囱几何高度 hs</span>
            <span class="v">{{ st.stack_height_hs_m }} m</span></div>
          <div class="kv"><span class="k">烟气抬升 Δh</span>
            <span class="v">{{ st.plume_rise_dh_m }} m</span></div>
          <div class="kv"><span class="k">有效源高 H = hs+Δh</span>
            <span class="v"><b>{{ st.effective_height_H_m }} m</b></span></div>
        </div>

        <h2>② 气象与风坐标转换（可检查）</h2>
        <div class="box">
          <div class="kv"><span class="k">稳定度</span>
            <span class="v">{{ wnd.stability_label }}</span></div>
          <div class="kv"><span class="k">气象风向（来向）</span>
            <span class="v">{{ wnd.wind_from_deg }}°（0=北，顺时针）</span></div>
          <div class="kv"><span class="k">输送方位（去向）</span>
            <span class="v">{{ wnd.transport_bearing_deg }}°</span></div>
          <div class="kv"><span class="k">10 m 参考风速 u10</span>
            <span class="v">{{ wnd.u_ref_10m_m_s }} m/s</span></div>
          <div class="kv"><span class="k">廓线指数 p（乡村）</span>
            <span class="v">{{ wnd.profile_exponent_p }}</span></div>
          <div class="kv"><span class="k">H 高度风速 u(H)</span>
            <span class="v"><b>{{ wnd.u_at_H_m_s.toFixed(2) }} m/s</b></span></div>
          <div class="kv"><span class="k">静风阈值</span>
            <span class="v">{{ wnd.calm_threshold_m_s }} m/s</span></div>
        </div>

        <h2>③ 浓度（三部分分别展示，{{ unitLabel }})</h2>
        <div class="box">
          <div class="kv"><span class="k">烟羽贡献峰值</span>
            <span class="v">{{ fmt(toUnit(conc.max_plume_ug_m3)) }}</span></div>
          <div class="kv"><span class="k">区域背景值</span>
            <span class="v">{{ fmt(toUnit(conc.background_ug_m3)) }}</span></div>
          <div class="kv"><span class="k">峰值处总量 = 烟羽+背景</span>
            <span class="v"><b>{{ fmt(toUnit(conc.max_total_ug_m3)) }}</b></span></div>
        </div>
        <div class="dim" style="font-size:11px">
          等值面与剖面图只画 <b>烟羽贡献</b>；背景值为空间常量、单独标注，
          避免把背景与扩散效果混在一张色图里。
        </div>

        <h2>下风向地面轴线剖面（烟羽贡献）</h2>
        <div class="chart-wrap">
          <svg :viewBox="`0 0 ${W} ${H}`" width="100%" height="150">
            <line :x1="pad.l" :y1="H-pad.b" :x2="W-pad.r" :y2="H-pad.b"
                  stroke="#2b3a52" />
            <line :x1="pad.l" :y1="pad.t" :x2="pad.l" :y2="H-pad.b"
                  stroke="#2b3a52" />
            <line v-if="bgY" :x1="pad.l" :y1="bgY" :x2="W-pad.r" :y2="bgY"
                  stroke="#ffb020" stroke-dasharray="4 3" />
            <text v-if="bgY" :x="W-pad.r-6" :y="bgY-3" fill="#ffb020"
                  font-size="9" text-anchor="end">背景 {{ fmt(toUnit(profile.bg)) }}</text>
            <path :d="profilePath" fill="none" stroke="#4da3ff" stroke-width="2" />
            <circle :cx="peakXY.x" :cy="peakXY.y" r="3" fill="#ff6b6b" />
            <text :x="peakXY.x+5" :y="peakXY.y-5" fill="#ff6b6b" font-size="9">
              峰值 x={{ fmt(profile.peakX) }} m
            </text>
            <text :x="pad.l" :y="H-3" fill="#93a3bb" font-size="9">100 m</text>
            <text :x="W-pad.r" :y="H-3" fill="#93a3bb" font-size="9" text-anchor="end">
              10 km
            </text>
          </svg>
          <div class="dim" style="font-size:11px">
            高架源"先升后降"：烟羽到达地面前浓度近零，混合到地面后出现峰值，
            随后随扩散单调衰减。
          </div>
        </div>

        <h2>采样范围与有效性</h2>
        <div class="box" style="font-size:12px">
          <div class="kv"><span class="k">网格规模</span>
            <span class="v">{{ g.nrows }}×{{ g.ncols }} = {{ g.sampling.n_cells }} 点</span></div>
          <div class="kv"><span class="k">有效距离内格点</span>
            <span class="v">{{ g.sampling.n_valid }}</span></div>
          <div class="kv"><span class="k">上风向（严格 0）</span>
            <span class="v">{{ g.sampling.n_upwind_zero }}</span></div>
          <div class="kv"><span class="k">超有效区间（NaN）</span>
            <span class="v">{{ g.sampling.n_out_of_range_nan }}</span></div>
        </div>
        <div v-if="result.warning" class="warn-box">{{ result.warning }}</div>

        <h2>模型有效性边界</h2>
        <div class="box dim" style="font-size:11px">
          <div>· {{ validity.terrain }}</div>
          <div>· {{ validity.wind }}</div>
          <div>· {{ validity.reflection }}</div>
          <div>· {{ validity.dispersion }}</div>
        </div>
        <div class="error-box" style="font-size:11px">⚠ {{ result.disclaimer }}</div>
      </template>
    </template>

    <template v-else-if="tab === 'verify'">
      <h2>解析核对用例</h2>
      <div class="dim" style="margin-bottom:6px">
        这些断言只依赖公式本身，可手工复算。
      </div>
      <div v-if="!cases.length" class="dim">点击下方按钮从后端载入核对结果。</div>
      <button class="primary" @click="loadCases">运行 / 刷新核对</button>
      <div v-for="c in cases" :key="c.key" class="case" :class="c.passed ? 'pass' : 'fail'">
        <div class="h">
          {{ c.title }}
          <span :class="c.passed ? 'ok-pill' : 'fail-pill'">
            {{ c.passed ? '通过' : '未通过' }}
          </span>
        </div>
        <div class="stmt">{{ c.statement }}</div>
        <VerificationDetail :c="c" />
      </div>
    </template>

    <template v-else>
      <h2>投影往返检查（PostGIS）</h2>
      <div class="dim" style="margin-bottom:6px">
        lon/lat(4326) → Web Mercator(3857) → lon/lat 的往返误差：
      </div>
      <button class="primary" @click="loadCoord">载入坐标检查</button>
      <div v-for="r in coordRows" :key="r.id" class="box" style="font-size:11px">
        <div class="kv"><span class="k">#{{ r.id }}</span>
          <span class="v">{{ r.lon.toFixed(4) }}, {{ r.lat.toFixed(4) }}</span></div>
        <div class="kv"><span class="k">merc x/y</span>
          <span class="v">{{ r.merc_x.toFixed(0) }}, {{ r.merc_y.toFixed(0) }}</span></div>
        <div class="kv"><span class="k">往返误差</span>
          <span class="v">Δlon {{ r.dlon_err.toExponential(1) }} /
            Δlat {{ r.dlat_err.toExponential(1) }}°</span></div>
      </div>

      <h2>风向转换检查（当前情景）</h2>
      <div v-if="windCheck" class="box">
        <div class="kv"><span class="k">风向（来向）</span>
          <span class="v">{{ windCheck.wind_from_deg }}°</span></div>
        <div class="kv"><span class="k">输送方位（去向）</span>
          <span class="v">{{ windCheck.transport_bearing_deg }}°</span></div>
        <div v-for="p in windCheck.check_points" :key="p.label"
             style="font-size:11px;margin-top:3px">
          {{ p.label }}：x↓风={{ p.x_downwind_m.toFixed(0) }} m，
          y横风={{ p.y_crosswind_m.toFixed(0) }} m
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, h, ref } from 'vue'
import { api, convertFromUg, UNIT_LABEL } from '../api'

const props = defineProps({ result: Object })
const tab = ref('result')
const cases = ref([])
const coordRows = ref([])
const windCheck = ref(null)

const W = 320, H = 150
const pad = { l: 38, r: 8, t: 12, b: 18 }

const st = computed(() => props.result?.source_term ?? {})
const wnd = computed(() => props.result?.wind ?? {})
const conc = computed(() => props.result?.concentration ?? {})
const g = computed(() => props.result?.grid ?? { sampling: {} })
const validity = computed(() => props.result?.model_validity ?? {})
const unitLabel = computed(() => UNIT_LABEL[conc.value.display_unit_requested] ?? 'µg/m³')

function toUnit(v) {
  if (v == null) return null
  return convertFromUg(v, conc.value.display_unit_requested)
}
function fmt(v) {
  if (v == null || Number.isNaN(v)) return '—'
  const av = Math.abs(v)
  if (av >= 1000) return v.toFixed(0)
  if (av >= 10) return v.toFixed(1)
  if (av >= 0.01) return v.toFixed(2)
  return v.toExponential(1)
}

const profile = computed(() => {
  if (!props.result) return null
  const p = props.result.centerline_profile
  const xs = p.x_m
  const cs = p.plume_ug_m3
  let iMax = 0
  for (let i = 1; i < cs.length; i++) if (cs[i] > cs[iMax]) iMax = i
  return { x: xs, c: cs, bg: p.background_ug_m3, peakX: xs[iMax], peakC: cs[iMax] }
})

const plotGeom = computed(() => {
  if (!profile.value) return null
  const p = profile.value
  const xmin = p.x[0], xmax = p.x[p.x.length - 1]
  const cmax = Math.max(...p.c, p.bg) * 1.05
  const X = (x) => pad.l + ((x - xmin) / (xmax - xmin)) * (W - pad.l - pad.r)
  const Y = (c) => H - pad.b - (c / cmax) * (H - pad.t - pad.b)
  return { X, Y, cmax }
})
const profilePath = computed(() => {
  if (!plotGeom.value) return ''
  const { X, Y } = plotGeom.value
  return profile.value.x.map((x, i) =>
    `${i === 0 ? 'M' : 'L'}${X(x).toFixed(1)},${Y(profile.value.c[i]).toFixed(1)}`).join(' ')
})
const peakXY = computed(() => {
  if (!plotGeom.value) return { x: 0, y: 0 }
  const { X, Y } = plotGeom.value
  return { x: X(profile.value.peakX), y: Y(profile.value.peakC) }
})
const bgY = computed(() => {
  if (!plotGeom.value) return null
  return plotGeom.value.Y(profile.value.bg)
})

async function loadCases() { cases.value = (await api.verification()).cases }
async function loadCoord() { coordRows.value = await api.coordinateCheck() }

async function refreshWind(deg) {
  windCheck.value = await api.windGeometry(deg)
}
defineExpose({ refreshWind })

// 各核对用例的精简数值展示
const VerificationDetail = {
  props: { c: Object },
  setup(p) {
    return () => {
      const rows = []
      const c = p.c
      if (c.max_relative_diff != null)
        rows.push(`最大相对差：${c.max_relative_diff.toExponential(1)}（容差 ${c.tolerance_relative}）`)
      if (c.peak_x_m != null) {
        rows.push(`峰值距离 x*=${c.peak_x_m.toFixed(0)} m，峰值=${c.peak_c_ug_m3.toFixed(1)} µg/m³`)
        rows.push(`100 m 处=${c.c_at_100m_ug_m3.toFixed(2)}；10 km 处=${c.c_at_10km_ug_m3.toFixed(2)} µg/m³`)
        rows.push(`峰后单调递减：${c.tail_monotone_nonincreasing}；峰值在区间内部：${c.peak_is_interior}`)
      }
      if (c.peak_c_ug_m3 && Array.isArray(c.peak_c_ug_m3)) {
        c.peak_c_ug_m3.forEach((v, i) =>
          rows.push(`hs=${c.inputs_summary.stack_heights_m[i]} m：峰值=${v.toFixed(1)} µg/m³ @ ${c.peak_x_m[i].toFixed(0)} m`))
        rows.push(`峰值随源高降低：${c.peak_concentration_decreases}；峰值距离变远：${c.peak_distance_increases}`)
      }
      if (c.pairs) c.pairs.forEach((q) =>
        rows.push(`来向 ${q.wind_from_deg}° → 去向 ${q.transport_bearing_deg}°（期望 ${q.expected_bearing_deg}°）`))
      return h('details', null, [h('summary', null, '数值明细'),
        h('pre', null, rows.join('\n'))])
    }
  },
}
</script>
