<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const loading = ref(true)
const errorMsg = ref('')
const containerRef = ref(null)

const EDGE_HIGHLIGHT_COLOR = '#ffb300'
const CELL_HIGHLIGHT_COLOR = '#fff59d'

let tooltipEl = null

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

// Cells and edges carry `id`s baked in by scripts/generate_db_schema.py
// (`cell_<schema>_<table>_<column>_l/_m/_r` and `fkedge--<srcSig>--<dstSig>`,
// where dstSig falls back to a `tbl_<schema>_<table>` node id when the FK
// target column has no matching model). Graphviz copies `id=`/`tooltip=`
// straight through to the SVG, so no re-parsing of the .dot source is needed.
function fillableShape(el) {
  if (!el) return null
  const tag = el.tagName && el.tagName.toLowerCase()
  if (tag === 'polygon' || tag === 'ellipse' || tag === 'path') return el
  return el.querySelector('polygon, ellipse, path')
}

function cellShapes(sig) {
  return ['_l', '_m', '_r']
    .map((suffix) => document.getElementById(sig + suffix))
    .map(fillableShape)
    .filter(Boolean)
}

function setupHoverInteractions(svg) {
  tooltipEl = document.createElement('div')
  tooltipEl.className = 'db-schema-tooltip'
  document.body.appendChild(tooltipEl)

  svg.querySelectorAll('g.edge').forEach((edge) => {
    const id = edge.id || ''
    if (!id.startsWith('fkedge--')) return
    const [, srcSig, dstSig] = id.split('--')
    if (!srcSig || !dstSig) return

    const path = edge.querySelector('path')
    const arrowhead = edge.querySelector('polygon')
    const titleText = edge.querySelector('title')?.textContent || ''
    const dstIsWholeTable = dstSig.startsWith('tbl_')
    const dstShapes = () =>
      dstIsWholeTable
        ? Array.from(document.getElementById(dstSig)?.querySelectorAll('polygon, ellipse, path') || [])
        : cellShapes(dstSig)

    edge.addEventListener('mouseenter', () => {
      if (path) {
        path.style.stroke = EDGE_HIGHLIGHT_COLOR
        path.style.strokeWidth = '3'
      }
      if (arrowhead) {
        arrowhead.style.fill = EDGE_HIGHLIGHT_COLOR
        arrowhead.style.stroke = EDGE_HIGHLIGHT_COLOR
      }
      cellShapes(srcSig).forEach((shape) => { shape.style.fill = CELL_HIGHLIGHT_COLOR })
      dstShapes().forEach((shape) => { shape.style.fill = CELL_HIGHLIGHT_COLOR })

      tooltipEl.textContent = titleText
      tooltipEl.style.display = 'block'
    })

    edge.addEventListener('mousemove', (e) => {
      tooltipEl.style.left = `${e.clientX + 14}px`
      tooltipEl.style.top = `${e.clientY + 14}px`
    })

    edge.addEventListener('mouseleave', () => {
      if (path) {
        path.style.stroke = ''
        path.style.strokeWidth = ''
      }
      if (arrowhead) {
        arrowhead.style.fill = ''
        arrowhead.style.stroke = ''
      }
      cellShapes(srcSig).forEach((shape) => { shape.style.fill = '' })
      dstShapes().forEach((shape) => { shape.style.fill = '' })

      tooltipEl.style.display = 'none'
    })
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
    setupHoverInteractions(svg)
  } catch (e) {
    errorMsg.value = `無法載入 DB schema 圖：${e.message}。請先執行 python scripts/generate_db_schema.py。`
  } finally {
    loading.value = false
  }
})

onBeforeUnmount(() => {
  tooltipEl?.remove()
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
.db-schema-graph :deep(g.edge) {
  cursor: pointer;
}
</style>

<style>
/* Unscoped: tooltip is appended to document.body, outside this component's tree. */
.db-schema-tooltip {
  display: none;
  position: fixed;
  z-index: 1000;
  pointer-events: none;
  background: #1f1f1f;
  color: #fff;
  font-family: Helvetica, Arial, sans-serif;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
  white-space: nowrap;
}
</style>
