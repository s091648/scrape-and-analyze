<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useData } from 'vitepress'

const { theme } = useData()

const isFullscreen = ref(false)
function toggleFullscreen() { isFullscreen.value = !isFullscreen.value }

const backendUrl = computed(() => theme.value.backendUrl || '')
const docsUrl = computed(() => backendUrl.value ? `${backendUrl.value.replace(/\/$/, '')}/docs` : '')

function onKeydown(e) {
  if (e.key === 'Escape' && isFullscreen.value) isFullscreen.value = false
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onUnmounted(() => document.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div :class="['swagger-viewer', { fullscreen: isFullscreen }]">
    <div class="top-bar">
      <span class="top-bar-label">⚙ API Docs (read-only — execution disabled)</span>
      <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '離開全螢幕' : '全螢幕'">
        {{ isFullscreen ? '⊡' : '⊞' }}
      </button>
    </div>

    <div v-if="docsUrl" class="swagger-frame">
      <iframe :src="docsUrl" allowfullscreen title="Backend API Docs" />
    </div>
    <div v-else class="swagger-empty">
      <p>Backend URL 未設定。</p>
      <p>請在 GitHub repo variables 加入 <code>BACKEND_URL</code>，並確認 <code>config.js</code> 已加入 <code>backendUrl</code>。</p>
      <p>本機預覽可用 <code>BACKEND_URL=http://localhost:8000 npm run generate</code> 重新產生設定。</p>
    </div>
  </div>
</template>

<style scoped>
.swagger-viewer {
  display: flex; flex-direction: column;
  height: calc(100vh - 120px); min-height: 560px;
  border: 1px solid var(--vp-c-border); border-radius: 8px;
  overflow: hidden; background: var(--vp-c-bg);
}
.swagger-viewer.fullscreen {
  position: fixed; inset: 0; z-index: 9999;
  height: 100vh; border-radius: 0; border: none;
}

.top-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 12px; height: 40px; background: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-border); flex-shrink: 0;
}
.top-bar-label { font-size: 13px; color: var(--vp-c-text-2); }
.fullscreen-btn {
  background: none; border: 1px solid var(--vp-c-border); border-radius: 4px;
  padding: 3px 9px; cursor: pointer; font-size: 16px; color: var(--vp-c-text-2);
  transition: background .12s; flex-shrink: 0;
}
.fullscreen-btn:hover { background: var(--vp-c-bg-mute); }

.swagger-frame { flex: 1; overflow: hidden; }
.swagger-frame iframe { width: 100%; height: 100%; border: none; display: block; background: #fff; }

.swagger-empty {
  flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; color: var(--vp-c-text-2); font-size: 14px; text-align: center; padding: 2rem;
}
.swagger-empty code { font-size: 12px; background: var(--vp-c-bg-mute); padding: 2px 6px; border-radius: 4px; }
</style>
