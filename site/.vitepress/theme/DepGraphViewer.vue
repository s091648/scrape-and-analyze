<script setup>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'

const CATEGORY_COLORS = {
  app: '#44BB99',
  components: '#77AADD',
  lib: '#EEDD88',
  other: '#EE8866',
}

const LAYER_RANK = { app: 0, components: 1, lib: 2, other: 3 }
const HUB_THRESHOLD = 5

const CONTEXT_COLORS = {
  session: '#77AADD',
  topic: '#44BB99',
  i18n: '#EEDD88',
  guestMode: '#EE8866',
}

const GITHUB_BASE = 'https://github.com/s091648/scrape-and-analyze/tree/master/frontend/'

// ─── State ────────────────────────────────────────────────────────────────────

const adjMap = ref({})
const errorMsg = ref('')
const selectedCategory = ref(null)
const focusNodeId = ref(null)
const selectedNode = ref(null)
const searchQuery = ref('')
const isFullscreen = ref(false)

const topMode = ref('graph')
const cycleNodes = ref(new Set())
const cycleEdges = ref(new Set())
const viewMode = ref('file')
const hoveredNode = ref(null)

const contextData = ref(null)
const contextError = ref('')
const selectedProvider = ref(null)
const expandedProviders = ref(new Set(['session']))

// Pan / zoom
const panX = ref(20)
const panY = ref(20)
const scale = ref(0.9)
let dragging = false
let dragLX = 0
let dragLY = 0

// ─── Utility ──────────────────────────────────────────────────────────────────

function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }

function classify(id) {
  if (id.startsWith('app/')) return 'app'
  if (id.startsWith('components/')) return 'components'
  if (id.startsWith('lib/')) return 'lib'
  return 'other'
}

function isHub(nodeId) {
  return (adjMap.value[nodeId]?.depended.length ?? 0) >= HUB_THRESHOLD
}

function parentDir(id) {
  const idx = id.lastIndexOf('/')
  return idx > 0 ? id.substring(0, idx) : id
}

function shortLabel(id) {
  return id.split('/').pop() || id
}

function githubUrl(path) {
  return GITHUB_BASE + path
}

// ─── Data parsing ─────────────────────────────────────────────────────────────

function parseDepsJson(json) {
  const map = {}
  for (const [src, deps] of Object.entries(json)) {
    if (!map[src]) map[src] = { category: classify(src), deps: [], depended: [] }
    for (const tgt of deps) {
      if (!map[tgt]) map[tgt] = { category: classify(tgt), deps: [], depended: [] }
      if (!map[src].deps.includes(tgt)) map[src].deps.push(tgt)
      if (!map[tgt].depended.includes(src)) map[tgt].depended.push(src)
    }
  }
  return map
}

// ─── Cycle detection ──────────────────────────────────────────────────────────

function detectCycles() {
  const map = adjMap.value
  const color = {}
  const cNodes = new Set()
  const cEdges = new Set()

  for (const n of Object.keys(map)) color[n] = 'white'

  function dfs(u, path) {
    color[u] = 'gray'
    path.push(u)
    for (const v of map[u]?.deps || []) {
      if (color[v] === 'gray') {
        const start = path.indexOf(v)
        for (let i = start; i < path.length; i++) cNodes.add(path[i])
        cEdges.add(`${u}->${v}`)
      } else if (color[v] === 'white') {
        dfs(v, path)
      }
    }
    path.pop()
    color[u] = 'black'
  }

  for (const n of Object.keys(map)) {
    if (color[n] === 'white') dfs(n, [])
  }

  cycleNodes.value = cNodes
  cycleEdges.value = cEdges
}

// ─── Directory aggregation ────────────────────────────────────────────────────

const dirAdjMap = computed(() => {
  if (viewMode.value !== 'directory') return null
  const dirMap = {}
  const dirFiles = {}

  for (const [id, info] of Object.entries(adjMap.value)) {
    const dir = parentDir(id)
    if (!dirMap[dir]) {
      dirMap[dir] = { category: classify(dir + '/x'), deps: new Set(), depended: new Set() }
      dirFiles[dir] = new Set()
    }
    dirFiles[dir].add(id)
  }

  for (const [src, info] of Object.entries(adjMap.value)) {
    const srcDir = parentDir(src)
    for (const tgt of info.deps) {
      const tgtDir = parentDir(tgt)
      if (srcDir !== tgtDir) {
        dirMap[srcDir]?.deps.add(tgtDir)
        dirMap[tgtDir]?.depended.add(srcDir)
      }
    }
  }

  const result = {}
  for (const [dir, info] of Object.entries(dirMap)) {
    result[dir] = {
      category: info.category,
      deps: [...info.deps],
      depended: [...info.depended],
      fileCount: dirFiles[dir].size,
    }
  }
  return result
})

const activeAdjMap = computed(() => viewMode.value === 'directory' ? dirAdjMap.value : adjMap.value)

// ─── Graph layout ─────────────────────────────────────────────────────────────

const CATEGORY_ORDER = ['app', 'components', 'lib', 'other']
const COL_W = 220
const NODE_H = 28
const NODE_GAP = 3
const COL_GAP = 60
const HEADER_H = 28

const graphLayout = computed(() => {
  const am = activeAdjMap.value
  if (!am) return { nodes: [], edges: [], columns: [], width: 0, height: 0 }

  // Determine visible nodes
  let visibleIds
  if (viewMode.value === 'directory') {
    visibleIds = new Set(Object.keys(am))
    if (searchQuery.value) {
      const q = searchQuery.value.toLowerCase()
      visibleIds = new Set([...visibleIds].filter(id => id.toLowerCase().includes(q)))
    }
  } else {
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
    visibleIds = new Set(ids)
  }

  // Group by category
  const columns = {}
  for (const cat of CATEGORY_ORDER) columns[cat] = []
  for (const id of visibleIds) {
    const info = am[id]
    if (!info) continue
    const cat = info.category || 'other'
    columns[cat].push(id)
  }

  // Sort within columns: fan-in descending, then alphabetical
  for (const cat of CATEGORY_ORDER) {
    columns[cat].sort((a, b) => {
      const fa = am[a]?.depended?.length ?? 0
      const fb = am[b]?.depended?.length ?? 0
      if (fb !== fa) return fb - fa
      return a.localeCompare(b)
    })
  }

  // Assign positions
  const nodePos = {}
  const colMeta = []
  let maxH = 0
  let colCount = 0

  for (let ci = 0; ci < CATEGORY_ORDER.length; ci++) {
    const cat = CATEGORY_ORDER[ci]
    const nodes = columns[cat]
    if (!nodes.length) continue

    const x = colCount * (COL_W + COL_GAP)
    for (let ni = 0; ni < nodes.length; ni++) {
      nodePos[nodes[ni]] = {
        id: nodes[ni],
        x,
        y: HEADER_H + ni * (NODE_H + NODE_GAP),
        width: COL_W,
        height: NODE_H,
        column: ci,
        category: cat,
      }
    }
    colMeta.push({ category: cat, x, count: nodes.length })
    const colH = HEADER_H + nodes.length * (NODE_H + NODE_GAP)
    if (colH > maxH) maxH = colH
    colCount++
  }

  // Compute edges
  const edges = []
  const drawnEdges = new Set()
  for (const [src, info] of Object.entries(am)) {
    if (!nodePos[src]) continue
    for (const tgt of info.deps) {
      if (!nodePos[tgt]) continue
      const key = `${src}->${tgt}`
      if (drawnEdges.has(key)) continue
      drawnEdges.add(key)

      const srcP = nodePos[src]
      const tgtP = nodePos[tgt]

      let path
      if (srcP.column < tgtP.column) {
        const sx = srcP.x + srcP.width, sy = srcP.y + srcP.height / 2
        const tx = tgtP.x, ty = tgtP.y + tgtP.height / 2
        const mx = (sx + tx) / 2
        path = `M ${sx} ${sy} C ${mx} ${sy} ${mx} ${ty} ${tx} ${ty}`
      } else if (srcP.column > tgtP.column) {
        const sx = srcP.x, sy = srcP.y + srcP.height / 2
        const tx = tgtP.x + tgtP.width, ty = tgtP.y + tgtP.height / 2
        const mx = (sx + tx) / 2
        path = `M ${sx} ${sy} C ${mx} ${sy} ${mx} ${ty} ${tx} ${ty}`
      } else {
        const sx = srcP.x + srcP.width, sy = srcP.y + srcP.height / 2
        const tx = tgtP.x + tgtP.width, ty = tgtP.y + tgtP.height / 2
        path = `M ${sx} ${sy} C ${sx + 25} ${sy} ${tx + 25} ${ty} ${tx} ${ty}`
      }

      const isCycleEdge = viewMode.value === 'file' && cycleEdges.value.has(key)
      const isViolation = viewMode.value === 'file' && LAYER_RANK[info.category] > LAYER_RANK[am[tgt]?.category]

      let color = '#ccc'
      let width = 1
      let dashed = false

      if (isCycleEdge) { color = '#e94560'; width = 2 }
      else if (isViolation) { color = '#EE8866'; dashed = true }

      if (viewMode.value === 'directory') {
        let weight = 0
        for (const [fsrc, finfo] of Object.entries(adjMap.value)) {
          if (parentDir(fsrc) !== src) continue
          for (const ftgt of finfo.deps) {
            if (parentDir(ftgt) === tgt) weight++
          }
        }
        width = Math.min(4, 1 + weight * 0.3)
        if (weight > 2) color = '#999'
      }

      edges.push({ key, source: src, target: tgt, path, color, width, dashed })
    }
  }

  return {
    nodes: Object.values(nodePos),
    edges,
    columns: colMeta,
    width: Math.max(colCount * (COL_W + COL_GAP), 400),
    height: Math.max(maxH + 20, 200),
  }
})

// ─── Computed ─────────────────────────────────────────────────────────────────

const categoryStats = computed(() =>
  Object.entries(CATEGORY_COLORS).map(([cat, color]) => ({
    key: cat,
    color,
    count: Object.values(adjMap.value).filter(v => v.category === cat).length,
  }))
)

const totalNodes = computed(() => Object.keys(adjMap.value).length)
const totalEdges = computed(() => Object.values(adjMap.value).reduce((s, v) => s + v.deps.length, 0))
const visibleNodeCount = computed(() => graphLayout.value.nodes.length)

const violationCount = computed(() => {
  let count = 0
  for (const [src, info] of Object.entries(adjMap.value)) {
    for (const tgt of info.deps) {
      if (LAYER_RANK[info.category] > LAYER_RANK[adjMap.value[tgt]?.category]) count++
    }
  }
  return count
})

// ─── Pan / zoom ───────────────────────────────────────────────────────────────

const canvasTransform = computed(() =>
  `translate(${panX.value}px, ${panY.value}px) scale(${scale.value})`
)

function onWheel(e) {
  e.preventDefault()
  scale.value = Math.max(0.1, Math.min(3, scale.value * (e.deltaY > 0 ? 0.9 : 1.1)))
}

function onDragStart(e) {
  if (e.button !== 0) return
  dragging = true
  dragLX = e.clientX - panX.value
  dragLY = e.clientY - panY.value
}

function onDragMove(e) {
  if (!dragging) return
  panX.value = e.clientX - dragLX
  panY.value = e.clientY - dragLY
}

function onDragEnd() { dragging = false }

// ─── Category / focus actions ─────────────────────────────────────────────────

function selectCategory(cat) {
  focusNodeId.value = null; selectedNode.value = null
  selectedCategory.value = selectedCategory.value === cat ? null : cat
}

function focusNode(nodeId) {
  focusNodeId.value = nodeId; selectedNode.value = nodeId; selectedCategory.value = null
  viewMode.value = 'file'
}

function clearFocus() {
  const cat = adjMap.value[focusNodeId.value]?.category
  focusNodeId.value = null; selectedCategory.value = cat || null
}

// ─── Context tab helpers ──────────────────────────────────────────────────────

function toggleProvider(id) {
  const s = new Set(expandedProviders.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedProviders.value = s
}

function selectProviderCtx(id) {
  selectedProvider.value = selectedProvider.value === id ? null : id
}

function providerConsumerList(id) {
  return contextData.value?.consumers.find(c => c.contextId === id)?.sites ?? []
}

// ─── Watchers ─────────────────────────────────────────────────────────────────

watch([selectedCategory, focusNodeId, searchQuery, viewMode], () => {})

watch(topMode, () => {
  if (topMode.value === 'graph') { selectedCategory.value = 'app'; focusNodeId.value = null; selectedNode.value = null }
})

// ─── Keyboard ─────────────────────────────────────────────────────────────────

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (isFullscreen.value) isFullscreen.value = false
    else if (selectedNode.value) selectedNode.value = null
  }
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)

  try {
    const res = await fetch('./frontend-deps.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    adjMap.value = parseDepsJson(json)
    detectCycles()
    selectedCategory.value = 'app'
  } catch (e) {
    errorMsg.value = `無法載入 frontend-deps.json：${e.message}。請先執行 make uml-frontend-deps。`
  }

  try {
    const res = await fetch('./frontend-context.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    contextData.value = await res.json()
  } catch (e) {
    contextError.value = `無法載入 frontend-context.json：${e.message}。請先執行 make uml-frontend-context。`
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="!errorMsg" :class="['dep-viewer', { fullscreen: isFullscreen }]">

    <!-- ── Top bar with tabs ─────────────────────────────────────────────── -->
    <div class="top-bar">
      <div class="tabs">
        <button :class="['tab', { active: topMode === 'graph' }]" @click="topMode = 'graph'">
          ◎ Module Graph
        </button>
        <button :class="['tab', { active: topMode === 'context' }]" @click="topMode = 'context'">
          ⟳ Provider Chain
        </button>
      </div>
      <div class="top-bar-right">
        <div class="search-wrap">
          <span class="search-icon">⌕</span>
          <input v-model="searchQuery" class="search-bar" placeholder="搜尋 module path..." />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
        </div>
        <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
          {{ isFullscreen ? '⊡' : '⊞' }}
        </button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- MODULE GRAPH TAB                                                   -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="topMode === 'graph'">

      <div class="toolbar">
        <div class="group-toggle">
          <button :class="['gm-btn', { active: viewMode === 'file' }]" @click="viewMode = 'file'">File</button>
          <button :class="['gm-btn', { active: viewMode === 'directory' }]" @click="viewMode = 'directory'">Directory</button>
        </div>
        <span class="stat">{{ visibleNodeCount }} / {{ totalNodes }} modules · {{ totalEdges }} imports</span>
        <span v-if="cycleNodes.size" class="badge cycle-badge">{{ cycleNodes.size }} cycle nodes</span>
        <span v-if="violationCount" class="badge violation-badge">{{ violationCount }} violations</span>
        <span v-if="focusNodeId" class="focus-badge">
          Focus: {{ focusNodeId.split('/').pop() }}
          <button @click="clearFocus" class="clear-btn">✕</button>
        </span>
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

        <!-- Graph viewport with pan/zoom -->
        <div class="graph-viewport"
          @wheel.prevent="onWheel"
          @mousedown="onDragStart"
          @mousemove="onDragMove"
          @mouseup="onDragEnd"
          @mouseleave="onDragEnd"
        >
          <div class="graph-canvas" :style="{ transform: canvasTransform }">
            <!-- Column headers -->
            <div v-for="col in graphLayout.columns" :key="col.category"
              class="column-header" :style="{ left: col.x + 'px' }"
            >
              <span class="column-dot" :style="{ background: CATEGORY_COLORS[col.category] }" />
              <span class="column-name">{{ col.category }}/</span>
              <span class="column-count">{{ col.count }}</span>
            </div>

            <!-- SVG edges -->
            <svg class="edge-layer"
              :width="graphLayout.width + 80"
              :height="graphLayout.height + 40"
            >
              <path
                v-for="edge in graphLayout.edges" :key="edge.key"
                :d="edge.path"
                fill="none"
                :stroke="edge.color"
                :stroke-width="edge.width"
                :stroke-dasharray="edge.dashed ? '6,3' : ''"
                :class="[
                  hoveredNode && edge.source === hoveredNode ? 'edge-highlight' : '',
                  hoveredNode && edge.source !== hoveredNode && edge.target !== hoveredNode ? 'edge-dim' : '',
                ]"
              />
            </svg>

            <!-- Nodes -->
            <div
              v-for="node in graphLayout.nodes" :key="node.id"
              :class="['graph-node', {
                'node-selected': node.id === selectedNode,
                'node-focused': node.id === focusNodeId,
                'node-hub': isHub(node.id),
                'node-cycle': cycleNodes.has(node.id),
                'node-dim': hoveredNode && node.id !== hoveredNode && !adjMap[node.id]?.deps?.includes(hoveredNode) && !adjMap[node.id]?.depended?.includes(hoveredNode),
              }]"
              :style="{
                left: node.x + 'px',
                top: node.y + 'px',
                width: node.width + 'px',
                borderColor: node.id === focusNodeId ? '#e94560' : node.id === selectedNode ? 'var(--vp-c-brand)' : CATEGORY_COLORS[node.category] || '#888',
              }"
              @mouseenter="hoveredNode = node.id"
              @mouseleave="hoveredNode = null"
              @click.stop="selectedNode = node.id"
            >
              <span class="node-label" :style="{ color: CATEGORY_COLORS[node.category] || '#888' }">{{ shortLabel(node.id) }}</span>
              <span v-if="viewMode === 'directory' && dirAdjMap?.[node.id]" class="node-filecount">{{ dirAdjMap[node.id].fileCount }} files</span>
            </div>
          </div>
        </div>

        <!-- Detail panel -->
        <div v-if="selectedNode && (adjMap[selectedNode] || dirAdjMap?.[selectedNode])" class="detail-panel">
          <div class="detail-header">
            <h3>{{ selectedNode.split('/').pop() }}</h3>
            <button class="close-btn" @click="selectedNode = null">✕</button>
          </div>
          <a v-if="viewMode === 'file'" class="detail-source" :href="githubUrl(selectedNode)" target="_blank" rel="noopener">{{ selectedNode }}</a>
          <div v-else class="detail-module">{{ selectedNode }}</div>
          <div class="detail-meta">
            <span class="badge" :style="{ background: CATEGORY_COLORS[(adjMap[selectedNode] || dirAdjMap?.[selectedNode])?.category] || '#888' }">
              {{ (adjMap[selectedNode] || dirAdjMap?.[selectedNode])?.category }}
            </span>
            <span v-if="isHub(selectedNode)" class="badge hub-badge">Hub</span>
            <span v-if="cycleNodes.has(selectedNode)" class="badge cycle-badge-sm">In cycle</span>
          </div>

          <div class="detail-metrics">
            <div class="metric">
              <span class="metric-label">Fan-out</span>
              <span class="metric-value">{{ (adjMap[selectedNode] || dirAdjMap?.[selectedNode])?.deps?.length ?? 0 }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Fan-in</span>
              <span class="metric-value">{{ (adjMap[selectedNode] || dirAdjMap?.[selectedNode])?.depended?.length ?? 0 }}</span>
            </div>
          </div>

          <!-- Directory mode: list files -->
          <template v-if="viewMode === 'directory' && dirAdjMap?.[selectedNode]">
            <div class="section-title">Files ({{ dirAdjMap[selectedNode].fileCount }})</div>
            <div v-for="id in Object.keys(adjMap).filter(n => parentDir(n) === selectedNode).slice(0, 20)" :key="id" class="rel-line" @click="focusNode(id)">
              {{ id.split('/').pop() }}
            </div>
            <div v-if="dirAdjMap[selectedNode].fileCount > 20" class="rel-line more-line">+{{ dirAdjMap[selectedNode].fileCount - 20 }} more</div>
          </template>

          <template v-if="adjMap[selectedNode]?.deps?.length">
            <div class="section-title">Imports ({{ adjMap[selectedNode].deps.length }})</div>
            <div v-for="d in adjMap[selectedNode].deps" :key="d" class="rel-line" @click="focusNode(d)">
              → {{ d }}
            </div>
          </template>

          <template v-if="adjMap[selectedNode]?.depended?.length">
            <div class="section-title">Imported by ({{ adjMap[selectedNode].depended.length }})</div>
            <div v-for="d in adjMap[selectedNode].depended" :key="d" class="rel-line" @click="focusNode(d)">
              ← {{ d }}
            </div>
          </template>

          <button class="focus-btn" @click="focusNode(selectedNode)">Focus: Node + Neighbors</button>
        </div>
      </div>

    </template>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- PROVIDER CHAIN TAB                                                 -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="topMode === 'context'">

      <div v-if="contextError" class="error-msg">{{ contextError }}</div>

      <div v-else-if="contextData" class="context-layout">

        <div class="context-tree">
          <div class="context-tree-title">Provider Nesting</div>
          <div v-for="provider in contextData.providers" :key="provider.id"
            class="provider-card"
            :style="{ marginLeft: (provider.nestingLevel * 24) + 'px', borderLeftColor: CONTEXT_COLORS[provider.id] || '#888' }"
          >
            <div class="provider-header" @click="selectProviderCtx(provider.id)">
              <span v-if="provider.nestingLevel > 0" class="tree-connector">└─</span>
              <span class="provider-name" :style="{ color: CONTEXT_COLORS[provider.id] }">{{ provider.name }}</span>
              <span class="provider-count" :style="{ background: (CONTEXT_COLORS[provider.id] || '#888') + '22', color: CONTEXT_COLORS[provider.id] }">
                {{ provider.consumerCount }} consumers
              </span>
            </div>
            <a class="provider-file" :href="githubUrl(provider.file)" target="_blank" rel="noopener">{{ provider.file }}</a>
            <div class="provider-desc">{{ provider.description }}</div>
            <button class="provider-expand-btn" @click.stop="toggleProvider(provider.id)">
              {{ expandedProviders.has(provider.id) ? '▼' : '▶' }} Consumers
            </button>
            <div v-if="expandedProviders.has(provider.id)" class="provider-consumers-list">
              <div v-for="site in providerConsumerList(provider.id)" :key="site.file + site.line" class="consumer-line">
                <a class="consumer-file" :href="githubUrl(site.file)" target="_blank" rel="noopener">{{ site.file }}</a>
                <span v-if="site.destructured" class="consumer-destructured">{{ site.destructured }}</span>
                <span class="consumer-line-num">:{{ site.line }}</span>
              </div>
              <div v-if="!providerConsumerList(provider.id).length" class="consumer-line empty">No consumers</div>
            </div>
          </div>

          <!-- Cross-context dependencies -->
          <div v-if="contextData.crossContextDeps?.length" class="cross-ctx-section">
            <div class="cross-ctx-title">Cross-Context Dependencies</div>
            <div v-for="dep in contextData.crossContextDeps" :key="dep.from + dep.to" class="cross-ctx-card">
              <div class="cross-ctx-from" :style="{ color: CONTEXT_COLORS[dep.from] }">
                {{ contextData.providers.find(p => p.id === dep.from)?.name }}
              </div>
              <div class="cross-ctx-arrow">→</div>
              <div class="cross-ctx-to" :style="{ color: CONTEXT_COLORS[dep.to] }">
                {{ contextData.providers.find(p => p.id === dep.to)?.name }}
              </div>
              <div class="cross-ctx-desc">{{ dep.description }}</div>
              <div class="cross-ctx-evidence">
                <a class="consumer-file" :href="githubUrl(dep.evidence.file)" target="_blank" rel="noopener">{{ dep.evidence.file }}</a>
                <span class="consumer-line-num">:{{ dep.evidence.line }}</span>
              </div>
              <code class="cross-ctx-code">{{ dep.evidence.code }}</code>
            </div>
          </div>

          <!-- Summary -->
          <div class="context-summary">
            <div class="summary-item">
              <span class="summary-label">Total consumer sites</span>
              <span class="summary-value">{{ contextData.summary.totalConsumerSites }}</span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Most consumed</span>
              <span class="summary-value" :style="{ color: CONTEXT_COLORS[contextData.summary.mostConsumedContext] }">
                {{ contextData.providers.find(p => p.id === contextData.summary.mostConsumedContext)?.name }}
              </span>
            </div>
            <div class="summary-item">
              <span class="summary-label">Nesting depth</span>
              <span class="summary-value">{{ contextData.summary.maxNestingDepth + 1 }} levels</span>
            </div>
          </div>
        </div>

        <!-- Right: Selected provider detail -->
        <div v-if="selectedProvider" class="context-detail">
          <div class="nav-bar">
            <span class="nav-provider-name" :style="{ color: CONTEXT_COLORS[selectedProvider] }">
              {{ contextData.providers.find(p => p.id === selectedProvider)?.name }}
            </span>
            <span class="nav-count">{{ providerConsumerList(selectedProvider).length }} consumers</span>
            <button class="close-btn" @click="selectedProvider = null">✕</button>
          </div>
          <div class="consumer-card-grid">
            <div v-for="site in providerConsumerList(selectedProvider)" :key="site.file + site.line" class="consumer-card">
              <a class="consumer-card-file" :href="githubUrl(site.file)" target="_blank" rel="noopener">{{ site.file }}</a>
              <div v-if="site.destructured" class="consumer-card-destructured">{{ site.destructured }}</div>
              <div class="consumer-card-line">line {{ site.line }}</div>
            </div>
            <div v-if="!providerConsumerList(selectedProvider).length" class="empty-msg">No consumers</div>
          </div>
        </div>
        <div v-else class="context-detail-empty">
          <p>點擊左側 Provider 查看消費者分佈</p>
        </div>

      </div>
    </template>

  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>
</template>

<style scoped>
.dep-viewer { display: flex; flex-direction: column; height: calc(100vh - 140px); border: 1px solid var(--vp-c-border); border-radius: 8px; overflow: hidden; }
.dep-viewer.fullscreen { position: fixed; inset: 0; z-index: 9999; height: 100vh; border-radius: 0; border: none; }

/* ── Top bar ──────────────────────────────────────────────────────────────── */
.top-bar { display: flex; align-items: center; justify-content: space-between; padding: 0 12px; background: var(--vp-c-bg-soft); border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; gap: 8px; }
.tabs { display: flex; flex-shrink: 0; }
.tab { padding: 9px 16px; background: none; border: none; border-bottom: 2px solid transparent; font-size: 13px; color: var(--vp-c-text-2); cursor: pointer; transition: color .15s, border-color .15s; }
.tab.active { color: var(--vp-c-brand); border-bottom-color: var(--vp-c-brand); font-weight: 600; }
.tab:hover:not(.active) { color: var(--vp-c-text-1); }
.top-bar-right { display: flex; align-items: center; gap: 8px; }
.search-wrap { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 7px; font-size: 15px; color: var(--vp-c-text-3); pointer-events: none; }
.search-bar { padding: 4px 28px 4px 26px; border-radius: 16px; border: 1px solid var(--vp-c-border); background: var(--vp-c-bg); color: var(--vp-c-text-1); width: 200px; font-size: 12px; transition: border-color .15s, width .2s; }
.search-bar:focus { outline: none; border-color: var(--vp-c-brand); width: 260px; }
.search-clear { position: absolute; right: 7px; background: none; border: none; color: var(--vp-c-text-3); cursor: pointer; font-size: 11px; padding: 0; }
.search-clear:hover { color: var(--vp-c-text-1); }
.fullscreen-btn { background: none; border: 1px solid var(--vp-c-border); border-radius: 4px; padding: 3px 9px; cursor: pointer; font-size: 16px; color: var(--vp-c-text-2); transition: background .12s; flex-shrink: 0; }
.fullscreen-btn:hover { background: var(--vp-c-bg-mute); }

/* ── Toolbar ──────────────────────────────────────────────────────────────── */
.toolbar { display: flex; align-items: center; gap: 12px; padding: 6px 12px; background: var(--vp-c-bg-soft); border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; flex-wrap: wrap; }
.group-toggle { display: flex; border: 1px solid var(--vp-c-border); border-radius: 5px; overflow: hidden; flex-shrink: 0; }
.gm-btn { background: none; border: none; padding: 3px 10px; font-size: 12px; cursor: pointer; color: var(--vp-c-text-2); transition: background .12s; }
.gm-btn:hover { background: var(--vp-c-bg-mute); }
.gm-btn.active { background: var(--vp-c-brand); color: #fff; font-weight: 600; }
.stat { font-size: 12px; color: var(--vp-c-text-2); }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.cycle-badge { background: rgba(233,69,96,.15); color: #e94560; }
.cycle-badge-sm { background: #e94560; color: #fff; font-size: 10px; }
.violation-badge { background: rgba(238,136,102,.15); color: #EE8866; }
.hub-badge { background: var(--vp-c-brand); color: #fff; font-size: 10px; }
.focus-badge { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #e94560; background: rgba(233,69,96,.1); padding: 2px 8px; border-radius: 12px; }
.clear-btn { background: none; border: none; color: #e94560; cursor: pointer; font-size: 12px; padding: 0; }

/* ── Layout ────────────────────────────────────────────────────────────────── */
.layout { display: flex; flex: 1; overflow: hidden; }
.sidebar { width: 170px; flex-shrink: 0; overflow-y: auto; padding: 8px 0; background: var(--vp-c-bg-soft); border-right: 1px solid var(--vp-c-border); }
.sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); padding: 4px 12px 8px; letter-spacing: .05em; }
.layer-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; cursor: pointer; font-size: 12px; transition: background .15s; }
.layer-item:hover { background: var(--vp-c-bg-mute); }
.layer-item.active { background: var(--vp-c-bg-mute); font-weight: 600; }
.dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.name { flex: 1; color: var(--vp-c-text-1); }
.count { font-size: 11px; color: var(--vp-c-text-2); background: var(--vp-c-bg-mute); padding: 1px 6px; border-radius: 8px; }

/* ── Graph viewport ───────────────────────────────────────────────────────── */
.graph-viewport {
  flex: 1; overflow: hidden; cursor: grab; background: var(--vp-c-bg);
  user-select: none; position: relative;
}
.graph-viewport:active { cursor: grabbing; }
.graph-canvas {
  position: absolute; top: 0; left: 0;
  transform-origin: 0 0;
  min-width: 100%; min-height: 100%;
}

/* ── Column headers ──────────────────────────────────────────────────────── */
.column-header {
  position: absolute; top: 0;
  display: flex; align-items: center; gap: 6px;
  height: 28px; padding: 0 8px;
  font-size: 12px; font-weight: 700;
  border-bottom: 2px solid var(--vp-c-border);
}
.column-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.column-name { color: var(--vp-c-text-2); }
.column-count { font-size: 11px; color: var(--vp-c-text-3); background: var(--vp-c-bg-mute); padding: 1px 6px; border-radius: 8px; }

/* ── SVG edges ──────────────────────────────────────────────────────────── */
.edge-layer { position: absolute; top: 0; left: 0; pointer-events: none; }
.edge-highlight { stroke-opacity: 1 !important; stroke-width: 2 !important; }
.edge-dim { stroke-opacity: 0.2; }

/* ── Graph nodes ─────────────────────────────────────────────────────────── */
.graph-node {
  position: absolute;
  height: 28px;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  border-radius: 4px;
  background: var(--vp-c-bg-soft);
  display: flex; align-items: center; gap: 6px;
  padding: 0 8px;
  cursor: pointer;
  transition: background .12s, border-color .12s, box-shadow .12s;
  font-size: 12px;
}
.graph-node:hover { background: var(--vp-c-bg-mute); box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.graph-node.node-selected { background: var(--vp-c-bg-mute); box-shadow: 0 0 0 1px var(--vp-c-brand); }
.graph-node.node-focused { background: rgba(233,69,96,.08); box-shadow: 0 0 0 1px #e94560; }
.graph-node.node-hub { font-weight: 600; border-left-width: 4px; }
.graph-node.node-cycle { border-color: #e94560; background: rgba(233,69,96,.06); }
.graph-node.node-dim { opacity: 0.35; }
.node-label { font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.node-filecount { font-size: 10px; color: var(--vp-c-text-3); flex-shrink: 0; }

/* ── Detail panel ────────────────────────────────────────────────────────── */
.detail-panel { width: 280px; flex-shrink: 0; overflow-y: auto; padding: 12px; background: var(--vp-c-bg-soft); border-left: 1px solid var(--vp-c-border); font-size: 13px; }
.detail-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 4px; }
.detail-header h3 { font-size: 14px; font-weight: 600; margin: 0; word-break: break-all; }
.close-btn { background: none; border: none; color: var(--vp-c-text-2); cursor: pointer; font-size: 14px; padding: 0; flex-shrink: 0; }
.detail-source { display: block; font-size: 11px; color: var(--vp-c-brand); font-family: monospace; margin-bottom: 6px; word-break: break-all; text-decoration: none; }
.detail-source:hover { text-decoration: underline; }
.detail-module { font-size: 11px; color: var(--vp-c-text-2); font-family: monospace; margin-bottom: 6px; word-break: break-all; }
.detail-meta { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 8px; }
.detail-metrics { display: flex; gap: 16px; margin-bottom: 8px; padding: 6px 0; border-top: 1px solid var(--vp-c-border); border-bottom: 1px solid var(--vp-c-border); }
.metric { display: flex; flex-direction: column; align-items: center; }
.metric-label { font-size: 10px; color: var(--vp-c-text-3); text-transform: uppercase; letter-spacing: .05em; }
.metric-value { font-size: 18px; font-weight: 700; color: var(--vp-c-text-1); }
.section-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); margin: 10px 0 4px; letter-spacing: .05em; }
.rel-line { font-size: 11px; color: var(--vp-c-brand); padding: 2px 0; cursor: pointer; font-family: monospace; word-break: break-all; }
.rel-line:hover { text-decoration: underline; }
.more-line { color: var(--vp-c-text-3); cursor: default; }
.more-line:hover { text-decoration: none; }
.focus-btn { width: 100%; margin-top: 12px; padding: 6px 12px; background: #e94560; color: #fff; border: none; border-radius: 4px; cursor: pointer; font-size: 12px; }
.focus-btn:hover { opacity: .9; }
.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
.empty-msg { padding: 2rem; text-align: center; color: var(--vp-c-text-2); }

/* ── Provider Chain tab ──────────────────────────────────────────────────── */
.context-layout { display: flex; flex: 1; overflow: hidden; }
.context-tree { flex: 1; overflow-y: auto; padding: 16px; min-width: 0; }
.context-tree-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); margin-bottom: 12px; letter-spacing: .05em; }

.provider-card { border: 1px solid var(--vp-c-border); border-left-width: 4px; border-radius: 8px; padding: 10px 12px; margin-bottom: 8px; background: var(--vp-c-bg-soft); transition: background .15s; }
.provider-card:hover { background: var(--vp-c-bg-mute); }
.provider-header { display: flex; align-items: center; gap: 8px; cursor: pointer; margin-bottom: 4px; flex-wrap: wrap; }
.tree-connector { color: var(--vp-c-text-3); font-family: monospace; }
.provider-name { font-size: 14px; font-weight: 700; }
.provider-count { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.provider-file { font-size: 11px; color: var(--vp-c-brand); font-family: monospace; margin-bottom: 4px; text-decoration: none; display: block; word-break: break-all; }
.provider-file:hover { text-decoration: underline; }
.provider-desc { font-size: 12px; color: var(--vp-c-text-2); margin-bottom: 6px; }
.provider-expand-btn { background: none; border: 1px solid var(--vp-c-border); border-radius: 4px; padding: 2px 8px; font-size: 11px; color: var(--vp-c-text-2); cursor: pointer; transition: background .12s; }
.provider-expand-btn:hover { background: var(--vp-c-bg-mute); }

.provider-consumers-list { margin-top: 6px; padding: 6px 8px; background: var(--vp-c-bg); border-radius: 6px; border: 1px solid var(--vp-c-border); }
.consumer-line { display: flex; align-items: center; gap: 8px; padding: 2px 0; font-size: 11px; }
.consumer-file { font-family: monospace; color: var(--vp-c-brand); word-break: break-all; flex: 1; text-decoration: none; }
.consumer-file:hover { text-decoration: underline; }
.consumer-destructured { font-family: monospace; color: var(--vp-c-text-2); font-size: 10px; }
.consumer-line-num { color: var(--vp-c-text-3); flex-shrink: 0; }
.consumer-line.empty { color: var(--vp-c-text-3); font-style: italic; }

.cross-ctx-section { margin-top: 16px; padding-top: 12px; border-top: 1px solid var(--vp-c-border); }
.cross-ctx-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); margin-bottom: 8px; letter-spacing: .05em; }
.cross-ctx-card { border: 1px dashed var(--vp-c-border); border-radius: 8px; padding: 10px 12px; background: rgba(238,136,102,.06); }
.cross-ctx-from, .cross-ctx-to { font-size: 13px; font-weight: 700; display: inline; }
.cross-ctx-arrow { display: inline; font-size: 14px; color: var(--vp-c-text-3); margin: 0 6px; }
.cross-ctx-desc { font-size: 12px; color: var(--vp-c-text-2); margin-top: 6px; }
.cross-ctx-evidence { margin-top: 4px; }
.cross-ctx-code { display: block; font-size: 11px; margin-top: 4px; padding: 4px 8px; background: var(--vp-c-bg-mute); border-radius: 4px; font-family: monospace; color: var(--vp-c-text-2); }

.context-summary { margin-top: 16px; display: flex; gap: 16px; flex-wrap: wrap; padding-top: 12px; border-top: 1px solid var(--vp-c-border); }
.summary-item { display: flex; flex-direction: column; }
.summary-label { font-size: 10px; color: var(--vp-c-text-3); text-transform: uppercase; letter-spacing: .05em; }
.summary-value { font-size: 14px; font-weight: 700; color: var(--vp-c-text-1); }

.context-detail { width: 320px; flex-shrink: 0; overflow-y: auto; border-left: 1px solid var(--vp-c-border); background: var(--vp-c-bg-soft); }
.context-detail-empty { flex: 0 0 320px; display: flex; align-items: center; justify-content: center; color: var(--vp-c-text-3); font-size: 13px; border-left: 1px solid var(--vp-c-border); background: var(--vp-c-bg); }
.nav-bar { display: flex; align-items: center; gap: 10px; padding: 10px 12px; border-bottom: 1px solid var(--vp-c-border); }
.nav-provider-name { font-size: 14px; font-weight: 700; flex: 1; }
.nav-count { font-size: 12px; color: var(--vp-c-text-2); }

.consumer-card-grid { padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.consumer-card { border: 1px solid var(--vp-c-border); border-radius: 6px; padding: 8px 10px; background: var(--vp-c-bg); transition: background .15s; }
.consumer-card:hover { background: var(--vp-c-bg-mute); }
.consumer-card-file { font-size: 12px; font-family: monospace; font-weight: 600; color: var(--vp-c-brand); word-break: break-all; text-decoration: none; display: block; }
.consumer-card-file:hover { text-decoration: underline; }
.consumer-card-destructured { font-size: 11px; font-family: monospace; color: var(--vp-c-text-2); margin-top: 2px; }
.consumer-card-line { font-size: 10px; color: var(--vp-c-text-3); margin-top: 2px; }
</style>
