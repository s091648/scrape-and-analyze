import DefaultTheme from 'vitepress/theme'
import { onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vitepress'
import { initImageLightbox } from './image-lightbox.js'

export default {
  extends: DefaultTheme,
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
