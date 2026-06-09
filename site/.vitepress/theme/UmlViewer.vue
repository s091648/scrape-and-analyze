<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

// ─── Constants ─────────────────────────────────────────────────────────────────

const CA_CIRCLES = [
  { id: 'infrastructure', label: 'Infrastructure',    color: '#BBCC33', outerR: 320, innerR: 240 },
  { id: 'adapters',       label: 'Interface Adapters',color: '#EEDD88', outerR: 240, innerR: 165 },
  { id: 'application',    label: 'Application',       color: '#44BB99', outerR: 165, innerR:  90 },
  { id: 'entities',       label: 'Domain / Entities', color: '#77AADD', outerR:  90, innerR:   0 },
]

const LAYER_COLORS = {
  entrypoints: '#e94560', application: '#44BB99', domain: '#77AADD',
  'shared-application': '#99DDFF', 'infrastructure-collection': '#BBCC33',
  'infrastructure-persistence': '#AAAA00', 'infrastructure-intelligence': '#EEDD88',
  'infrastructure-shared': '#EE8866', config: '#DDDDDD', unknown: '#888888',
}

// ─── State ─────────────────────────────────────────────────────────────────────

const umlData        = ref(null)
const errorMsg       = ref('')
const topMode        = ref('ca')      // 'ca' | 'pipeline'
const caView         = ref('overview') // 'overview' | 'layer' | 'subgroup'
const selCircle      = ref(null)
const selSubgroup    = ref(null)
const hoveredRing    = ref(null)
const expandedStages    = ref(new Set())
const expandedCards     = ref(new Set())
const expandedDddLayers = ref(new Set(['domain', 'application', 'infrastructure', 'adapters']))
const highlightedId     = ref(null)
const isFullscreen      = ref(false)
const searchQuery       = ref('')

// Dialog history stack — enables card-shuffle navigation
const dialogHistory  = ref([])   // array of nodes
const dialogIndex    = ref(-1)   // current position in history
const dialogSlideDir = ref('right') // animation direction

const dialogNode = computed(() => dialogHistory.value[dialogIndex.value] ?? null)

// Module (use-case) view state
const moduleCtx  = ref(null)   // selected context object {id, label, nodes}
const moduleView = ref('grid') // 'grid' | 'detail'

// ─── DDD layer groups (used in module tab) ──────────────────────────────────

const DDD_LAYER_GROUPS = [
  { id: 'domain',        label: 'Domain',              color: '#77AADD',
    test: l => l === 'domain' },
  { id: 'application',   label: 'Application',         color: '#44BB99',
    test: l => l === 'application' || l === 'shared-application' },
  { id: 'infrastructure',label: 'Infrastructure',      color: '#BBCC33',
    test: l => l !== 'domain' && l !== 'application' && l !== 'shared-application' },
]

const CONTEXT_LABELS = {
  collection: 'Collection', intelligence: 'Intelligence', shared: 'Shared',
  notifications: 'Notifications', entrypoints: 'Entrypoints',
  config: 'Config', bootstrap: 'Bootstrap', other: 'Other',
}

const CONTEXT_ICONS = {
  collection: '📋', intelligence: '🧠', shared: '🔗',
  notifications: '📢', entrypoints: '🚀', config: '⚙️',
  bootstrap: '🏗️', other: '📦',
}

// ─── SVG helper ───────────────────────────────────────────────────────────────

function ringPath(outerR, innerR) {
  const o = `M ${outerR},0 A ${outerR},${outerR},0,1,0,${-outerR},0 A ${outerR},${outerR},0,1,0,${outerR},0 Z`
  if (innerR <= 0) return o
  const i = `M ${innerR},0 A ${innerR},${innerR},0,1,1,${-innerR},0 A ${innerR},${innerR},0,1,1,${innerR},0 Z`
  return `${o} ${i}`
}

// ─── Computed ──────────────────────────────────────────────────────────────────

const circles = computed(() =>
  CA_CIRCLES.map(c => {
    const found = umlData.value?.circles?.find(x => x.id === c.id)
    return { ...c, count: found?.count ?? 0, subgroups: found?.subgroups ?? [] }
  })
)

const subgraphNodes = computed(() => {
  if (!umlData.value || !selCircle.value || !selSubgroup.value) return []
  return umlData.value.nodes.filter(
    n => n.ca_layer === selCircle.value.id && n.subgroup === selSubgroup.value.id
  )
})

const pipelineStages = computed(() => umlData.value?.pipeline ?? [])

const searchLower = computed(() => searchQuery.value.toLowerCase().trim())
function nodeMatchesSearch(node) {
  if (!searchLower.value) return true
  const q = searchLower.value
  return (
    node.class_name.toLowerCase().includes(q) ||
    (node.docstring || '').toLowerCase().includes(q) ||
    (node.module || '').toLowerCase().includes(q)
  )
}

const filteredSubgraphNodes = computed(() =>
  subgraphNodes.value.filter(nodeMatchesSearch)
)

// Flat search results across ALL nodes — shown in overview and layer views when searching
const searchResults = computed(() => {
  if (!searchLower.value || !umlData.value) return []
  return umlData.value.nodes.filter(nodeMatchesSearch)
})

// Filter folder cards in CA layer view (structural subgroups only)
const filteredSubgroups = computed(() => {
  if (!selCircle.value || !umlData.value) return []
  const sgs = circles.value.find(c => c.id === selCircle.value.id)?.subgroups ?? []
  if (!searchLower.value) return sgs
  return sgs.filter(sg =>
    umlData.value.nodes.some(
      n => n.ca_layer === selCircle.value.id && n.subgroup === sg.id && nodeMatchesSearch(n)
    )
  )
})

// ── Module (use-case) tab computed ──────────────────────────────────────────

const allModuleContexts = computed(() => {
  if (!umlData.value) return []
  const map = {}
  for (const n of umlData.value.nodes) {
    if (!map[n.context]) map[n.context] = { id: n.context, nodes: [] }
    map[n.context].nodes.push(n)
  }
  const ORDER = ['collection','intelligence','shared','notifications','entrypoints','config','bootstrap','other']
  return Object.values(map).sort((a, b) => {
    const ai = ORDER.indexOf(a.id), bi = ORDER.indexOf(b.id)
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi)
  })
})

const moduleDddGroups = computed(() => {
  if (!moduleCtx.value || !umlData.value) return []
  const ctxNodes = moduleCtx.value.nodes.filter(nodeMatchesSearch)
  return DDD_LAYER_GROUPS.map(g => ({
    ...g,
    nodes: ctxNodes.filter(n => g.test(n.layer)),
  })).filter(g => g.nodes.length > 0)
})

// ─── Dialog helpers ───────────────────────────────────────────────────────────

function findNodeById(id) {
  return umlData.value?.nodes.find(n => n.id === id) ?? null
}

function openDialog(node) {
  if (!node) return
  // Truncate forward history when branching to a new card
  const history = dialogHistory.value.slice(0, dialogIndex.value + 1)
  history.push(node)
  dialogSlideDir.value = 'right'
  dialogHistory.value = history
  dialogIndex.value = history.length - 1
}

function closeDialog() {
  dialogHistory.value = []
  dialogIndex.value = -1
}

function dialogGoBack() {
  if (dialogIndex.value > 0) {
    dialogSlideDir.value = 'left'
    dialogIndex.value--
  }
}

function dialogGoForward() {
  if (dialogIndex.value < dialogHistory.value.length - 1) {
    dialogSlideDir.value = 'right'
    dialogIndex.value++
  }
}

function dialogGoToIndex(i) {
  if (i === dialogIndex.value) return
  dialogSlideDir.value = i > dialogIndex.value ? 'right' : 'left'
  dialogIndex.value = i
}

// ─── CA navigation ────────────────────────────────────────────────────────────

function selectCircle(c) { selCircle.value = c; selSubgroup.value = null; caView.value = 'layer' }
function selectSubgroup(sg) { selSubgroup.value = sg; caView.value = 'subgroup' }
function caGoBack() {
  if (caView.value === 'subgroup') { caView.value = 'layer'; selSubgroup.value = null }
  else { caView.value = 'overview'; selCircle.value = null }
}
function caGoOverview() { caView.value = 'overview'; selCircle.value = null; selSubgroup.value = null }

// ─── Pipeline helpers ─────────────────────────────────────────────────────────

function toggleStage(id) {
  const s = new Set(expandedStages.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedStages.value = s
}

function getStageNodes(classNames) {
  if (!umlData.value) return []
  const nodes = classNames
    .map(name => umlData.value.nodes.find(n => n.class_name === name))
    .filter(Boolean)
  return searchLower.value ? nodes.filter(nodeMatchesSearch) : nodes
}

// ─── Card helpers ─────────────────────────────────────────────────────────────

function cardId(nodeId) { return 'cc-' + nodeId.replace(/\./g, '-') }

function scrollToCard(nodeId) {
  const el = document.getElementById(cardId(nodeId))
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  highlightedId.value = nodeId
  setTimeout(() => { if (highlightedId.value === nodeId) highlightedId.value = null }, 1800)
}

function toggleCardMethods(nodeId) {
  const s = new Set(expandedCards.value)
  s.has(nodeId) ? s.delete(nodeId) : s.add(nodeId)
  expandedCards.value = s
}

function cardAttrs(node) {
  return node.typed_attrs?.length ? node.typed_attrs : node.attributes ?? []
}

function allCardMethods(node) {
  return node.typed_methods?.length ? node.typed_methods : node.methods ?? []
}

function displayMethods(node) {
  const all = allCardMethods(node)
  return expandedCards.value.has(node.id) ? all : all.slice(0, 8)
}

// typed_methods entries may be {sig, doc} objects or plain strings (old JSON)
function methodSig(m) { return typeof m === 'object' && m !== null ? (m.sig || '') : (m || '') }
function methodDoc(m) { return typeof m === 'object' && m !== null ? (m.doc || '') : '' }

// Flatten a DI tree into [{param, cls, indent}] for simple v-for rendering
function flattenDiTree(deps, indent = 0) {
  const rows = []
  for (const dep of deps ?? []) {
    rows.push({ param: dep.param, cls: dep.class, indent })
    if (dep.deps?.length) rows.push(...flattenDiTree(dep.deps, indent + 1))
  }
  return rows
}

function nodeEdgesOut(nodeId) {
  return umlData.value?.edges.filter(e => e.source === nodeId) ?? []
}
function nodeEdgesIn(nodeId) {
  return umlData.value?.edges.filter(e => e.target === nodeId) ?? []
}
function nodeNameById(id) {
  return umlData.value?.nodes.find(n => n.id === id)?.class_name ?? id.split('.').pop()
}

// ─── Mode switching ───────────────────────────────────────────────────────────

function switchMode(mode) {
  topMode.value = mode
  if (mode === 'ca')     { caView.value = 'overview'; selCircle.value = null; selSubgroup.value = null }
  if (mode === 'module') { moduleView.value = 'grid'; moduleCtx.value = null }
}

function selectModule(ctx) {
  moduleCtx.value = ctx
  moduleView.value = 'detail'
  expandedDddLayers.value = new Set(['domain', 'application', 'infrastructure', 'adapters'])
}

function toggleDddLayer(id) {
  const s = new Set(expandedDddLayers.value)
  s.has(id) ? s.delete(id) : s.add(id)
  expandedDddLayers.value = s
}

function ctxDddSummary(nodes) {
  return DDD_LAYER_GROUPS.map(g => ({
    ...g, count: nodes.filter(n => g.test(n.layer)).length,
  })).filter(g => g.count > 0)
}

function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }

// ─── Lifecycle ────────────────────────────────────────────────────────────────

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (dialogNode.value) { closeDialog(); return }
    if (isFullscreen.value) { isFullscreen.value = false }
  }
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  try {
    const res = await fetch('./uml-data.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    umlData.value = await res.json()
  } catch (e) {
    errorMsg.value = `無法載入 UML 資料：${e.message}。請先執行 make uml-backend。`
  }
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div v-if="!errorMsg" :class="['uml-viewer', { fullscreen: isFullscreen }]">

    <!-- ── Top tab + fullscreen bar ────────────────────────────────────── -->
    <div class="top-bar">
      <div class="tabs">
        <button :class="['tab', { active: topMode === 'ca' }]" @click="switchMode('ca')">
          ◎ Clean Architecture
        </button>
        <button :class="['tab', { active: topMode === 'pipeline' }]" @click="switchMode('pipeline')">
          ⇒ Pipeline Flow
        </button>
        <button :class="['tab', { active: topMode === 'module' }]" @click="switchMode('module')">
          ⊙ Domain Module
        </button>
      </div>
      <div class="top-bar-right">
        <div class="search-wrap">
          <span class="search-icon">⌕</span>
          <input v-model="searchQuery" class="search-bar" placeholder="搜尋 class / docstring…" />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
        </div>
        <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
          {{ isFullscreen ? '⊡' : '⊞' }}
        </button>
      </div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- CLEAN ARCHITECTURE MODE                                           -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="topMode === 'ca'">

      <!-- Overview: concentric rings OR search results -->
      <div v-if="caView === 'overview'" class="overview">
        <!-- Search results flat view -->
        <template v-if="searchLower">
          <div class="search-results-header">
            找到 {{ searchResults.length }} 個符合「{{ searchQuery }}」的 class
            <button class="search-results-clear" @click="searchQuery = ''">清除搜尋</button>
          </div>
          <div v-if="!searchResults.length" class="empty-msg" style="grid-column:1/-1">
            沒有符合的 class。
          </div>
          <div class="card-grid search-results-grid">
            <div
              v-for="node in searchResults" :key="node.id"
              :id="cardId(node.id)"
              :class="['class-card', 'card-clickable', { highlighted: highlightedId === node.id }]"
              :style="{ borderLeftColor: LAYER_COLORS[node.layer] ?? '#888' }"
              @click="openDialog(node)"
            >
              <div class="cc-header">
                <span class="cc-name">{{ node.class_name }}</span>
                <span class="cc-badge" :style="{ background: LAYER_COLORS[node.layer] ?? '#888' }">{{ node.ca_layer }}</span>
              </div>
              <div class="cc-module">{{ node.module || node.id }}</div>
              <div v-if="node.docstring" class="cc-doc">{{ node.docstring }}</div>
              <template v-if="cardAttrs(node).length">
                <div class="cc-section-title">ATTRIBUTES</div>
                <div class="cc-attrs">
                  <div v-for="a in cardAttrs(node)" :key="a" class="cc-attr">
                    <span class="cc-attr-name">{{ a.split(':')[0].trim() }}</span>
                    <span v-if="a.includes(':')" class="cc-attr-type">{{ a.slice(a.indexOf(':') + 1).trim() }}</span>
                  </div>
                </div>
              </template>
              <template v-if="displayMethods(node).length">
                <div class="cc-section-title">METHODS</div>
                <div class="cc-methods">
                  <div v-for="m in displayMethods(node)" :key="methodSig(m)" class="cc-method-row">
                    <span class="cc-method">{{ methodSig(m) }}</span>
                    <span v-if="methodDoc(m)" class="cc-method-doc">{{ methodDoc(m) }}</span>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>

        <!-- Default: concentric rings -->
        <template v-else>
          <div class="overview-hint">點擊同心圓環查看各 Clean Architecture 層</div>
          <svg viewBox="-360 -360 720 720" class="ca-svg">
            <g v-for="c in circles" :key="c.id" class="ca-ring"
              @click="selectCircle(c)"
              @mouseenter="hoveredRing = c.id"
              @mouseleave="hoveredRing = null"
            >
              <path :d="ringPath(c.outerR, c.innerR)"
                :fill="hoveredRing === c.id ? c.color + '58' : c.color + '2a'"
                :stroke="c.color" stroke-width="2.5" fill-rule="evenodd" />
              <text x="0" :y="-((c.outerR + c.innerR) / 2 + 14)"
                text-anchor="middle" :fill="c.color" font-size="20" font-weight="600"
                style="pointer-events:none;font-family:inherit">{{ c.label }}</text>
              <text x="0" :y="-((c.outerR + c.innerR) / 2 - 12)"
                text-anchor="middle" :fill="c.color + 'bb'" font-size="15"
                style="pointer-events:none;font-family:inherit">{{ c.count }} classes</text>
            </g>
          </svg>
        </template>
      </div>

      <!-- Layer: folder card grid -->
      <div v-else-if="caView === 'layer'" class="sub-view">
        <div class="nav-bar">
          <button class="back-btn" @click="caGoBack">← Back</button>
          <nav class="breadcrumb">
            <span class="bc-link" @click="caGoOverview">Overview</span>
            <span class="bc-sep">/</span>
            <span :style="{ color: selCircle.color }">{{ selCircle.label }}</span>
          </nav>
          <span class="nav-count">{{ selCircle.count }} classes</span>
        </div>
        <div class="folder-grid">
          <div v-for="sg in filteredSubgroups" :key="sg.id"
            class="folder-card" @click="selectSubgroup(sg)">
            <div class="folder-icon" :style="{ color: selCircle.color }">▤</div>
            <div class="folder-name">{{ sg.label }}</div>
            <div class="folder-count"
              :style="{ background: selCircle.color + '22', color: selCircle.color }">{{ sg.count }}</div>
          </div>
          <div v-if="!filteredSubgroups.length && searchLower" class="empty-msg">
            沒有符合「{{ searchQuery }}」的子群組。
          </div>
          <div v-else-if="!filteredSubgroups.length" class="empty-msg">
            此層無分類資料，請先執行 <code>make uml-backend</code>
          </div>
        </div>
      </div>

      <!-- Subgroup: class card grid -->
      <div v-else class="sub-view">
        <div class="nav-bar">
          <button class="back-btn" @click="caGoBack">← Back</button>
          <nav class="breadcrumb">
            <span class="bc-link" @click="caGoOverview">Overview</span>
            <span class="bc-sep">/</span>
            <span class="bc-link" @click="caGoBack">{{ selCircle.label }}</span>
            <span class="bc-sep">/</span>
            <span>{{ selSubgroup.label }}</span>
          </nav>
          <span class="nav-count">{{ subgraphNodes.length }} classes</span>
        </div>
        <div v-if="searchQuery && !filteredSubgraphNodes.length" class="empty-msg" style="padding:2rem">
          沒有符合「{{ searchQuery }}」的 class。
        </div>
        <div class="card-grid">
          <!-- ── Class card (CA subgroup) ─────────────────────────────── -->
          <div
            v-for="node in filteredSubgraphNodes" :key="node.id"
            :id="cardId(node.id)"
            :class="['class-card', 'card-clickable', { highlighted: highlightedId === node.id }]"
            :style="{ borderLeftColor: selCircle.color }"
            @click="openDialog(node)"
          >
            <div class="cc-header">
              <span class="cc-name">{{ node.class_name }}</span>
              <span class="cc-badge" :style="{ background: LAYER_COLORS[node.layer] ?? '#888' }">{{ node.layer }}</span>
            </div>
            <div class="cc-module">{{ node.module || node.id }}</div>
            <div v-if="node.docstring" class="cc-doc">{{ node.docstring }}</div>

            <template v-if="cardAttrs(node).length">
              <div class="cc-section-title">ATTRIBUTES</div>
              <div class="cc-attrs">
                <div v-for="a in cardAttrs(node)" :key="a" class="cc-attr">
                  <span class="cc-attr-name">{{ a.split(':')[0].trim() }}</span>
                  <span v-if="a.includes(':')" class="cc-attr-type">{{ a.slice(a.indexOf(':') + 1).trim() }}</span>
                </div>
              </div>
            </template>

            <template v-if="displayMethods(node).length">
              <div class="cc-section-title">METHODS</div>
              <div class="cc-methods">
                <div v-for="m in displayMethods(node)" :key="methodSig(m)" class="cc-method-row">
                  <span class="cc-method">{{ methodSig(m) }}</span>
                  <span v-if="methodDoc(m)" class="cc-method-doc">{{ methodDoc(m) }}</span>
                </div>
                <button v-if="!expandedCards.has(node.id) && allCardMethods(node).length > 8"
                  class="cc-show-more" @click.stop="toggleCardMethods(node.id)">
                  + {{ allCardMethods(node).length - 8 }} more methods
                </button>
              </div>
            </template>

            <template v-if="nodeEdgesOut(node.id).length || nodeEdgesIn(node.id).length">
              <div class="cc-section-title">RELATIONS</div>
              <div class="cc-rels">
                <div v-if="nodeEdgesOut(node.id).length" class="cc-rel-row">
                  <span class="cc-rel-label">→ depends on</span>
                  <div class="cc-chips">
                    <span
                      v-for="e in nodeEdgesOut(node.id)" :key="e.target"
                      :class="['cc-chip', findNodeById(e.target) ? 'chip-nav' : 'chip-ext']"
                      :title="e.target"
                      @click.stop="openDialog(findNodeById(e.target))"
                    >{{ nodeNameById(e.target) }}</span>
                  </div>
                </div>
                <div v-if="nodeEdgesIn(node.id).length" class="cc-rel-row">
                  <span class="cc-rel-label">← used by</span>
                  <div class="cc-chips">
                    <span
                      v-for="e in nodeEdgesIn(node.id)" :key="e.source"
                      :class="['cc-chip', findNodeById(e.source) ? 'chip-nav' : 'chip-ext']"
                      :title="e.source"
                      @click.stop="openDialog(findNodeById(e.source))"
                    >{{ nodeNameById(e.source) }}</span>
                  </div>
                </div>
              </div>
            </template>
          </div>

          <div v-if="!filteredSubgraphNodes.length && !searchQuery" class="empty-msg">此子群組沒有 class。</div>
        </div>
      </div>

    </template>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- PIPELINE FLOW MODE                                                -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-else-if="topMode === 'pipeline'" class="pipeline-view">
      <div v-if="!pipelineStages.length" class="empty-msg" style="padding:3rem">
        Pipeline 資料未找到，請先執行 <code>make uml-backend</code>
      </div>
      <template v-else>
        <div v-for="(stage, idx) in pipelineStages" :key="stage.id" class="pipeline-stage">

          <!-- Stage header -->
          <div class="stage-layout">
            <!-- Main stage column -->
            <div class="stage-main">
              <div class="stage-header" @click="toggleStage(stage.id)">
                <div class="stage-num" :style="{ background: stage.color + '30', color: stage.color }">{{ stage.step }}</div>
                <div class="stage-info">
                  <div class="stage-label-row">
                    <span class="stage-name" :style="{ color: stage.color }">{{ stage.icon }} {{ stage.label }}</span>
                    <div class="event-chips">
                      <span v-for="ev in stage.receives" :key="ev" class="ev-chip receives">{{ ev }}</span>
                      <span v-for="ev in stage.emits" :key="ev" class="ev-chip emits">→ {{ ev }}</span>
                    </div>
                  </div>
                  <div class="stage-desc">{{ stage.desc }}</div>
                </div>
                <span class="stage-chevron">{{ expandedStages.has(stage.id) ? '▼' : '▶' }}</span>
              </div>

              <!-- Stage expanded: class cards + DI tree -->
              <div v-if="expandedStages.has(stage.id)" class="stage-expanded">
                <div class="stage-cards">
                  <div
                    v-for="node in getStageNodes(stage.classes)" :key="node.id"
                    :id="cardId(node.id)"
                    :class="['class-card', 'card-clickable', { highlighted: highlightedId === node.id }]"
                    :style="{ borderLeftColor: stage.color }"
                    @click="openDialog(node)"
                  >
                    <div class="cc-header">
                      <span class="cc-name">{{ node.class_name }}</span>
                      <span class="cc-badge" :style="{ background: LAYER_COLORS[node.layer] ?? '#888' }">{{ node.layer }}</span>
                    </div>
                    <div class="cc-module">{{ node.module || node.id }}</div>
                    <div v-if="node.docstring" class="cc-doc">{{ node.docstring }}</div>

                    <template v-if="cardAttrs(node).length">
                      <div class="cc-section-title">ATTRIBUTES</div>
                      <div class="cc-attrs">
                        <div v-for="a in cardAttrs(node)" :key="a" class="cc-attr">
                          <span class="cc-attr-name">{{ a.split(':')[0].trim() }}</span>
                          <span v-if="a.includes(':')" class="cc-attr-type">{{ a.slice(a.indexOf(':') + 1).trim() }}</span>
                        </div>
                      </div>
                    </template>

                    <template v-if="displayMethods(node).length">
                      <div class="cc-section-title">METHODS</div>
                      <div class="cc-methods">
                        <div v-for="m in displayMethods(node)" :key="methodSig(m)" class="cc-method-row">
                          <span class="cc-method">{{ methodSig(m) }}</span>
                          <span v-if="methodDoc(m)" class="cc-method-doc">{{ methodDoc(m) }}</span>
                        </div>
                        <button v-if="!expandedCards.has(node.id) && allCardMethods(node).length > 8"
                          class="cc-show-more" @click.stop="toggleCardMethods(node.id)">
                          + {{ allCardMethods(node).length - 8 }} more methods
                        </button>
                      </div>
                    </template>
                  </div>

                  <div v-if="!getStageNodes(stage.classes).length" class="empty-msg">
                    此 stage 的 class 不在 JSON 中，請先執行 <code>make uml-backend</code>
                  </div>
                </div>

                <!-- DI tree -->
                <div v-if="flattenDiTree(stage.di).length" class="di-panel">
                  <div class="di-title">📦 依賴注入 (DI)</div>
                  <div
                    v-for="(row, i) in flattenDiTree(stage.di)" :key="i"
                    class="di-row"
                    :style="{ paddingLeft: (row.indent * 18 + 8) + 'px' }"
                  >
                    <span class="di-connector">{{ row.indent === 0 ? '●' : '└' }}</span>
                    <span v-if="row.param" class="di-param">{{ row.param }}:</span>
                    <span
                      class="di-chip"
                      :class="{ 'di-chip-link': !!umlData?.nodes.find(n => n.class_name === row.cls) }"
                      :title="row.cls"
                      @click.stop="openDialog(umlData?.nodes.find(n => n.class_name === row.cls) ?? null)"
                    >{{ row.cls }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- Branch columns (error paths) -->
            <div v-if="stage.branches?.length" class="stage-branches">
              <div v-for="branch in stage.branches" :key="branch.label" class="branch-col">
                <div class="branch-header" :style="{ borderColor: branch.color, color: branch.color }">
                  <span class="branch-arrow">⤷</span> {{ branch.label }}
                  <div class="event-chips" style="margin-top:4px">
                    <span v-for="ev in branch.emits" :key="ev" class="ev-chip emits">{{ ev }}</span>
                  </div>
                </div>
                <div class="branch-desc">{{ branch.desc }}</div>
                <div v-if="expandedStages.has(stage.id)" class="branch-cards">
                  <div
                    v-for="node in getStageNodes(branch.classes)" :key="node.id"
                    :class="['class-card', 'card-clickable', { highlighted: highlightedId === node.id }]"
                    :style="{ borderLeftColor: branch.color }"
                    @click="openDialog(node)"
                  >
                    <div class="cc-header">
                      <span class="cc-name">{{ node.class_name }}</span>
                      <span class="cc-badge" :style="{ background: LAYER_COLORS[node.layer] ?? '#888' }">{{ node.layer }}</span>
                    </div>
                    <div class="cc-module">{{ node.module || node.id }}</div>
                    <div v-if="node.docstring" class="cc-doc">{{ node.docstring }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- Arrow to next stage -->
          <div v-if="idx < pipelineStages.length - 1" class="stage-arrow">↓</div>
        </div>
      </template>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- MODULE / USE CASE VIEW                                             -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-else-if="topMode === 'module'" class="module-view">

      <!-- Context folder grid -->
      <div v-if="moduleView === 'grid'" class="module-grid-wrap">
        <div class="overview-hint">
          按業務情境分類，點擊查看各模組在 DDD 架構中的 class 分布
        </div>
        <div class="module-folder-grid">
          <div v-for="ctx in allModuleContexts" :key="ctx.id"
            class="module-folder-card" @click="selectModule(ctx)">
            <div class="module-folder-icon">{{ CONTEXT_ICONS[ctx.id] ?? '📦' }}</div>
            <div class="module-folder-name">{{ CONTEXT_LABELS[ctx.id] ?? ctx.id }}</div>
            <div class="module-folder-count">{{ ctx.nodes.length }} classes</div>
            <div class="module-folder-layers">
              <span v-for="g in ctxDddSummary(ctx.nodes)" :key="g.id"
                class="module-layer-badge"
                :style="{ background: g.color + '28', color: g.color, border: '1px solid ' + g.color + '66' }">
                {{ g.label }} {{ g.count }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- DDD layer detail view -->
      <div v-else class="module-detail-wrap">
        <div class="nav-bar">
          <button class="back-btn" @click="moduleView = 'grid'; moduleCtx = null">← Back</button>
          <nav class="breadcrumb">
            <span class="bc-link" @click="moduleView = 'grid'; moduleCtx = null">業務模組</span>
            <span class="bc-sep">/</span>
            <span>{{ CONTEXT_LABELS[moduleCtx.id] ?? moduleCtx.id }}</span>
          </nav>
          <span class="nav-count">{{ moduleCtx.nodes.length }} classes</span>
        </div>

        <div v-if="searchQuery && !moduleDddGroups.length" class="empty-msg" style="padding:2rem">
          沒有符合「{{ searchQuery }}」的 class。
        </div>

        <div class="module-ddd-sections">
          <div v-for="group in moduleDddGroups" :key="group.id" class="module-ddd-section">
            <!-- DDD layer header (collapsible) -->
            <div class="module-ddd-header" @click="toggleDddLayer(group.id)"
              :style="{ borderLeftColor: group.color }">
              <span class="module-ddd-dot" :style="{ background: group.color }"></span>
              <span class="module-ddd-label" :style="{ color: group.color }">{{ group.label }}</span>
              <span class="module-ddd-count" :style="{ color: group.color }">{{ group.nodes.length }}</span>
              <span class="module-ddd-chevron">{{ expandedDddLayers.has(group.id) ? '▼' : '▶' }}</span>
            </div>
            <!-- Class cards within this DDD layer -->
            <div v-if="expandedDddLayers.has(group.id)" class="card-grid module-ddd-cards">
              <div
                v-for="node in group.nodes" :key="node.id"
                :class="['class-card', 'card-clickable']"
                :style="{ borderLeftColor: group.color }"
                @click="openDialog(node)"
              >
                <div class="cc-header">
                  <span class="cc-name">{{ node.class_name }}</span>
                  <span class="cc-badge" :style="{ background: LAYER_COLORS[node.layer] ?? '#888' }">
                    {{ node.subgroup ?? node.layer }}
                  </span>
                </div>
                <div class="cc-module">{{ node.module || node.id }}</div>
                <div v-if="node.docstring" class="cc-doc">{{ node.docstring }}</div>

                <template v-if="cardAttrs(node).length">
                  <div class="cc-section-title">ATTRIBUTES</div>
                  <div class="cc-attrs">
                    <div v-for="a in cardAttrs(node)" :key="a" class="cc-attr">
                      <span class="cc-attr-name">{{ a.split(':')[0].trim() }}</span>
                      <span v-if="a.includes(':')" class="cc-attr-type">{{ a.slice(a.indexOf(':') + 1).trim() }}</span>
                    </div>
                  </div>
                </template>

                <template v-if="displayMethods(node).length">
                  <div class="cc-section-title">METHODS</div>
                  <div class="cc-methods">
                    <div v-for="m in displayMethods(node)" :key="methodSig(m)" class="cc-method-row">
                      <span class="cc-method">{{ methodSig(m) }}</span>
                      <span v-if="methodDoc(m)" class="cc-method-doc">{{ methodDoc(m) }}</span>
                    </div>
                    <button v-if="!expandedCards.has(node.id) && allCardMethods(node).length > 8"
                      class="cc-show-more" @click.stop="toggleCardMethods(node.id)">
                      + {{ allCardMethods(node).length - 8 }} more
                    </button>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>

  <!-- ── Class detail dialog ────────────────────────────────────────────── -->
  <Teleport to="body">
    <div v-if="dialogNode" class="dialog-overlay" @click.self="closeDialog">
      <div class="dialog-box" role="dialog" :aria-label="dialogNode.class_name">

        <!-- Navigation bar -->
        <div class="dialog-nav-bar">
          <button class="dialog-nav-btn" :disabled="dialogIndex <= 0" @click="dialogGoBack"
            title="上一個 (←)">‹</button>
          <!-- History breadcrumb dots -->
          <div class="dialog-nav-crumb">
            <span
              v-for="(n, i) in dialogHistory" :key="i"
              :class="['dialog-crumb-dot', { active: i === dialogIndex }]"
              :title="n.class_name"
              @click="dialogGoToIndex(i)"
            ></span>
          </div>
          <span class="dialog-nav-label">
            {{ dialogHistory[dialogIndex]?.class_name }}
          </span>
          <button class="dialog-nav-btn" :disabled="dialogIndex >= dialogHistory.length - 1"
            @click="dialogGoForward" title="下一個 (→)">›</button>
          <button class="dialog-close" @click="closeDialog" title="ESC to close">✕</button>
        </div>

        <!-- Animated card pane -->
        <div class="dialog-anim-wrap">
          <Transition :name="'card-slide-' + dialogSlideDir">
            <div :key="dialogIndex" class="dialog-slide-pane">

              <!-- Header -->
              <div class="dialog-header" :style="{ borderBottomColor: LAYER_COLORS[dialogNode.layer] ?? '#888' }">
                <div>
                  <div class="dialog-class-name">{{ dialogNode.class_name }}</div>
                  <div class="dialog-module">{{ dialogNode.module || dialogNode.id }}</div>
                </div>
                <span class="cc-badge" :style="{ background: LAYER_COLORS[dialogNode.layer] ?? '#888' }">
                  {{ dialogNode.layer }}
                </span>
              </div>

              <!-- Body (scrollable) -->
              <div class="dialog-body">
                <div v-if="dialogNode.docstring" class="dialog-doc">{{ dialogNode.docstring }}</div>

                <a class="dialog-source"
                  :href="'https://github.com/s091648/scrape-and-analyze/tree/master/' + (dialogNode.source_file || dialogNode.full_path)"
                  target="_blank" rel="noopener"
                >{{ dialogNode.source_file || dialogNode.full_path }}</a>

                <template v-if="cardAttrs(dialogNode).length">
                  <div class="cc-section-title">ATTRIBUTES</div>
                  <div class="dialog-attrs">
                    <div v-for="a in cardAttrs(dialogNode)" :key="a" class="cc-attr">
                      <span class="cc-attr-name">{{ a.split(':')[0].trim() }}</span>
                      <span v-if="a.includes(':')" class="cc-attr-type">{{ a.slice(a.indexOf(':') + 1).trim() }}</span>
                    </div>
                  </div>
                </template>

                <template v-if="allCardMethods(dialogNode).length">
                  <div class="cc-section-title">METHODS ({{ allCardMethods(dialogNode).length }})</div>
                  <div class="dialog-methods">
                    <div v-for="m in allCardMethods(dialogNode)" :key="methodSig(m)" class="dialog-method-row">
                      <span class="cc-method">{{ methodSig(m) }}</span>
                      <span v-if="methodDoc(m)" class="dialog-method-doc">{{ methodDoc(m) }}</span>
                    </div>
                  </div>
                </template>

                <template v-if="nodeEdgesOut(dialogNode.id).length || nodeEdgesIn(dialogNode.id).length">
                  <div class="cc-section-title">RELATIONS</div>
                  <div class="cc-rels">
                    <div v-if="nodeEdgesOut(dialogNode.id).length" class="cc-rel-row">
                      <span class="cc-rel-label">→ depends on ({{ nodeEdgesOut(dialogNode.id).length }})</span>
                      <div class="cc-chips">
                        <span
                          v-for="e in nodeEdgesOut(dialogNode.id)" :key="e.target"
                          :class="['cc-chip', findNodeById(e.target) ? 'chip-nav' : 'chip-ext']"
                          :title="e.target"
                          @click.stop="openDialog(findNodeById(e.target))"
                        >{{ nodeNameById(e.target) }}</span>
                      </div>
                    </div>
                    <div v-if="nodeEdgesIn(dialogNode.id).length" class="cc-rel-row">
                      <span class="cc-rel-label">← used by ({{ nodeEdgesIn(dialogNode.id).length }})</span>
                      <div class="cc-chips">
                        <span
                          v-for="e in nodeEdgesIn(dialogNode.id)" :key="e.source"
                          :class="['cc-chip', findNodeById(e.source) ? 'chip-nav' : 'chip-ext']"
                          :title="e.source"
                          @click.stop="openDialog(findNodeById(e.source))"
                        >{{ nodeNameById(e.source) }}</span>
                      </div>
                    </div>
                  </div>
                </template>
              </div>

            </div>
          </Transition>
        </div>

      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* ── Shell ──────────────────────────────────────────────────────────────────── */
.uml-viewer {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px); min-height: 560px;
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  overflow: hidden; background: var(--vp-c-bg);
}
.uml-viewer.fullscreen {
  position: fixed; inset: 0; z-index: 9999;
  height: 100vh; border-radius: 0; border: none;
}

/* ── Top bar ────────────────────────────────────────────────────────────────── */
.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 12px; background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; gap: 8px;
}
.tabs { display: flex; flex-shrink: 0; }
.tab {
  padding: 9px 16px; background: none; border: none;
  border-bottom: 2px solid transparent; font-size: 13px;
  color: var(--vp-c-text-2); cursor: pointer;
  transition: color .15s, border-color .15s;
}
.tab.active { color: var(--vp-c-brand); border-bottom-color: var(--vp-c-brand); font-weight: 600; }
.tab:hover:not(.active) { color: var(--vp-c-text-1); }
.top-bar-right { display: flex; align-items: center; gap: 8px; }
.search-wrap {
  position: relative; display: flex; align-items: center;
}
.search-icon {
  position: absolute; left: 7px; font-size: 15px; color: var(--vp-c-text-3);
  pointer-events: none;
}
.search-bar {
  padding: 4px 28px 4px 26px; border-radius: 16px;
  border: 1px solid var(--vp-c-border); background: var(--vp-c-bg);
  color: var(--vp-c-text-1); width: 200px; font-size: 12px;
  transition: border-color .15s, width .2s;
}
.search-bar:focus { outline: none; border-color: var(--vp-c-brand); width: 260px; }
.search-clear {
  position: absolute; right: 7px; background: none; border: none;
  color: var(--vp-c-text-3); cursor: pointer; font-size: 11px; padding: 0;
}
.search-clear:hover { color: var(--vp-c-text-1); }
.fullscreen-btn {
  background: none; border: 1px solid var(--vp-c-border); border-radius: 4px;
  padding: 3px 9px; cursor: pointer; font-size: 16px; color: var(--vp-c-text-2);
  transition: background .12s; flex-shrink: 0;
}
.fullscreen-btn:hover { background: var(--vp-c-bg-mute); }

/* ── CA Overview ────────────────────────────────────────────────────────────── */
.overview { display: flex; flex-direction: column; align-items: center; flex: 1; overflow: hidden; }
.overview:has(.search-results-header) { overflow-y: auto; align-items: stretch; }
.overview-hint { padding: 10px 0 4px; font-size: 13px; color: var(--vp-c-text-2); flex-shrink: 0; }
.ca-svg { flex: 1; width: 100%; max-height: calc(100% - 36px); }
.ca-ring { cursor: pointer; }
.ca-ring path { transition: fill .18s; }
.ca-ring:hover path { filter: brightness(1.12); }
.search-results-header {
  display: flex; align-items: center; gap: 12px; flex-shrink: 0;
  padding: 8px 16px; font-size: 13px; color: var(--vp-c-text-2);
  border-bottom: 1px solid var(--vp-c-border); width: 100%; background: var(--vp-c-bg-soft);
}
.search-results-clear {
  background: none; border: 1px solid var(--vp-c-border); border-radius: 4px;
  padding: 2px 10px; cursor: pointer; font-size: 12px; color: var(--vp-c-text-2);
}
.search-results-clear:hover { background: var(--vp-c-bg-mute); }
.search-results-grid { width: 100%; }

/* ── Shared sub-view wrapper ────────────────────────────────────────────────── */
.sub-view { display: flex; flex-direction: column; flex: 1; overflow: hidden; }

/* ── Nav bar ────────────────────────────────────────────────────────────────── */
.nav-bar {
  display: flex; align-items: center; gap: 10px; padding: 8px 14px;
  background: var(--vp-c-bg-soft); border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0;
}
.back-btn {
  background: var(--vp-c-bg-mute); border: 1px solid var(--vp-c-border);
  color: var(--vp-c-text-1); padding: 3px 12px; border-radius: 5px;
  cursor: pointer; font-size: 13px; flex-shrink: 0; transition: background .12s;
}
.back-btn:hover { background: var(--vp-c-bg); }
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; flex: 1; min-width: 0; }
.bc-link { color: var(--vp-c-brand); cursor: pointer; white-space: nowrap; }
.bc-link:hover { text-decoration: underline; }
.bc-sep { color: var(--vp-c-text-3); }
.nav-count { font-size: 12px; color: var(--vp-c-text-2); flex-shrink: 0; }

/* ── Group mode toggle ──────────────────────────────────────────────────────── */
.group-toggle { display: flex; border: 1px solid var(--vp-c-border); border-radius: 5px; overflow: hidden; flex-shrink: 0; }
.gm-btn {
  background: none; border: none; padding: 3px 10px; font-size: 12px;
  cursor: pointer; color: var(--vp-c-text-2); transition: background .12s;
}
.gm-btn:hover { background: var(--vp-c-bg-mute); }
.gm-btn.active { background: var(--vp-c-brand); color: #fff; font-weight: 600; }

/* ── Folder grid ────────────────────────────────────────────────────────────── */
.folder-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px; padding: 20px; overflow-y: auto; flex: 1; align-content: start;
}
.folder-card {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 20px 12px 16px; border-radius: 10px; border: 1px solid var(--vp-c-border);
  background: var(--vp-c-bg-soft); cursor: pointer;
  transition: background .15s, transform .12s, box-shadow .15s;
}
.folder-card:hover { background: var(--vp-c-bg-mute); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.1); }
.folder-icon { font-size: 38px; line-height: 1; }
.folder-name { font-size: 13px; font-weight: 600; color: var(--vp-c-text-1); text-align: center; word-break: break-word; }
.folder-count { font-size: 12px; font-weight: 700; padding: 2px 12px; border-radius: 10px; }

/* ── Card grid ──────────────────────────────────────────────────────────────── */
.card-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 14px; padding: 16px; overflow-y: auto; flex: 1; align-content: start;
}

/* ── Class card ─────────────────────────────────────────────────────────────── */
.class-card {
  border: 1px solid var(--vp-c-border);
  border-left: 4px solid #888;
  border-radius: 8px;
  background: var(--vp-c-bg-soft);
  overflow: hidden;
  font-size: 12px;
  transition: box-shadow .2s, transform .15s;
}
.class-card:hover { box-shadow: 0 3px 10px rgba(0,0,0,.1); }
.class-card.highlighted {
  box-shadow: 0 0 0 2px var(--vp-c-brand), 0 4px 16px rgba(0,0,0,.15);
  transform: translateY(-1px);
}

.cc-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 12px 4px; gap: 8px;
}
.cc-name { font-size: 14px; font-weight: 700; color: var(--vp-c-text-1); word-break: break-all; }
.cc-badge { font-size: 10px; color: #fff; padding: 2px 7px; border-radius: 8px; flex-shrink: 0; white-space: nowrap; }
.cc-module { padding: 0 12px 6px; font-family: monospace; font-size: 10px; color: var(--vp-c-text-3); word-break: break-all; }
.cc-doc {
  padding: 5px 12px; font-size: 11px; color: var(--vp-c-text-2);
  font-style: italic; line-height: 1.5; border-top: 1px dashed var(--vp-c-border);
}
.cc-section-title {
  padding: 4px 12px 2px; font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em; color: var(--vp-c-text-3);
  border-top: 1px solid var(--vp-c-border); background: var(--vp-c-bg-mute);
}
.cc-attrs { padding: 4px 12px; }
.cc-attr { display: flex; justify-content: space-between; gap: 6px; padding: 1.5px 0; }
.cc-attr-name { font-family: monospace; color: var(--vp-c-text-1); white-space: nowrap; }
.cc-attr-type {
  font-family: monospace; color: var(--vp-c-text-2); font-style: italic;
  text-align: right; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.cc-methods { padding: 4px 12px 8px; }
.cc-method-row { padding: 1.5px 0; }
.cc-method { font-family: monospace; font-size: 11px; color: var(--vp-c-text-2); word-break: break-all; }
.cc-method-doc { display: block; font-size: 10px; color: var(--vp-c-text-3); font-style: italic; padding-left: 10px; line-height: 1.4; margin-bottom: 2px; }
.cc-show-more {
  background: none; border: none; color: var(--vp-c-brand); cursor: pointer;
  font-size: 11px; padding: 4px 0; text-decoration: underline;
}
.cc-rels { padding: 4px 12px 8px; }
.cc-rel-row { margin-bottom: 4px; }
.cc-rel-label { font-size: 10px; color: var(--vp-c-text-3); font-weight: 600; display: block; margin-bottom: 3px; }
.cc-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.cc-chip {
  font-size: 10px; padding: 1px 8px; border-radius: 8px;
  font-family: monospace; white-space: nowrap; cursor: default;
}
.chip-nav { background: rgba(68,187,153,.1); color: var(--vp-c-brand); border: 1px solid rgba(68,187,153,.35); cursor: pointer; }
.chip-nav:hover { background: var(--vp-c-brand); color: #fff; }
.chip-ext { background: var(--vp-c-bg-mute); color: var(--vp-c-text-3); }

/* ── Pipeline view ──────────────────────────────────────────────────────────── */
.pipeline-view { flex: 1; overflow-y: auto; padding: 16px; }
.pipeline-stage { margin-bottom: 4px; }
.stage-header {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px;
  border-radius: 8px; border: 1px solid var(--vp-c-border);
  background: var(--vp-c-bg-soft); cursor: pointer; transition: background .15s;
}
.stage-header:hover { background: var(--vp-c-bg-mute); }
.stage-num {
  flex-shrink: 0; width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700;
}
.stage-info { flex: 1; min-width: 0; }
.stage-label-row {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 4px;
}
.stage-name { font-size: 14px; font-weight: 600; }
.event-chips { display: flex; gap: 5px; flex-wrap: wrap; }
.ev-chip {
  font-size: 10px; padding: 1px 7px; border-radius: 8px;
  font-family: monospace; white-space: nowrap;
}
.ev-chip.receives { background: rgba(68,187,153,.15); color: #44BB99; }
.ev-chip.emits    { background: rgba(119,170,221,.15); color: #77AADD; }
.stage-desc { font-size: 12px; color: var(--vp-c-text-2); line-height: 1.5; }
.stage-chevron { color: var(--vp-c-text-3); font-size: 12px; flex-shrink: 0; padding-top: 4px; }
.stage-layout { display: flex; gap: 12px; align-items: flex-start; }
.stage-main { flex: 1; min-width: 0; }
.stage-branches { display: flex; gap: 12px; flex-shrink: 0; max-width: 340px; flex-direction: column; }
.branch-col {
  border: 1px dashed var(--vp-c-border); border-radius: 8px;
  padding: 10px; background: var(--vp-c-bg);
}
.branch-header {
  font-size: 12px; font-weight: 600; padding-bottom: 6px;
  border-left: 3px solid currentColor; padding-left: 8px; margin-bottom: 6px;
}
.branch-arrow { font-size: 14px; }
.branch-desc { font-size: 11px; color: var(--vp-c-text-2); line-height: 1.4; margin-bottom: 6px; }
.branch-cards { display: flex; flex-direction: column; gap: 8px; }
.stage-expanded { display: flex; flex-direction: column; gap: 0; }
.stage-cards {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px; padding: 12px 0 12px 44px;
}
.stage-arrow { text-align: center; font-size: 20px; color: var(--vp-c-text-3); padding: 4px 0; }

/* ── DI panel ───────────────────────────────────────────────────────────────── */
.di-panel {
  margin: 0 0 8px 44px; padding: 10px 14px;
  border: 1px dashed var(--vp-c-border); border-radius: 6px;
  background: var(--vp-c-bg-soft);
}
.di-title { font-size: 11px; font-weight: 700; color: var(--vp-c-text-2); margin-bottom: 8px; letter-spacing: .04em; }
.di-row { display: flex; align-items: center; gap: 5px; padding: 2px 0; font-family: monospace; flex-wrap: wrap; }
.di-connector { color: var(--vp-c-text-3); font-size: 10px; flex-shrink: 0; width: 12px; }
.di-param { font-size: 10px; color: var(--vp-c-text-3); font-style: italic; }
.di-chip {
  display: inline-block; font-size: 11px; font-family: monospace;
  padding: 1px 8px; border-radius: 10px;
  background: var(--vp-c-bg-mute); color: var(--vp-c-text-2);
  border: 1px solid var(--vp-c-border);
}
.di-chip-link {
  background: rgba(68,187,153,.1); color: var(--vp-c-brand);
  border-color: rgba(68,187,153,.4); cursor: pointer;
}
.di-chip-link:hover { background: var(--vp-c-brand); color: #fff; border-color: var(--vp-c-brand); }

/* ── Module / Use-Case view ─────────────────────────────────────────────────── */
.module-view { display: flex; flex-direction: column; flex: 1; overflow: hidden; min-height: 0; }
.module-grid-wrap { display: flex; flex-direction: column; flex: 1; overflow-y: auto; min-height: 0; }
.module-folder-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px; padding: 20px; align-content: start;
}
.module-folder-card {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 20px 14px 16px; border-radius: 10px; border: 1px solid var(--vp-c-border);
  background: var(--vp-c-bg-soft); cursor: pointer; text-align: center;
  transition: background .15s, transform .12s, box-shadow .15s;
}
.module-folder-card:hover { background: var(--vp-c-bg-mute); transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.1); }
.module-folder-icon { font-size: 36px; line-height: 1; }
.module-folder-name { font-size: 14px; font-weight: 700; color: var(--vp-c-text-1); }
.module-folder-count { font-size: 12px; color: var(--vp-c-text-2); }
.module-folder-layers { display: flex; flex-wrap: wrap; gap: 4px; justify-content: center; margin-top: 4px; }
.module-layer-badge { font-size: 10px; padding: 1px 7px; border-radius: 8px; font-weight: 600; }

.module-detail-wrap { display: flex; flex-direction: column; flex: 1; overflow: hidden; min-height: 0; }
.module-ddd-sections {
  flex: 1; overflow-y: auto; padding: 12px 16px;
  display: flex; flex-direction: column; gap: 8px; min-height: 0;
}
/* Each section must NOT shrink — collapsed headers must stay full height */
.module-ddd-section {
  border-radius: 8px; border: 1px solid var(--vp-c-border);
  overflow: hidden; flex-shrink: 0;
}
.module-ddd-header {
  display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  min-height: 48px;
  background: var(--vp-c-bg-soft); border-left: 4px solid transparent;
  cursor: pointer; user-select: none; transition: background .15s;
}
.module-ddd-header:hover { background: var(--vp-c-bg-mute); }
.module-ddd-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
.module-ddd-label { font-size: 14px; font-weight: 700; flex: 1; }
.module-ddd-count { font-size: 12px; font-weight: 600; background: var(--vp-c-bg-mute); padding: 1px 8px; border-radius: 8px; }
.module-ddd-chevron { font-size: 11px; color: var(--vp-c-text-3); }
/* Card grid inside accordion: plain auto-height grid, no internal scroll */
.module-ddd-cards {
  padding: 12px; background: var(--vp-c-bg);
  overflow-y: visible; flex: none;
}

/* ── Card clickable ─────────────────────────────────────────────────────────── */
.card-clickable { cursor: pointer; }
.card-clickable:hover { box-shadow: 0 4px 14px rgba(0,0,0,.14); transform: translateY(-2px); }

/* ── Card clickable (keep hover above class-card's default hover) ───────────── */

/* ── Shared ─────────────────────────────────────────────────────────────────── */
.empty-msg { padding: 2rem; text-align: center; color: var(--vp-c-text-2); font-size: 13px; grid-column: 1/-1; }
.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
</style>

<!-- Dialog styles must be global (Teleport moves DOM outside scoped component) -->
<style>
.dialog-overlay {
  position: fixed; inset: 0; z-index: 99999;
  background: rgba(0,0,0,.55);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.dialog-box {
  background: var(--vp-c-bg);
  border: 1px solid var(--vp-c-border);
  border-radius: 12px;
  width: min(720px, 100%);
  max-height: 85vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 64px rgba(0,0,0,.35);
  overflow: hidden;
  font-size: 13px;
}

/* ── Dialog navigation bar ─────────────────────────────────────────────── */
.dialog-nav-bar {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 12px; background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0;
}
.dialog-nav-btn {
  background: none; border: 1px solid var(--vp-c-border); border-radius: 6px;
  font-size: 20px; line-height: 1; width: 30px; height: 30px;
  cursor: pointer; color: var(--vp-c-text-1); display: flex; align-items: center; justify-content: center;
  transition: background .12s;
}
.dialog-nav-btn:hover:not(:disabled) { background: var(--vp-c-bg-mute); }
.dialog-nav-btn:disabled { opacity: .3; cursor: default; }
.dialog-nav-crumb { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.dialog-crumb-dot {
  width: 7px; height: 7px; border-radius: 50%;
  background: var(--vp-c-border); cursor: pointer; transition: background .15s, transform .15s;
}
.dialog-crumb-dot.active { background: var(--vp-c-brand); transform: scale(1.4); }
.dialog-crumb-dot:hover:not(.active) { background: var(--vp-c-text-3); }
.dialog-nav-label {
  flex: 1; font-size: 12px; font-weight: 600; color: var(--vp-c-text-2);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; min-width: 0;
}

/* ── Animated pane wrapper ─────────────────────────────────────────────── */
.dialog-anim-wrap {
  position: relative; overflow: hidden;
  flex: 1; display: flex; flex-direction: column; min-height: 0;
}
.dialog-slide-pane {
  display: flex; flex-direction: column;
  width: 100%; min-height: 0; flex: 1;
}

/* Forward (right): old slides left, new slides in from right */
.card-slide-right-enter-active { transition: transform .26s cubic-bezier(.4,0,.2,1), opacity .2s; }
.card-slide-right-leave-active { transition: transform .26s cubic-bezier(.4,0,.2,1), opacity .2s; position: absolute; inset: 0; }
.card-slide-right-enter-from { transform: translateX(48px); opacity: 0; }
.card-slide-right-leave-to   { transform: translateX(-48px); opacity: 0; }

/* Back (left): old slides right, new slides in from left */
.card-slide-left-enter-active { transition: transform .26s cubic-bezier(.4,0,.2,1), opacity .2s; }
.card-slide-left-leave-active { transition: transform .26s cubic-bezier(.4,0,.2,1), opacity .2s; position: absolute; inset: 0; }
.card-slide-left-enter-from { transform: translateX(-48px); opacity: 0; }
.card-slide-left-leave-to   { transform: translateX(48px); opacity: 0; }

.dialog-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 14px 20px; border-bottom: 2px solid var(--vp-c-border);
  flex-shrink: 0; gap: 12px;
}
.dialog-class-name { font-size: 18px; font-weight: 700; color: var(--vp-c-text-1); }
.dialog-module { font-size: 11px; font-family: monospace; color: var(--vp-c-text-3); margin-top: 3px; word-break: break-all; }
.dialog-close {
  background: none; border: none; font-size: 20px; color: var(--vp-c-text-2);
  cursor: pointer; padding: 0 4px; line-height: 1; flex-shrink: 0;
}
.dialog-close:hover { color: var(--vp-c-text-1); }
.dialog-body { overflow-y: auto; padding: 16px 20px; flex: 1; min-height: 0; }
.dialog-doc {
  font-size: 13px; color: var(--vp-c-text-2); font-style: italic;
  line-height: 1.6; padding: 10px 14px; border-radius: 6px;
  background: var(--vp-c-bg-soft); margin-bottom: 12px; white-space: pre-wrap;
}
.dialog-source { font-size: 11px; font-family: monospace; color: var(--vp-c-text-3); margin-bottom: 12px; text-decoration: none; display: block; }
.dialog-source:hover { color: var(--vp-c-brand); text-decoration: underline; }
.dialog-attrs { padding: 4px 0 12px; }
.dialog-methods { padding: 4px 0 12px; display: flex; flex-direction: column; gap: 4px; }
.dialog-method-row { padding: 2px 0; }
.dialog-method-doc { display: block; font-size: 11px; color: var(--vp-c-text-3); font-style: italic; padding-left: 12px; line-height: 1.5; margin-top: 1px; }
/* cc-* classes inside dialog (Teleport puts them outside scoped scope) */
.dialog-box .cc-section-title {
  padding: 4px 12px 2px; font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: .05em; color: var(--vp-c-text-3);
  border-top: 1px solid var(--vp-c-border); background: var(--vp-c-bg-mute);
}
.dialog-box .cc-attr {
  display: flex; justify-content: space-between; gap: 6px;
  padding: 2px 12px; font-family: monospace; font-size: 12px;
}
.dialog-box .cc-attr-name { color: var(--vp-c-text-1); white-space: nowrap; }
.dialog-box .cc-attr-type { color: var(--vp-c-text-2); font-style: italic; text-align: right; overflow: hidden; text-overflow: ellipsis; }
.dialog-box .cc-method { font-family: monospace; font-size: 12px; color: var(--vp-c-text-2); padding: 2px 12px 0; word-break: break-all; }
.dialog-box .dialog-method-doc { padding-left: 24px; }
.dialog-box .cc-rels { padding: 4px 12px 12px; }
.dialog-box .cc-rel-row { margin-bottom: 8px; }
.dialog-box .cc-rel-label { font-size: 11px; color: var(--vp-c-text-3); font-weight: 600; display: block; margin-bottom: 4px; }
.dialog-box .cc-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.dialog-box .cc-chip { font-size: 11px; padding: 2px 9px; border-radius: 8px; font-family: monospace; background: var(--vp-c-bg-mute); color: var(--vp-c-text-3); }
.dialog-box .chip-nav { background: rgba(68,187,153,.1); color: var(--vp-c-brand); border: 1px solid rgba(68,187,153,.35); cursor: pointer; }
.dialog-box .chip-nav:hover { background: var(--vp-c-brand); color: #fff; }
.dialog-box .cc-badge { font-size: 11px; color: #fff; padding: 2px 8px; border-radius: 8px; flex-shrink: 0; white-space: nowrap; }
</style>
