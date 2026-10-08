import { ref, computed } from "vue";

export const BREAKPOINTS = Object.freeze({
  COMPACT: 900,
  DESKTOP: 1280,
});

export const DEFAULT_SIZES = Object.freeze({
  SIDEBAR: 280,
  RIGHT_DRAWER: 420,
  BOTTOM_DOCK: 220,
});

export const SIZE_LIMITS = Object.freeze({
  SIDEBAR: Object.freeze([200, 450]),
  RIGHT_DRAWER: Object.freeze([320, 650]),
  BOTTOM_DOCK: Object.freeze([150, 400]),
});

/**
 * Determine breakpoint tier from viewport width.
 * @param {number} width
 * @returns {'desktop' | 'compact' | 'mobile'}
 */
export function getBreakpointTier(width) {
  const w = Number(width) || 0;
  if (w > BREAKPOINTS.DESKTOP) return "desktop";
  if (w >= BREAKPOINTS.COMPACT) return "compact";
  return "mobile";
}

/**
 * Clamp a dimension value within min and max boundaries.
 * @param {number} val
 * @param {[number, number]} limits
 * @returns {number}
 */
export function clampSize(val, [min, max]) {
  return Math.max(min, Math.min(max, Number(val) || min));
}

/**
 * Create reactive responsive layout state container.
 * @returns {object}
 */
export function createResponsiveState() {
  const initialWidth =
    typeof window !== "undefined" && window.innerWidth
      ? window.innerWidth
      : 1440;
  const initialHeight =
    typeof window !== "undefined" && window.innerHeight
      ? window.innerHeight
      : 900;

  const windowWidth = ref(initialWidth);
  const windowHeight = ref(initialHeight);

  const tier = computed(() => getBreakpointTier(windowWidth.value));
  const isDesktop = computed(() => tier.value === "desktop");
  const isCompact = computed(() => tier.value === "compact");
  const isMobile = computed(() => tier.value === "mobile");

  const initialTier = getBreakpointTier(initialWidth);
  const sidebarOpen = ref(initialTier !== "mobile");
  const rightDrawerOpen = ref(initialTier === "desktop");
  const bottomDockOpen = ref(false);

  const activeOverlay = ref(null);

  const sidebarWidth = ref(DEFAULT_SIZES.SIDEBAR);
  const rightDrawerWidth = ref(DEFAULT_SIZES.RIGHT_DRAWER);
  const bottomDockHeight = ref(DEFAULT_SIZES.BOTTOM_DOCK);

  let resizeHandler = null;

  function updateDimensions(width, height) {
    const prevTier = tier.value;
    const w = Number(width) || 0;
    const h = Number(height) || 0;
    windowWidth.value = w;
    windowHeight.value = h;
    const nextTier = getBreakpointTier(w);

    // Auto-collapse right drawer when transitioning from desktop down to compact/mobile
    if (prevTier === "desktop" && nextTier !== "desktop") {
      rightDrawerOpen.value = false;
    }

    // Auto-close temporary overlays when returning to desktop layout
    if (nextTier === "desktop") {
      activeOverlay.value = null;
    }
  }

  function toggleSidebar(force) {
    const nextState = typeof force === "boolean" ? force : !sidebarOpen.value;
    sidebarOpen.value = nextState;
    if (tier.value !== "desktop") {
      activeOverlay.value = nextState ? "sidebar" : null;
    }
  }

  function toggleRightDrawer(force) {
    const nextState = typeof force === "boolean" ? force : !rightDrawerOpen.value;
    rightDrawerOpen.value = nextState;
    if (tier.value !== "desktop") {
      activeOverlay.value = nextState ? "assistant" : null;
    }
  }

  function toggleBottomDock(force) {
    bottomDockOpen.value =
      typeof force === "boolean" ? force : !bottomDockOpen.value;
  }

  function openOverlay(name) {
    activeOverlay.value = name;
  }

  function closeOverlays() {
    activeOverlay.value = null;
    if (tier.value !== "desktop") {
      rightDrawerOpen.value = false;
    }
  }

  function setSidebarWidth(width) {
    sidebarWidth.value = clampSize(width, SIZE_LIMITS.SIDEBAR);
  }

  function setRightDrawerWidth(width) {
    rightDrawerWidth.value = clampSize(width, SIZE_LIMITS.RIGHT_DRAWER);
  }

  function setBottomDockHeight(height) {
    bottomDockHeight.value = clampSize(height, SIZE_LIMITS.BOTTOM_DOCK);
  }

  function bindResizeListener() {
    if (typeof window === "undefined" || !window.addEventListener) return;
    if (resizeHandler) return;

    resizeHandler = () => {
      updateDimensions(window.innerWidth, window.innerHeight);
    };
    window.addEventListener("resize", resizeHandler);
  }

  function unbindResizeListener() {
    if (
      typeof window === "undefined" ||
      !window.removeEventListener ||
      !resizeHandler
    )
      return;
    window.removeEventListener("resize", resizeHandler);
    resizeHandler = null;
  }

  return {
    windowWidth,
    windowHeight,
    tier,
    isDesktop,
    isCompact,
    isMobile,
    sidebarOpen,
    rightDrawerOpen,
    bottomDockOpen,
    activeOverlay,
    sidebarWidth,
    rightDrawerWidth,
    bottomDockHeight,
    updateDimensions,
    toggleSidebar,
    toggleRightDrawer,
    toggleBottomDock,
    openOverlay,
    closeOverlays,
    setSidebarWidth,
    setRightDrawerWidth,
    setBottomDockHeight,
    bindResizeListener,
    unbindResizeListener,
  };
}
