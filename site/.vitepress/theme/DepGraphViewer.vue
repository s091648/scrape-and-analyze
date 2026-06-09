<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useData } from 'vitepress'

const CATEGORY_COLORS = {
  app: '#44BB99',
  components: '#77AADD',
  lib: '#EEDD88',
  other: '#EE8866',
}

const LAYER_RANK = { app: 0, components: 1, lib: 2, other: 3 }

const CONTEXT_COLORS = {
  session: '#77AADD',
  topic: '#44BB99',
  i18n: '#EEDD88',
  guestMode: '#EE8866',
}

const GITHUB_BASE = 'https://github.com/s091648/scrape-and-analyze/tree/master/frontend/'

const { theme } = useData()

// ─── State ────────────────────────────────────────────────────────────────────

const adjMap = ref({})
const errorMsg = ref('')
const searchQuery = ref('')
const isFullscreen = ref(false)

const topMode = ref('graph')
const cycleNodes = ref(new Set())
const cycleEdges = ref(new Set())

const hoveredNode = ref(null)
const expandedDir = ref(null)
const violationPopupOpen = ref(false)

const contextData = ref(null)
const contextError = ref('')
const selectedProvider = ref(null)
const expandedProviders = ref(new Set(['session']))

// Pan / zoom
const INIT_PAN_X = 20
const INIT_PAN_Y = 20
const INIT_SCALE = 0.9
const panX = ref(INIT_PAN_X)
const panY = ref(INIT_PAN_Y)
const scale = ref(INIT_SCALE)
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

function parentDir(id) {
  const idx = id.lastIndexOf('/')
  return idx > 0 ? id.substring(0, idx) : id
}

function shortLabel(id) {
  const parts = id.split('/')
  return parts.length > 1 ? parts.slice(1).join('/') : id
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

const dirFileIds = computed(() => {
  const map = {}
  for (const id of Object.keys(adjMap.value)) {
    const dir = parentDir(id)
    if (!map[dir]) map[dir] = []
    map[dir].push(id)
  }
  for (const dir of Object.keys(map)) {
    map[dir].sort()
  }
  return map
})

const dirCycleNodes = computed(() => {
  const dirs = new Set()
  for (const fileId of cycleNodes.value) {
    dirs.add(parentDir(fileId))
  }
  return dirs
})

// ─── Graph layout ─────────────────────────────────────────────────────────────

const CATEGORY_ORDER = ['app', 'components', 'lib', 'other']
const COL_W = 240
const DIR_NODE_H = 32
const FILE_NODE_H = 24
const NODE_GAP = 3
const COL_GAP = 60
const HEADER_H = 28
const EXPAND_INDENT = 16

const graphLayout = computed(() => {
  const am = dirAdjMap.value
  if (!am) return { nodes: [], edges: [], columns: [], width: 0, height: 0 }

  let visibleIds = new Set(Object.keys(am))
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    visibleIds = new Set([...visibleIds].filter(id => id.toLowerCase().includes(q)))
  }

  const columns = {}
  for (const cat of CATEGORY_ORDER) columns[cat] = []
  for (const id of visibleIds) {
    const info = am[id]
    if (!info) continue
    const cat = info.category || 'other'
    columns[cat].push(id)
  }

  for (const cat of CATEGORY_ORDER) {
    columns[cat].sort((a, b) => {
      const fa = am[a]?.depended?.length ?? 0
      const fb = am[b]?.depended?.length ?? 0
      if (fb !== fa) return fb - fa
      return a.localeCompare(b)
    })
  }

  const nodePos = {}
  const colMeta = []
  let maxH = 0
  let colCount = 0

  for (let ci = 0; ci < CATEGORY_ORDER.length; ci++) {
    const cat = CATEGORY_ORDER[ci]
    const nodes = columns[cat]
    if (!nodes.length) continue

    const x = colCount * (COL_W + COL_GAP)
    let y = HEADER_H

    for (let ni = 0; ni < nodes.length; ni++) {
      const dirId = nodes[ni]
      const isExpanded = expandedDir.value === dirId

      nodePos[dirId] = {
        id: dirId,
        x,
        y,
        width: COL_W,
        height: DIR_NODE_H,
        column: ci,
        category: cat,
        type: 'directory',
      }
      y += DIR_NODE_H + NODE_GAP

      if (isExpanded && dirFileIds.value[dirId]) {
        const files = dirFileIds.value[dirId]
        for (const fileId of files) {
          nodePos[fileId] = {
            id: fileId,
            x: x + EXPAND_INDENT,
            y,
            width: COL_W - EXPAND_INDENT,
            height: FILE_NODE_H,
            column: ci,
            category: adjMap.value[fileId]?.category || cat,
            type: 'file',
            parentDir: dirId,
          }
          y += FILE_NODE_H + NODE_GAP
        }
        y += 6
      }
    }

    colMeta.push({ category: cat, x, count: nodes.length })
    if (y > maxH) maxH = y
    colCount++
  }

  // Directory-level edges
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

      let weight = 0
      for (const [fsrc, finfo] of Object.entries(adjMap.value)) {
        if (parentDir(fsrc) !== src) continue
        for (const ftgt of finfo.deps) {
          if (parentDir(ftgt) === tgt) weight++
        }
      }

      edges.push({
        key, source: src, target: tgt, path,
        color: weight > 2 ? '#999' : '#ccc',
        width: Math.min(4, 1 + weight * 0.3),
        dashed: false,
        type: 'directory',
      })
    }
  }

  // Intra-directory file edges for expanded directory
  if (expandedDir.value && dirFileIds.value[expandedDir.value]) {
    const dirId = expandedDir.value
    const files = dirFileIds.value[dirId]
    const fileSet = new Set(files)

    for (const fileId of files) {
      const fileInfo = adjMap.value[fileId]
      if (!fileInfo) continue
      for (const dep of fileInfo.deps) {
        if (!fileSet.has(dep)) continue
        if (!nodePos[fileId] || !nodePos[dep]) continue

        const key = `file:${fileId}->${dep}`
        if (drawnEdges.has(key)) continue
        drawnEdges.add(key)

        const srcP = nodePos[fileId]
        const tgtP = nodePos[dep]

        const sx = srcP.x + srcP.width, sy = srcP.y + srcP.height / 2
        const tx = tgtP.x + tgtP.width, ty = tgtP.y + tgtP.height / 2
        const path = `M ${sx} ${sy} C ${sx + 20} ${sy} ${tx + 20} ${ty} ${tx} ${ty}`

        const isViolation = LAYER_RANK[fileInfo.category] > LAYER_RANK[adjMap.value[dep]?.category]
        const isCycleEdge = cycleEdges.value.has(`${fileId}->${dep}`)

        let edgeColor = CATEGORY_COLORS[fileInfo.category] || '#999'
        let edgeDashed = false
        if (isCycleEdge) { edgeColor = '#e94560' }
        else if (isViolation) { edgeColor = '#EE8866'; edgeDashed = true }

        edges.push({
          key,
          source: fileId,
          target: dep,
          path,
          color: edgeColor,
          width: 1,
          dashed: edgeDashed,
          type: 'file',
        })
      }
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

const storybookUrl = computed(() => theme.value.storybookUrl || '')

const totalNodes = computed(() => Object.keys(adjMap.value).length)
const totalEdges = computed(() => Object.values(adjMap.value).reduce((s, v) => s + v.deps.length, 0))
const dirCount = computed(() => Object.keys(dirAdjMap.value).length)

const violationCount = computed(() => {
  let count = 0
  for (const [src, info] of Object.entries(adjMap.value)) {
    for (const tgt of info.deps) {
      if (LAYER_RANK[info.category] > LAYER_RANK[adjMap.value[tgt]?.category]) count++
    }
  }
  return count
})

const violationDetails = computed(() => {
  const details = []
  for (const [src, info] of Object.entries(adjMap.value)) {
    for (const tgt of info.deps) {
      if (LAYER_RANK[info.category] > LAYER_RANK[adjMap.value[tgt]?.category]) {
        details.push({
          source: src,
          target: tgt,
          sourceLayer: info.category,
          targetLayer: adjMap.value[tgt]?.category || 'other',
        })
      }
    }
  }
  return details
})

// ─── Node dimming ────────────────────────────────────────────────────────────

function shouldDimNode(node) {
  if (expandedDir.value) {
    if (node.type === 'directory') return node.id !== expandedDir.value
    if (node.type === 'file') return node.parentDir !== expandedDir.value
    return true
  }
  if (hoveredNode.value) {
    if (node.id === hoveredNode.value) return false
    const info = adjMap.value[node.id]
    if (info?.deps?.includes(hoveredNode.value) || info?.depended?.includes(hoveredNode.value)) return false
    const dirInfo = dirAdjMap.value[node.id]
    if (dirInfo?.deps?.includes(hoveredNode.value) || dirInfo?.depended?.includes(hoveredNode.value)) return false
    return true
  }
  return false
}

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

function resetView() {
  panX.value = INIT_PAN_X
  panY.value = INIT_PAN_Y
  scale.value = INIT_SCALE
}

// ─── Directory actions ────────────────────────────────────────────────────────

function toggleExpandDir(dirId) {
  expandedDir.value = expandedDir.value === dirId ? null : dirId
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

watch(searchQuery, () => {})

watch(topMode, () => {
  if (topMode.value === 'graph') { expandedDir.value = null; hoveredNode.value = null }
})

// ─── Keyboard ─────────────────────────────────────────────────────────────────

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (isFullscreen.value) isFullscreen.value = false
    else if (violationPopupOpen.value) violationPopupOpen.value = false
    else if (expandedDir.value) expandedDir.value = null
  }
}

function onClickOutside(e) {
  if (violationPopupOpen.value && !e.target.closest('.violation-badge-wrap')) {
    violationPopupOpen.value = false
  }
}

// ─── Lifecycle ────────────────────────────────────────────────────────────────

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('click', onClickOutside)

  try {
    const res = await fetch('./frontend-deps.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const json = await res.json()
    adjMap.value = parseDepsJson(json)
    detectCycles()
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
  document.removeEventListener('click', onClickOutside)
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
        <button :class="['tab', { active: topMode === 'storybook' }]" @click="topMode = 'storybook'">
          ⧉ Storybook
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
        <span class="stat">{{ dirCount }} directories · {{ totalNodes }} files · {{ totalEdges }} imports</span>
        <span v-if="cycleNodes.size" class="badge cycle-badge">{{ cycleNodes.size }} cycle nodes</span>
        <span class="violation-badge-wrap">
          <span v-if="violationCount" class="badge violation-badge clickable" @click.stop="violationPopupOpen = !violationPopupOpen">
            {{ violationCount }} violations
          </span>
          <div v-if="violationPopupOpen" class="violation-popup" @click.stop>
            <div class="violation-popup-header">
              <h3>Layer Violations</h3>
              <button class="close-btn" @click="violationPopupOpen = false">✕</button>
            </div>
            <div class="violation-popup-desc">Higher-layer modules importing from lower layers (app → components → lib → other)</div>
            <div class="violation-list">
              <div v-for="(v, i) in violationDetails" :key="i" class="violation-item">
                <span class="violation-src" :style="{ color: CATEGORY_COLORS[v.sourceLayer] }">{{ v.source }}</span>
                <span class="violation-arrow">→</span>
                <span class="violation-tgt" :style="{ color: CATEGORY_COLORS[v.targetLayer] }">{{ v.target }}</span>
                <span class="violation-layers">{{ v.sourceLayer }} → {{ v.targetLayer }}</span>
              </div>
            </div>
          </div>
        </span>
        <span v-if="expandedDir" class="focus-badge">
          ▼ {{ expandedDir.split('/').pop() }}
          <button @click="expandedDir = null" class="clear-btn">✕</button>
        </span>
      </div>

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
                edge.type === 'file' ? 'edge-file' : '',
                hoveredNode && edge.source === hoveredNode ? 'edge-highlight' : '',
                hoveredNode && edge.source !== hoveredNode && edge.target !== hoveredNode ? 'edge-dim' : '',
                expandedDir && edge.type === 'directory' && edge.source !== expandedDir && edge.target !== expandedDir ? 'edge-dim' : '',
              ]"
            />
          </svg>

          <!-- Nodes -->
          <div
            v-for="node in graphLayout.nodes" :key="node.id"
            :class="['graph-node', {
              'node-dir': node.type === 'directory',
              'node-file': node.type === 'file',
              'node-expanded-dir': node.type === 'directory' && node.id === expandedDir,
              'node-cycle': node.type === 'directory' && dirCycleNodes.has(node.id),
              'node-file-cycle': node.type === 'file' && cycleNodes.has(node.id),
              'node-dim': shouldDimNode(node),
            }]"
            :style="{
              left: node.x + 'px',
              top: node.y + 'px',
              width: node.width + 'px',
              height: node.height + 'px',
              borderColor: node.type === 'directory' && node.id === expandedDir
                ? '#e94560'
                : CATEGORY_COLORS[node.category] || '#888',
            }"
            @mouseenter="hoveredNode = node.id"
            @mouseleave="hoveredNode = null"
            @click.stop="node.type === 'directory' ? toggleExpandDir(node.id) : undefined"
          >
            <span v-if="node.type === 'directory'" class="node-expand-icon">{{ node.id === expandedDir ? '▼' : '▶' }}</span>
            <span class="node-label" :style="{ color: CATEGORY_COLORS[node.category] || '#888' }">{{ shortLabel(node.id) }}</span>
            <span v-if="node.type === 'directory' && dirAdjMap?.[node.id]" class="node-filecount">{{ dirAdjMap[node.id].fileCount }} files</span>
            <a v-if="node.type === 'file'" class="node-file-link" :href="githubUrl(node.id)" target="_blank" rel="noopener" @click.stop>↗</a>
          </div>
        </div>
        <button class="reset-view-btn" @click.stop="resetView" title="重置視角">⊹ Reset</button>
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

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- STORYBOOK TAB                                                       -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="topMode === 'storybook'">
      <div v-if="storybookUrl" class="storybook-frame">
        <iframe :src="storybookUrl" allowfullscreen />
      </div>
      <div v-else class="storybook-empty">
        <p>Storybook URL 未設定。</p>
        <p>請在 GitHub repo variables 加入 <code>STORYBOOK_URL</code>，並確認 <code>config.js</code> 已加入 <code>storybookUrl</code>。</p>
      </div>
    </template>

  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>
</template>

<style scoped>
.dep-viewer { display: flex; flex-direction: column; height: calc(100vh - 140px); border: 1px solid var(--vp-c-border); border-radius: 8px; overflow: hidden; background: var(--vp-c-bg); }
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
.toolbar { display: flex; align-items: center; gap: 12px; padding: 6px 12px; background: var(--vp-c-bg-soft); border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; flex-wrap: wrap; position: relative; }
.stat { font-size: 12px; color: var(--vp-c-text-2); }
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
.cycle-badge { background: rgba(233,69,96,.15); color: #e94560; }
.violation-badge { background: rgba(238,136,102,.15); color: #EE8866; }
.violation-badge.clickable { cursor: pointer; transition: background .15s; }
.violation-badge.clickable:hover { background: rgba(238,136,102,.3); }
.focus-badge { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #e94560; background: rgba(233,69,96,.1); padding: 2px 8px; border-radius: 12px; }
.clear-btn { background: none; border: none; color: #e94560; cursor: pointer; font-size: 12px; padding: 0; }

/* ── Violation popup ──────────────────────────────────────────────────────── */
.violation-badge-wrap { position: relative; }
.violation-popup {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  z-index: 100;
  width: 520px;
  max-height: 400px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,.15);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.violation-popup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  border-bottom: 1px solid var(--vp-c-border);
}
.violation-popup-header h3 { font-size: 13px; font-weight: 600; margin: 0; }
.violation-popup-desc { font-size: 11px; color: var(--vp-c-text-2); padding: 8px 14px; border-bottom: 1px solid var(--vp-c-border); }
.violation-list { overflow-y: auto; padding: 6px 0; flex: 1; }
.violation-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  font-size: 11px;
  font-family: monospace;
}
.violation-item:hover { background: var(--vp-c-bg-mute); }
.violation-src { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.violation-arrow { color: var(--vp-c-text-3); flex-shrink: 0; }
.violation-tgt { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.violation-layers { font-size: 10px; color: var(--vp-c-text-3); flex-shrink: 0; font-family: sans-serif; padding: 1px 6px; background: var(--vp-c-bg-mute); border-radius: 4px; }

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
.edge-dim { stroke-opacity: 0.15; }
.edge-file { stroke-opacity: 0.6; }

/* ── Graph nodes ─────────────────────────────────────────────────────────── */
.graph-node {
  position: absolute;
  border: 1px solid transparent;
  border-left: 3px solid transparent;
  border-radius: 4px;
  background: var(--vp-c-bg-soft);
  display: flex; align-items: center; gap: 6px;
  padding: 0 8px;
  cursor: pointer;
  transition: background .12s, border-color .12s, box-shadow .12s, opacity .2s;
  font-size: 12px;
}

/* Directory node */
.node-dir {
  height: 32px;
  border-left-width: 4px;
}
.node-dir:hover { background: var(--vp-c-bg-mute); box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.node-expanded-dir {
  background: rgba(233,69,96,.06);
  box-shadow: 0 0 0 1px #e94560;
}
.node-expand-icon { font-size: 9px; color: var(--vp-c-text-3); flex-shrink: 0; width: 12px; text-align: center; }
.node-filecount { font-size: 10px; color: var(--vp-c-text-3); flex-shrink: 0; }

/* File node */
.node-file {
  height: 24px;
  border-left-width: 2px;
  background: var(--vp-c-bg);
  font-size: 11px;
}
.node-file:hover { background: var(--vp-c-bg-mute); box-shadow: 0 1px 3px rgba(0,0,0,.06); }

/* Cycle */
.node-cycle { border-color: #e94560; background: rgba(233,69,96,.06); }
.node-file-cycle { border-color: #e94560; background: rgba(233,69,96,.04); }

/* Dimming */
.node-dim { opacity: 0.3; }

/* Labels */
.node-label { font-family: monospace; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.node-file-link {
  font-size: 11px;
  color: var(--vp-c-brand);
  text-decoration: none;
  flex-shrink: 0;
  opacity: 0.6;
  transition: opacity .12s;
}
.node-file-link:hover { opacity: 1; text-decoration: underline; }

.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
.empty-msg { padding: 2rem; text-align: center; color: var(--vp-c-text-2); }

/* ── Reset view button ───────────────────────────────────────────────────────── */
.reset-view-btn {
  position: absolute; bottom: 12px; right: 12px; z-index: 10;
  background: var(--vp-c-bg-soft); border: 1px solid var(--vp-c-border);
  border-radius: 6px; padding: 5px 10px; font-size: 12px;
  color: var(--vp-c-text-2); cursor: pointer; transition: background .12s;
}
.reset-view-btn:hover { background: var(--vp-c-bg-mute); color: var(--vp-c-text-1); }

/* ── Storybook tab ───────────────────────────────────────────────────────────── */
.storybook-frame { flex: 1; overflow: hidden; }
.storybook-frame iframe { width: 100%; height: 100%; border: none; display: block; }
.storybook-empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px; color: var(--vp-c-text-2); font-size: 14px; text-align: center; padding: 2rem; }
.storybook-empty code { font-size: 12px; background: var(--vp-c-bg-mute); padding: 2px 6px; border-radius: 4px; }

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
