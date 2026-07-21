<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const CATEGORY_COLORS = {
  custom: '#77AADD',
  framework: '#EEDD88',
  builtin: '#BBCC33',
}

const GITHUB_BASE = 'https://github.com/s091648/scrape-and-analyze/tree/master/'

const exceptions = ref([])
const errorMsg = ref('')
const searchQuery = ref('')
const isFullscreen = ref(false)
const selected = ref(null)

const searchLower = computed(() => searchQuery.value.toLowerCase().trim())

const filteredExceptions = computed(() => {
  if (!searchLower.value) return exceptions.value
  const q = searchLower.value
  return exceptions.value.filter(e =>
    e.name.toLowerCase().includes(q) ||
    (e.docstring || '').toLowerCase().includes(q) ||
    e.bases.some(b => b.toLowerCase().includes(q))
  )
})

function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }
function openDialog(exc) { selected.value = exc }
function closeDialog() { selected.value = null }

function githubUrl(file, line) {
  return `${GITHUB_BASE}${file}${line ? '#L' + line : ''}`
}

function onKeydown(e) {
  if (e.key === 'Escape') {
    if (selected.value) { closeDialog(); return }
    if (isFullscreen.value) isFullscreen.value = false
  }
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  try {
    const res = await fetch('./exceptions-data.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    exceptions.value = data.exceptions ?? []
  } catch (e) {
    errorMsg.value = `無法載入 exceptions-data.json：${e.message}。請先執行 make uml-exceptions。`
  }
})

onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div v-if="!errorMsg" :class="['exception-viewer', { fullscreen: isFullscreen }]">

    <div class="top-bar">
      <span class="top-bar-label">{{ exceptions.length }} exception types</span>
      <div class="top-bar-right">
        <div class="search-wrap">
          <span class="search-icon">⌕</span>
          <input v-model="searchQuery" class="search-bar" placeholder="搜尋 exception 名稱…" />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
        </div>
        <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
          {{ isFullscreen ? '⊡' : '⊞' }}
        </button>
      </div>
    </div>

    <div class="grid-wrap">
      <div v-if="!filteredExceptions.length" class="empty-msg">
        {{ searchQuery ? `沒有符合「${searchQuery}」的 exception。` : '尚無資料，請先執行 make uml-exceptions。' }}
      </div>
      <div class="card-grid">
        <div
          v-for="exc in filteredExceptions" :key="exc.name"
          class="exc-card card-clickable"
          :style="{ borderLeftColor: CATEGORY_COLORS[exc.category] ?? '#888' }"
          @click="openDialog(exc)"
        >
          <div class="exc-header">
            <span class="exc-name">{{ exc.name }}</span>
            <span class="exc-badge" :style="{ background: CATEGORY_COLORS[exc.category] ?? '#888' }">{{ exc.category }}</span>
          </div>
          <div v-if="exc.bases.length" class="exc-bases">extends {{ exc.bases.join(', ') }}</div>
          <div v-if="exc.docstring" class="exc-doc">{{ exc.docstring }}</div>
          <div class="exc-count">{{ exc.raise_sites.length }} raise site{{ exc.raise_sites.length === 1 ? '' : 's' }}</div>
        </div>
      </div>
    </div>

    <!-- ── Detail dialog ────────────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="selected" class="dialog-overlay" @click.self="closeDialog">
        <div class="dialog-box" role="dialog" :aria-label="selected.name">
          <div class="dialog-header" :style="{ borderBottomColor: CATEGORY_COLORS[selected.category] ?? '#888' }">
            <div>
              <span class="dialog-name">{{ selected.name }}</span>
              <div v-if="selected.bases.length" class="dialog-bases">extends {{ selected.bases.join(', ') }}</div>
            </div>
            <div class="dialog-header-right">
              <span class="exc-badge" :style="{ background: CATEGORY_COLORS[selected.category] ?? '#888' }">{{ selected.category }}</span>
              <button class="dialog-close" @click="closeDialog" title="ESC to close">✕</button>
            </div>
          </div>

          <div class="dialog-body">
            <div v-if="selected.docstring" class="dialog-doc">{{ selected.docstring }}</div>
            <a v-if="selected.defined_at" class="dialog-source"
              :href="githubUrl(selected.defined_at.file, selected.defined_at.line)"
              target="_blank" rel="noopener"
            >defined at {{ selected.defined_at.file }}:{{ selected.defined_at.line }}</a>

            <div class="section-title">RAISE SITES ({{ selected.raise_sites.length }})</div>
            <div class="raise-list">
              <div v-for="(site, i) in selected.raise_sites" :key="i" class="raise-item">
                <div class="raise-item-head">
                  <a class="raise-file" :href="githubUrl(site.file, site.line)" target="_blank" rel="noopener">
                    {{ site.file }}:{{ site.line }}
                  </a>
                  <span v-if="site.status_code" class="status-badge">→ {{ site.status_code }}</span>
                </div>
                <div class="raise-function">{{ site.function }}</div>
                <code class="raise-snippet">{{ site.snippet }}</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>
</template>

<style scoped>
.exception-viewer {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px); min-height: 560px;
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  overflow: hidden; background: var(--vp-c-bg);
}
.exception-viewer.fullscreen {
  position: fixed; inset: 0; z-index: 9999;
  height: 100vh; border-radius: 0; border: none;
}

.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 12px; height: 40px; background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0; gap: 8px;
}
.top-bar-label { font-size: 13px; color: var(--vp-c-text-2); }
.top-bar-right { display: flex; align-items: center; gap: 8px; }
.search-wrap { position: relative; display: flex; align-items: center; }
.search-icon { position: absolute; left: 7px; font-size: 15px; color: var(--vp-c-text-3); pointer-events: none; }
.search-bar {
  padding: 4px 28px 4px 26px; border-radius: 16px;
  border: 1px solid var(--vp-c-border); background: var(--vp-c-bg);
  color: var(--vp-c-text-1); width: 200px; font-size: 12px;
  transition: border-color .15s, width .2s;
}
.search-bar:focus { outline: none; border-color: var(--vp-c-brand); width: 260px; }
.search-clear { position: absolute; right: 7px; background: none; border: none; color: var(--vp-c-text-3); cursor: pointer; font-size: 11px; padding: 0; }
.search-clear:hover { color: var(--vp-c-text-1); }
.fullscreen-btn {
  background: none; border: 1px solid var(--vp-c-border); border-radius: 4px;
  padding: 3px 9px; cursor: pointer; font-size: 16px; color: var(--vp-c-text-2);
  transition: background .12s; flex-shrink: 0;
}
.fullscreen-btn:hover { background: var(--vp-c-bg-mute); }

.grid-wrap { flex: 1; overflow-y: auto; padding: 16px; }
.empty-msg { padding: 2rem; text-align: center; color: var(--vp-c-text-2); }

.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.exc-card {
  border: 1px solid var(--vp-c-border); border-left-width: 4px; border-radius: 8px;
  padding: 12px 14px; background: var(--vp-c-bg-soft); cursor: pointer;
  transition: background .15s, box-shadow .15s;
}
.exc-card:hover { background: var(--vp-c-bg-mute); box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.exc-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px; }
.exc-name { font-size: 14px; font-weight: 700; font-family: monospace; }
.exc-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; color: #1a1a1a; flex-shrink: 0; }
.exc-bases { font-size: 11px; color: var(--vp-c-text-2); font-family: monospace; margin-bottom: 4px; }
.exc-doc { font-size: 12px; color: var(--vp-c-text-2); margin-bottom: 6px; }
.exc-count { font-size: 11px; color: var(--vp-c-text-3); }

/* ── Dialog ───────────────────────────────────────────────────────────── */
.dialog-overlay {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.dialog-box {
  background: var(--vp-c-bg); border-radius: 10px; width: min(720px, 100%);
  max-height: 85vh; display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 12px 40px rgba(0,0,0,.3);
}
.dialog-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 16px 20px; border-bottom: 2px solid; flex-shrink: 0;
}
.dialog-name { font-size: 18px; font-weight: 700; font-family: monospace; }
.dialog-bases { font-size: 12px; color: var(--vp-c-text-2); font-family: monospace; margin-top: 2px; }
.dialog-header-right { display: flex; align-items: center; gap: 10px; }
.dialog-close { background: none; border: none; font-size: 16px; color: var(--vp-c-text-2); cursor: pointer; }
.dialog-close:hover { color: var(--vp-c-text-1); }

.dialog-body { padding: 16px 20px; overflow-y: auto; }
.dialog-doc { font-size: 13px; color: var(--vp-c-text-2); margin-bottom: 8px; }
.dialog-source { display: block; font-size: 12px; color: var(--vp-c-brand); margin-bottom: 12px; text-decoration: none; }
.dialog-source:hover { text-decoration: underline; }

.section-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); letter-spacing: .05em; margin: 12px 0 8px; }
.raise-list { display: flex; flex-direction: column; gap: 8px; }
.raise-item { border: 1px solid var(--vp-c-border); border-radius: 6px; padding: 8px 10px; background: var(--vp-c-bg-soft); }
.raise-item-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.raise-file { font-size: 12px; font-family: monospace; color: var(--vp-c-brand); text-decoration: none; word-break: break-all; }
.raise-file:hover { text-decoration: underline; }
.status-badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: var(--vp-c-bg-mute); color: var(--vp-c-text-2); flex-shrink: 0; }
.raise-function { font-size: 11px; color: var(--vp-c-text-2); margin-top: 2px; }
.raise-snippet { display: block; font-size: 11px; margin-top: 4px; padding: 4px 8px; background: var(--vp-c-bg-mute); border-radius: 4px; font-family: monospace; color: var(--vp-c-text-1); overflow-x: auto; white-space: pre; }

.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
</style>
