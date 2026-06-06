let initialized = false

function injectStyles() {
  if (document.getElementById('vp-lightbox-styles')) return
  const style = document.createElement('style')
  style.id = 'vp-lightbox-styles'
  style.textContent = `
    .vp-doc img {
      cursor: zoom-in;
      transition: opacity 0.15s;
    }
    .vp-doc img:hover {
      opacity: 0.9;
    }
    #vp-image-lightbox {
      display: none;
      position: fixed;
      inset: 0;
      z-index: 9999;
      background: rgba(0, 0, 0, 0.85);
      cursor: zoom-out;
      align-items: center;
      justify-content: center;
      animation: vp-lightbox-in 0.15s ease;
    }
    #vp-image-lightbox.active {
      display: flex;
    }
    @keyframes vp-lightbox-in {
      from { opacity: 0; }
      to { opacity: 1; }
    }
    #vp-image-lightbox img {
      max-width: 90vw;
      max-height: 90vh;
      object-fit: contain;
      border-radius: 6px;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.6);
      cursor: default;
    }
    #vp-image-lightbox .vp-lightbox-close {
      position: absolute;
      top: 16px;
      right: 16px;
      width: 36px;
      height: 36px;
      background: rgba(255, 255, 255, 0.15);
      border: none;
      border-radius: 50%;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      color: white;
      line-height: 1;
      transition: background 0.15s;
    }
    #vp-image-lightbox .vp-lightbox-close:hover {
      background: rgba(255, 255, 255, 0.28);
    }
  `
  document.head.appendChild(style)
}

function createOverlay() {
  if (document.getElementById('vp-image-lightbox')) return

  const overlay = document.createElement('div')
  overlay.id = 'vp-image-lightbox'
  overlay.setAttribute('role', 'dialog')
  overlay.setAttribute('aria-modal', 'true')
  overlay.setAttribute('aria-label', 'Image preview')

  const closeBtn = document.createElement('button')
  closeBtn.className = 'vp-lightbox-close'
  closeBtn.setAttribute('aria-label', 'Close preview')
  closeBtn.textContent = '✕'

  const img = document.createElement('img')
  img.alt = ''

  overlay.appendChild(closeBtn)
  overlay.appendChild(img)

  function close() {
    overlay.classList.remove('active')
    document.body.style.overflow = ''
    // Clear src after animation
    setTimeout(() => { img.src = '' }, 200)
  }

  // Clicking the backdrop closes the lightbox
  overlay.addEventListener('click', (e) => {
    if (e.target === overlay) close()
  })

  // Close button
  closeBtn.addEventListener('click', close)

  // Clicking the image itself doesn't bubble to the backdrop
  img.addEventListener('click', (e) => e.stopPropagation())

  // Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && overlay.classList.contains('active')) close()
  })

  document.body.appendChild(overlay)
}

export function initImageLightbox() {
  if (typeof document === 'undefined') return

  injectStyles()
  createOverlay()

  if (initialized) return
  initialized = true

  // Event delegation: click any img inside .vp-doc to open lightbox
  document.addEventListener('click', (e) => {
    const target = e.target
    if (target.tagName !== 'IMG' || !target.closest('.vp-doc')) return

    const overlay = document.getElementById('vp-image-lightbox')
    if (!overlay) return

    const img = overlay.querySelector('img')
    img.src = target.src
    img.alt = target.alt || ''
    overlay.classList.add('active')
    document.body.style.overflow = 'hidden'
    overlay.querySelector('.vp-lightbox-close').focus()
  })
}
