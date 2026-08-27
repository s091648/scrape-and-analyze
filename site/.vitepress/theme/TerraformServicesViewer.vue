<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const data = ref(null)
const errorMsg = ref('')
const searchQuery = ref('')
const isFullscreen = ref(false)
const selectedService = ref(null)
const selectedGithubCi = ref(null)

const searchLower = computed(() => searchQuery.value.toLowerCase().trim())

const filteredServices = computed(() => {
  const services = data.value?.services ?? []
  if (!searchLower.value) return services
  const q = searchLower.value
  return services.filter(s =>
    s.key.toLowerCase().includes(q) ||
    (s.service_name || '').toLowerCase().includes(q) ||
    (s.source_repo || '').toLowerCase().includes(q)
  )
})

function envSummary(env) {
  if (!env) return '未宣告'
  const n = env.variables.length
  const parts = [`${n} 個變數`]
  if (env.managed_count) parts.push(`${env.managed_count} 個 Terraform 管理`)
  return parts.join('，')
}

function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }
function openService(s) { selectedService.value = s }
function closeService() { selectedService.value = null }
function openGithubCi(g) { selectedGithubCi.value = g }
function closeGithubCi() { selectedGithubCi.value = null }

function scopeLabel(g) {
  if (g.scope === 'repo') return 'Repo 層級'
  return `Environment：${g.github_environment_name_ref || g.environment}`
}

function onKeydown(e) {
  if (e.key !== 'Escape') return
  if (selectedService.value) { closeService(); return }
  if (selectedGithubCi.value) { closeGithubCi(); return }
  if (isFullscreen.value) isFullscreen.value = false
}

onMounted(async () => {
  document.addEventListener('keydown', onKeydown)
  try {
    const res = await fetch('./terraform-services-data.json')
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
  } catch (e) {
    errorMsg.value = `無法載入 terraform-services-data.json：${e.message}。請先執行 make uml-terraform-docs。`
  }
})

onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div v-if="!errorMsg" :class="['tf-viewer', { fullscreen: isFullscreen }]">

    <div class="top-bar">
      <span class="top-bar-label">{{ data?.services.length ?? 0 }} 個服務</span>
      <div class="top-bar-right">
        <div class="search-wrap">
          <span class="search-icon">⌕</span>
          <input v-model="searchQuery" class="search-bar" placeholder="搜尋服務名稱／repo…" />
          <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">✕</button>
        </div>
        <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
          {{ isFullscreen ? '⊡' : '⊞' }}
        </button>
      </div>
    </div>

    <div class="grid-wrap">
      <div v-if="!filteredServices.length" class="empty-msg">
        {{ searchQuery ? `沒有符合「${searchQuery}」的服務。` : '尚無資料，請先執行 make uml-terraform-docs。' }}
      </div>

      <div class="card-grid">
        <div
          v-for="s in filteredServices" :key="s.key"
          class="svc-card card-clickable"
          @click="openService(s)"
        >
          <div class="svc-header">
            <span class="svc-name">{{ s.service_name || s.key }}</span>
          </div>
          <div v-if="s.source_repo" class="svc-meta">{{ s.source_repo }}{{ s.root_directory ? s.root_directory : '' }}</div>
          <div v-if="s.cron_schedule" class="svc-meta">cron: <code>{{ s.cron_schedule }}</code></div>
          <div class="svc-env-row">
            <span class="env-badge prod">production</span>
            <span class="env-count">{{ envSummary(s.environments.production) }}</span>
          </div>
          <div class="svc-env-row">
            <span class="env-badge staging">staging</span>
            <span class="env-count">{{ envSummary(s.environments.staging) }}</span>
          </div>
        </div>
      </div>

      <div v-if="data?.github_ci.length" class="section-title">GITHUB ACTIONS 密鑰／變數（{{ data.github_ci.length }}）</div>
      <div v-if="data?.github_ci.length" class="card-grid">
        <div
          v-for="g in data.github_ci" :key="g.key"
          class="svc-card card-clickable"
          @click="openGithubCi(g)"
        >
          <div class="svc-header">
            <span class="svc-name">{{ g.key }}</span>
          </div>
          <div class="svc-meta">{{ scopeLabel(g) }}</div>
          <div class="svc-env-row">
            <span class="env-count">{{ g.secrets.length }} 個 secrets、{{ g.variables.length }} 個 variables</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ── Service detail dialog ────────────────────────────────────────── -->
    <Teleport to="body">
      <div v-if="selectedService" class="dialog-overlay" @click.self="closeService">
        <div class="dialog-box" role="dialog" :aria-label="selectedService.key">
          <div class="dialog-header">
            <div>
              <span class="dialog-name">{{ selectedService.service_name || selectedService.key }}</span>
              <div v-if="selectedService.source_repo" class="dialog-sub">
                {{ selectedService.source_repo }}{{ selectedService.root_directory || '' }}
                <span v-if="selectedService.cron_schedule"> · cron: {{ selectedService.cron_schedule }}</span>
              </div>
            </div>
            <button class="dialog-close" @click="closeService" title="ESC to close">✕</button>
          </div>

          <div class="dialog-body">
            <div v-for="envName in ['production', 'staging']" :key="envName">
              <div class="section-title">{{ envName.toUpperCase() }}</div>
              <div v-if="!selectedService.environments[envName]" class="empty-msg small">此服務在此環境沒有宣告任何 railway-variables 模組。</div>
              <table v-else class="var-table">
                <thead>
                  <tr><th>變數名稱</th><th>來源</th><th>Sensitive</th><th>值</th></tr>
                </thead>
                <tbody>
                  <tr v-for="v in selectedService.environments[envName].variables" :key="v.name">
                    <td class="mono">{{ v.name }}</td>
                    <td>
                      <span v-if="v.managed" class="badge managed">Terraform 管理</span>
                      <span v-else class="badge baseline">Baseline（值不受管）</span>
                    </td>
                    <td>{{ v.sensitive ? '是' : '否' }}</td>
                    <td class="mono value-cell">{{ v.value ?? (v.sensitive ? '(由 TF_VAR_* 注入，不顯示)' : '—') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── GitHub CI config detail dialog ───────────────────────────────── -->
    <Teleport to="body">
      <div v-if="selectedGithubCi" class="dialog-overlay" @click.self="closeGithubCi">
        <div class="dialog-box" role="dialog" :aria-label="selectedGithubCi.key">
          <div class="dialog-header">
            <div>
              <span class="dialog-name">{{ selectedGithubCi.key }}</span>
              <div class="dialog-sub">{{ scopeLabel(selectedGithubCi) }}</div>
            </div>
            <button class="dialog-close" @click="closeGithubCi" title="ESC to close">✕</button>
          </div>

          <div class="dialog-body">
            <div class="section-title">SECRETS（{{ selectedGithubCi.secrets.length }}）</div>
            <table class="var-table">
              <thead><tr><th>名稱</th><th>來源</th></tr></thead>
              <tbody>
                <tr v-for="v in selectedGithubCi.secrets" :key="v.name">
                  <td class="mono">{{ v.name }}</td>
                  <td>
                    <span v-if="v.managed" class="badge managed">Terraform 管理</span>
                    <span v-else class="badge baseline">Baseline（值不受管）</span>
                  </td>
                </tr>
              </tbody>
            </table>

            <div class="section-title">VARIABLES（{{ selectedGithubCi.variables.length }}）</div>
            <table class="var-table">
              <thead><tr><th>名稱</th><th>來源</th><th>值</th></tr></thead>
              <tbody>
                <tr v-for="v in selectedGithubCi.variables" :key="v.name">
                  <td class="mono">{{ v.name }}</td>
                  <td>
                    <span v-if="v.managed" class="badge managed">Terraform 管理</span>
                    <span v-else class="badge baseline">Baseline（值不受管）</span>
                  </td>
                  <td class="mono value-cell">{{ v.value ?? '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
  <div v-else class="error-msg">{{ errorMsg }}</div>
</template>

<style scoped>
.tf-viewer {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px); min-height: 560px;
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  overflow: hidden; background: var(--vp-c-bg);
}
.tf-viewer.fullscreen {
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
.empty-msg.small { padding: 0.5rem 0; text-align: left; font-size: 12px; }

.section-title { font-size: 11px; font-weight: 600; text-transform: uppercase; color: var(--vp-c-text-2); letter-spacing: .05em; margin: 20px 0 8px; }
.grid-wrap > .section-title:first-child { margin-top: 0; }

.card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.svc-card {
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  padding: 12px 14px; background: var(--vp-c-bg-soft); cursor: pointer;
  transition: background .15s, box-shadow .15s;
}
.svc-card:hover { background: var(--vp-c-bg-mute); box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.svc-header { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.svc-name { font-size: 14px; font-weight: 700; font-family: monospace; }
.svc-meta { font-size: 11px; color: var(--vp-c-text-2); font-family: monospace; margin-bottom: 2px; word-break: break-all; }
.svc-env-row { display: flex; align-items: center; gap: 6px; margin-top: 6px; font-size: 11px; }
.env-badge { padding: 1px 8px; border-radius: 10px; font-weight: 600; font-size: 10px; color: #1a1a1a; }
.env-badge.prod { background: #77AADD; }
.env-badge.staging { background: #EEDD88; }
.env-count { color: var(--vp-c-text-3); }

/* ── Dialog ───────────────────────────────────────────────────────────── */
.dialog-overlay {
  position: fixed; inset: 0; z-index: 10000;
  background: rgba(0,0,0,.5); display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.dialog-box {
  background: var(--vp-c-bg); border-radius: 10px; width: min(760px, 100%);
  max-height: 85vh; display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 12px 40px rgba(0,0,0,.3);
}
.dialog-header {
  display: flex; align-items: flex-start; justify-content: space-between;
  padding: 16px 20px; border-bottom: 2px solid var(--vp-c-border); flex-shrink: 0;
}
.dialog-name { font-size: 18px; font-weight: 700; font-family: monospace; }
.dialog-sub { font-size: 12px; color: var(--vp-c-text-2); font-family: monospace; margin-top: 2px; }
.dialog-close { background: none; border: none; font-size: 16px; color: var(--vp-c-text-2); cursor: pointer; }
.dialog-close:hover { color: var(--vp-c-text-1); }

.dialog-body { padding: 16px 20px; overflow-y: auto; }

.var-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 8px; }
.var-table th { text-align: left; padding: 4px 8px; color: var(--vp-c-text-2); border-bottom: 1px solid var(--vp-c-border); font-weight: 600; }
.var-table td { padding: 4px 8px; border-bottom: 1px solid var(--vp-c-border); vertical-align: top; }
.var-table tr:last-child td { border-bottom: none; }
.mono { font-family: monospace; }
.value-cell { color: var(--vp-c-text-2); word-break: break-all; }

.badge { font-size: 10px; padding: 1px 7px; border-radius: 8px; font-weight: 600; white-space: nowrap; }
.badge.managed { background: #77AADD; color: #1a1a1a; }
.badge.baseline { background: var(--vp-c-bg-mute); color: var(--vp-c-text-2); }

.error-msg { padding: 2rem; color: #e94560; background: rgba(233,69,96,.08); border-radius: 8px; font-size: 14px; }
</style>
