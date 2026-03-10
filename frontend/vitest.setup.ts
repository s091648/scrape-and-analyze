import '@testing-library/jest-dom'

// jsdom does not implement ResizeObserver; provide a no-op stub
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}