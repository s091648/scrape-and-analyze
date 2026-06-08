<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'

const CATEGORY_COLORS = {
  app: '#44BB99',
  components: '#77AADD',
  lib: '#EEDD88',
  other: '#EE8866',
}

const adjMap = ref({})   // { nodeId: { category, deps: string[], depended: string[] } }
const errorMsg = ref('')
const selectedCategory = ref(null)
const focusNodeId = ref(null)
const selectedNode = ref(null)
const searchQuery = ref('')
const graphEl = ref(null)
const isFullscreen = ref(false)
let vizInstance = null

function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }

function classify(id) {
  if (id.startsWith('app/')) return 'app'
  if (id.startsWith('components/')) return 'components'
  if (id.startsWith('lib/')) return 'lib'
  return 'other'
}

async function loadViz() {
  if (typeof window === 'undefined') return null
  if (window.__vizInstance) return window.__vizInstance
  await new Promise((resolve, reject) => {
    if (document.querySelector('#viz-script')) { resolve(); return }
    const s = document.createElement('script')
    s.id = 'viz-script'
    s.src = 'https://cdn.jsdelivr.net/npm/@viz-js/viz@3.4.0/lib/viz-standalone.js'
    s.onload = resolve; s.onerror = reject
    document.head.appendChild(s)
  })
  window.__vizInstance = await window.Viz.instance()
  return window.__vizInstance
}

function parseDot(source) {
  const map = {}
  const edgeRe = /"([^"]+)"\s*->\s*"([^"]+)"/g
  let m
  while ((m = edgeRe.exec(source)) !== null) {
    const [, src, tgt] = m
    if (!map[src]) map[src] = { category: classify(src), deps: [], depended: [] }
    if (!map[tgt]) map[tgt] = { category: classify(tgt), deps: [], depended: [] }
    map[src].deps.push(tgt)
    map[tgt].depended.push(src)
  }
  return map
}

const categoryStats = computed(() =>
  Object.entries(CATEGORY_COLORS).map(([cat, color]) => ({
    key: cat,
    color,
    count: Object.values(adjMap.value).filter(v => v.category === cat).length,
  }))
)

const totalNodes = computed(() => Object.keys(adjMap.value).length)
const totalEdges = computed(() => Object.values(adjMap.value).reduce((s, v) => s + v.deps.length, 0))

const displayNodeIds = computed(() => {
  let ids = Object.keys(adjMap.value)

  if (focusNodeId.value) {
    const nid = focusNodeId.value
    const neighbors = new Set([nid])
    adjMap.value[nid]?.deps.forEach(d => neighbors.add(d))
    adjMap.value[nid]?.depended.forEach(d => neighbors.add(d))
    ids = ids.filter(id => neighbors.has(id))
  } else if (selectedCategory.value) {
    ids = ids.filter(id => adjMap.value[id]?.category === selectedCategory.value)
  }

  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    ids = ids.filter(id => id.toLowerCase().includes(q))
  }
  return new Set(ids)
})

function buildDot() {
  if (!displayNodeIds.value.size) return ''
  let dot = 'digraph {\n  rankdir=LR\n  splines=ortho\n  nodesep=0.3\n  ranksep=1.0\n  fontsize=10\n'
  dot += '  node [shape=box, style=rounded, fontsize=9]\n\n'

  for (const id of displayNodeIds.value) {
    const cat = adjMap.value[id]?.category || 'other'
    const isFocus = id === focusNodeId.value
    const color = isFocus ? '#e94560' : (CATEGORY_COLORS[cat] || '#888')
    const label = id.split('/').pop() || id
    dot += `  "${id}" [label="${label}", color="${color}", fontcolor="${color}"${isFocus ? ', penwidth=2' : ''}, tooltip="${id}"]\n`
  }
  dot += '\n'

  for (const [src, info] of Object.entries(adjMap.value)) {
    if (!displayNodeIds.value.has(src)) continue
    for (const tgt of info.deps) {
      if (displayNodeIds.value.has(tgt)) dot += `  "${src}" -> "${tgt}"\n`
    }
  }
  dot += '}\n'
  return dot
}

async function render() {
  if (!vizInstance || !graphEl.value) return
  const dot = buildDot()
  if (!dot) {
    graphEl.value.innerHTML = '<p class="empty-msg">No modules to show.</p>'
    return
  }
  try {
    const svg = vizInstance.renderSVGElement(dot)
    svg.style.width = '100%'; svg.style.height = '100%'
    graphEl.value.innerHTML = ''
    graphEl.value.appendChild(svg)
    setupPanZoom(svg)
    wireClicks(svg)
  } catch (e) {
    graphEl.value.innerHTML = `<p style="color:red;padding:1rem">Render error: ${e.message}</p>`
  }
}

function setupPanZoom(svg) {
  let scale = 0.9, panX = 20, panY = 20, dragging = false, lx = 0, ly = 0
  const apply = () => { svg.style.transform = `translate(${panX}px,${panY}px) scale(${scale})`; svg.style.transformOrigin = '0 0' }
  apply()
  graphEl.value.addEventListener('wheel', e => {
    e.preventDefault()
    scale = Math.max(0.05, Math.min(5, scale * (e.deltaY > 0 ? 0.9 : 1.1)))
    apply()
  })
  graphEl.value.addEventListener('mousedown', e => { dragging = true; lx = e.clientX; ly = e.clientY })
  window.addEventListener('mousemove', e => { if (!dragging) return; panX += e.clientX - lx; panY += e.clientY - ly; lx = e.clientX; ly = e.clientY; apply() })
  window.addEventListener('mouseup', () => { dragging = false })
}

function wireClicks(svg) {
  svg.querySelectorAll('g').forEach(g => {
    const title = g.querySelector('title')
    if (!title) return
    const nodeId = title.textContent.trim()
    if (!adjMap.value[nodeId]) return
    g.style.cursor = 'pointer'
    g.addEventListener('click', e => { e.stopPropagation(); selectedNode.value = nodeId })
  })
}

function selectCategory(cat) {
  focusNodeId.value = null; selectedNode.value = null
  selectedCategory.value = selectedCategory.value === cat ? null : cat
}

function focusNode(nodeId) {
  focusNodeId.value = nodeId; selectedNode.value = nodeId; selectedCategory.value = null
}

function clearFocus() {
  const cat = adjMap.value[focusNodeId.value]?.category
  focusNodeId.value = null; selectedCategory.value = cat || null
}

watch([selectedCategory, focusNodeId, searchQuery], async () => { await nextTick(); render() })

onMounted(async () => {
  try {
    vizInstance = await loadViz()
    const res = await fetch('./frontend.dot')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const source = await res.text()
    adjMap.value = parseDot(source)
    selectedCategory.value = 'app'
  } catch (e) {
    errorMsg.value = `無法載入 frontend.dot：${e.message}。請先執行 make uml-frontend。`
  }
})
</script>

<template>
  <div v-if="!errorMsg" :class="['dep-viewer', { fullscreen: isFullscreen }]">
    <div class="toolbar">
      <input v-model="searchQuery" class="search" placeholder="搜尋 module path..." />
      <span class="stat">{{ displayNodeIds.size }} / {{ totalNodes }} modules · {{ totalEdges }} imports total</span>
      <span v-if="focusNodeId" class="focus-badge">
        Focus: {{ focusNodeId.split('/').pop() }}
        <button @click="clearFocus" class="clear-btn">✕ Clear</button>
      </span>
      <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
        {{ isFullscreen ? '⊡' : '⊞' }}
      </button>
    </div>

    <div class="layout">
      <div class="sidebar">
        <div class="sidebar-title">Category</div>
        <div
          v-for="cat in categoryStats" :key="cat.key"
          :class="['layer-item', { active: selectedCategory === cat.key }]"
          @click="selectCategory(cat.key)"
        >
          <span class="dot" :style="{ background: cat.color }" />
          <span class="name">{{ cat.key }}/</span>
          <span class="count">{{ cat.count }}</span>
        </div>
        <div
          :class="['layer-item', { active: !selectedCategory && !focusNodeId }]"
          @click="selectedCategory = null; focusNodeId = null; selectedNode = null"
        >
          <span class="dot" style="background:#888" />
          <span class="name">All</span>
          <span class="count">{{ totalNodes }}</span>
        </div>
      </div>

      <div ref="graphEl" class="graph-canvas" />

      <div v-if="selectedNode && adjMap[selectedNode]" class="detail-panel">
        <div class="detail-header">
          <h3>{{ selectedNode.split('/').pop() }}</h3>
          <button class="close-btn" @click="selectedNode = null">✕</button>
        </div>
        <div class="detail-module">{{ selectedNode }}</div>
        <div class="detail-meta">
          <span class="badge" :style="{ background: CATEGORY_COLORS[adjMap[selectedNode].category] }">
            {{ adjMap[selectedNode].category }}
          </span>
        </div>

        <template v-if="adjMap[selectedNode].deps.length">
          <div class="section-title">Imports ({{ adjMap[selectedNode].deps.length }})</div>
          <div v-for="d in adjMap[selectedNode].deps" :key="d" class="rel-line" @click="focusNode(d)">
            → {{ d }}
          </div>
        </template>

        <template v-if="adjMap[selectedNode].depended.length">
          <div class="section-title">Imported by ({{ adjMap[selectedNode].depended.length }})</div>
          <div v-for="d in adjMap[selectedNode].depended" :key="d" class="rel-line" @click="focusNode(d)">
            ← {{ d }}
          </div>
        </template>

        <button class="focus-btn" @click="focusNode(selectedNode)">Focus: Node + Neighbors</button>
      </div>
    </div>
  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>
</template>

<style scoped>
.dep-viewer { display: flex; flex-direction: column; height: calc(100vh - 140px); border: 1px solid var(--vp-c-border); border-radius: 8px; overflow: hidden; }
.dep-viewer.fullscreen { position: fixed; inset: 0; z-index: 9999; height: 100vh; border-radius: 0; border: none; }

.toolbar { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: var(--vp-c-bg-soft); border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; flex-wrap: wrap; }
.search { padding: 4px 10px; border-radius: 4px; border: 1px solid var(--vp-c-border); background: var(--vp-c-bg); color: var(--vp-c-text-1); width: 220px; font-size: 13px; }
.stat { font-size: 12px; color: var(--vp-c-text-2); }
.focus-badge { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #e94560; background: rgba(233,69,96,.1); padding: 2px 8px; border-radius: 12px; }
.clear-btn { background: none; border: none; color: #e94560; cursor: pointer; font-size: 12px; padding: 0; }
.fullscreen-btn { margin-left: auto; background: none; border: 1px solid var(--vp-c-border); border-radius: 4px; padding: 3px 9px; cursor: pointer; font-size: 16px; color: var(--vp-c-text-2); transition: background .12s; }
.fullscreen-btn:hover { background: var(--vp-c-bg-mute); }

.layout { display: flex; flex: 1; overflow: hidden; }

.sidebar { width: 170px; flex-shrink: 0; overflow-y: auto; padding: 8px 0; background: var(--vp-c-bg-soft); border-right: 1px solid var(--vp-c-border); }
.sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); padding: 4px 12px 8px; letter-spacing: .05em; }
.layer-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; cursor: pointer; font-size: 12px; transition: background .15s; }
.layer-item:hover { background: var(--vp-c-bg-mute); }
.layer-item.active { background: var(--vp-c-bg-mute); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.name { flex: 1; color: var(--vp-c-text-1); }
.count { font-size: 11px; color: var(--vp-c-text-2); background: var(--vp-c-bg-mute); padding: 1px 6px; border-radius: 8px; }

.graph-canvas { flex: 1; overflow: hidden; cursor: grab; background: var(--vp-c-bg); }
.graph-canvas:active { cursor: grabbing; }
.empty-msg { padding: 2rem; text-align: center; color: var(--vp-c-text-2); }

.detail-panel { width: 280px; flex-shrink: 0; overflow-y: auto; padding: 12px; background: var(--vp-c-bg-soft); border-left: 1px solid var(--vp-c-border); font-size: 13px; }
.detail-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 8px; }
.detail-header h3 { font-size: 14px; font-weight: 600; margin: 0; word-break: break-all; }
.close-btn { background: none; border: none; color: var(--vp-c-text-2); cursor: pointer; font-size: 14px; padding: 0; flex-shrink: 0; }
.detail-module { font-size: 11px; color: var(--vp-c-text-2); font-family: monospace; margin-bottom: 6px; word-break: break-all; }
.detail-meta { margin-bottom: 8px; }
.badge { font-size: 11px; color: #fff; padding: 2px 8px; border-radius: 10px; }
.section-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); margin: 10px 0 4px; letter-spacing: .05em; }
.rel-line { font-size: 11px; color: var(--vp-c-brand); padding: 2px 0; cursor: pointer; font-family: monospace; word-break: break-all; }
.rel-line:hover { text-decoration: underline; }
.focus-btn { width: 100%; margin-top: 12px; padding: 6px 12px; background: #e94560; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
.focus-btn:hover { opacity: .9; }
.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
</style>
