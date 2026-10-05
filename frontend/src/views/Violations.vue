<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const viols = ref<any[]>([])
const unplaced = ref<any[]>([])
const rejections = ref<any[]>([])
onMounted(async () => {
  try {
    const res = await api('/seating/violations?hall_id=1')
    viols.value = res.violations; unplaced.value = res.unplaced
  } catch { /* 尚无方案：违规账为空 */ }
  rejections.value = await api('/seating/rejections?hall_id=1')
})
</script>
<template>
  <h1>违规</h1>
  <p class="sub">间距不足或同试卷四邻相邻</p>
  <div class="card">
    <table>
      <thead><tr><th>类型</th><th>考生A</th><th>考生B</th><th>说明</th></tr></thead>
      <tbody>
        <tr v-for="(v,i) in viols" :key="i">
          <td>{{ v.kind }}</td><td>{{ v.a_id }}</td><td>{{ v.b_id }}</td><td>{{ v.detail }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!viols.length" class="muted">无违规</p>
  </div>
  <div class="card" v-if="unplaced.length">
    <h3>未排上</h3>
    <div v-for="u in unplaced" :key="u.id">{{ u.name }}（{{ u.ticket_no }}）</div>
  </div>
  <div class="card">
    <h3>拒绝记录</h3>
    <table>
      <thead><tr><th>时间</th><th>原因码</th><th>说明</th><th>已写库</th></tr></thead>
      <tbody>
        <tr v-for="r in rejections" :key="r.id">
          <td>{{ r.created_at }}</td><td>{{ r.reason_code }}</td><td>{{ r.detail }}</td>
          <td><span class="badge badge-bad">否</span></td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rejections.length" class="muted">无拒绝记录</p>
  </div>
</template>
