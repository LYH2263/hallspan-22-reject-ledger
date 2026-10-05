<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
onMounted(async () => { rows.value = await api('/seating/rejections') })
</script>
<template>
  <h1>拒绝记录</h1>
  <p class="sub">排座失败留痕 · 每次失败一行 · 是否写库恒为否 · 成功不会删减历史记录</p>
  <div class="card">
    <table>
      <thead><tr><th>时间</th><th>考室</th><th>原因码</th><th>说明</th><th>是否写库</th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.rejection_id">
          <td>{{ r.created_at }}</td>
          <td>{{ r.hall_id }}</td>
          <td><span class="badge badge-bad">{{ r.reason_code }}</span></td>
          <td>{{ r.detail }}</td>
          <td>{{ r.persisted ? '是' : '否' }}</td>
        </tr>
      </tbody>
    </table>
    <p v-if="!rows.length" class="muted">暂无拒绝记录</p>
  </div>
</template>
