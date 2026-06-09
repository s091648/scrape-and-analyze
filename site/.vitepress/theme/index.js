import DefaultTheme from 'vitepress/theme'
import { onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import { initImageLightbox } from './image-lightbox.js'
import UmlViewer from './UmlViewer.vue'
import DepGraphViewer from './DepGraphViewer.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('UmlViewer', UmlViewer)
    app.component('DepGraphViewer', DepGraphViewer)
  },
  setup() {
    const route = useRoute()

    onMounted(() => {
      initImageLightbox()
    })

    // Re-init on route change so new page images are covered
    watch(
      () => route.path,
      () => nextTick(() => initImageLightbox())
    )
  },
}
