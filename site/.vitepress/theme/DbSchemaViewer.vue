<script setup>
import { ref, onMounted } from 'vue'

const loading = ref(true)
const errorMsg = ref('')
const containerRef = ref(null)

// Same CDN build + global-script loading pattern as viewer.html (the UML page's
// viewer), which already proves this works client-side in this VitePress site.
function loadVizScript() {
  return new Promise((resolve, reject) => {
    if (window.Viz) { resolve(); return }
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/@viz-js/viz@3.4.0/lib/viz-standalone.js'
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('failed to load viz-standalone.js'))
    document.head.appendChild(script)
  })
}

onMounted(async () => {
  try {
    const res = await fetch('./db-schema.dot')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const dotSource = await res.text()

    await loadVizScript()
    const viz = await window.Viz.instance()
    const svg = viz.renderSVGElement(dotSource)
    svg.removeAttribute('width')
    svg.removeAttribute('height')
    svg.style.maxWidth = '100%'
    containerRef.value.appendChild(svg)
  } catch (e) {
    errorMsg.value = `無法載入 DB schema 圖：${e.message}。請先執行 python scripts/generate_db_schema.py。`
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="db-schema-viewer">
    <div v-if="loading" class="db-schema-loading">Loading…</div>
    <div v-else-if="errorMsg" class="db-schema-error">{{ errorMsg }}</div>
    <div ref="containerRef" class="db-schema-graph"></div>
  </div>
</template>

<style scoped>
.db-schema-viewer {
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  padding: 12px;
  overflow: auto;
  background: var(--vp-c-bg-soft);
}
.db-schema-loading,
.db-schema-error {
  padding: 2rem;
  text-align: center;
  color: var(--vp-c-text-2);
}
.db-schema-graph {
  display: flex;
  justify-content: center;
}
</style>
