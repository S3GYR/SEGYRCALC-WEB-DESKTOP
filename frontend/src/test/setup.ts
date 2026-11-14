import "@testing-library/jest-dom/vitest";

class ResizeObserverStub {
  observe() {}
  disconnect() {}
  unobserve() {}
}

Object.defineProperty(globalThis, "ResizeObserver", {
  writable: true,
  value: ResizeObserverStub,
});

Object.defineProperty(window, "scrollTo", {
  writable: true,
  value: () => undefined,
});
