<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api, ApiError } from '../api'
const data = ref<any>(null)
const halls = ref<any[]>([])
const hallId = ref(1)
const allCandidates = ref<any[]>([])
const violKeys = ref<Set<string>>(new Set())
const rejection = ref<any>(null)
const candidates = computed(() => allCandidates.value.filter(c => c.hall_id === hallId.value))
async function refreshViolKeys() {
  try {
    const v = await api(`/seating/violations?hall_id=${hallId.value}`)
    const keys = new Set<string>()
    for (const x of v.violations || []) {
      if (x.a_id != null) keys.add(String(x.a_id))
      if (x.b_id != null) keys.add(String(x.b_id))
    }
    violKeys.value = keys
  } catch { violKeys.value = new Set() }
}
async function run() {
  try {
    data.value = await api(`/seating/run?hall_id=${hallId.value}`, { method: 'POST' })
    rejection.value = null
    await refreshViolKeys()
  } catch (e) {
    // 失败走拒绝账：图保持操作前，只展示拒绝行
    if (e instanceof ApiError && e.body && e.body.reason_code) {
      rejection.value = e.body
    } else {
      rejection.value = { reason_code: 'REQUEST_FAILED', detail: String(e), persisted: false }
    }
  }
}
async function loadLatest() {
  rejection.value = null
  data.value = null
  try {
    data.value = await api(`/seating/latest?hall_id=${hallId.value}`)
    await refreshViolKeys()
  } catch {
    await run()
  }
}
onMounted(async () => {
  halls.value = await api('/halls')
  allCandidates.value = await api('/candidates')
  if (halls.value.length && !halls.value.some(h => h.id === hallId.value)) hallId.value = halls.value[0].id
  await loadLatest()
})
const gridStyle = computed(() => data.value ? ({ gridTemplateColumns: `repeat(${data.value.cols}, 72px)` }) : {})
const cells = computed(() => {
  if (!data.value) return []
  const map = new Map<string, any>()
  for (const a of data.value.assignments || []) map.set(a.row + ',' + a.col, a)
  const out: any[] = []
  for (let r = 0; r < data.value.rows; r++) {
    for (let c = 0; c < data.value.cols; c++) {
      out.push(map.get(r + ',' + c) || { empty: true, row: r, col: c })
    }
  }
  return out
})
function isViol(cell: any) {
  if (cell.empty) return false
  const id = cell.candidate_id ?? cell.id
  return id != null && violKeys.value.has(String(id))
}
function paperClass(pid: number) {
  return pid % 2 === 0 ? 'b' : 'a'
}
</script>
<template>
  <h1>考场课桌网格</h1>
  <p class="sub">课桌网格为主视图 · 左侧考生名册夹板 · 违规课桌高亮</p>
  <div style="display:flex;gap:0.6rem;align-items:center">
    <select class="btn" v-model.number="hallId" @change="loadLatest">
      <option v-for="h in halls" :key="h.id" :value="h.id">{{ h.name }}{{ h.closed ? '（封闭）' : '' }}</option>
    </select>
    <button class="btn" @click="run">重新排座</button>
  </div>
  <div v-if="rejection" class="card hs-rejection" role="alert">
    <strong>排座被拒绝（{{ rejection.reason_code }}）</strong>
    <div>{{ rejection.detail }}</div>
    <div class="muted">是否写库：否 · 方案账未变，上图仍为操作前方案 · 详见<RouterLink to="/rejections">拒绝记录</RouterLink></div>
  </div>
  <div class="hs-classroom" style="margin-top:0.85rem">
    <aside class="hs-clipboard">
      <h2>考生名册</h2>
      <div v-for="c in candidates" :key="c.id" class="hs-roster-row">
        <div>
          <div>{{ c.name }}</div>
          <div class="hs-ticket">{{ c.ticket_no }}</div>
        </div>
        <div>卷{{ c.paper_id }}</div>
      </div>
    </aside>
    <div class="hs-desk-stage" v-if="data">
      <div class="hs-grid-board" :style="gridStyle">
        <div
          v-for="(cell,i) in cells" :key="i"
          class="hs-desk"
          :class="{ empty: cell.empty, 'hs-viol': isViol(cell) }"
        >
          <template v-if="!cell.empty">
            <span class="hs-paper-tag" :class="paperClass(cell.paper_id)">卷{{ cell.paper_id }}</span>
            <div>{{ cell.name }}</div>
          </template>
          <template v-else>·</template>
        </div>
      </div>
    </div>
    <div v-else class="card">暂无排座方案，点击「重新排座」生成。</div>
  </div>
</template>
