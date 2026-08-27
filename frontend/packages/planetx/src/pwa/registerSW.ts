/**
 * Register PlanetX PWA service worker (M0/M1).
 * Safe no-op on localhost http without SW support / insecure contexts except localhost.
 */
export function registerPlanetXPWA(): void {
  if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;

  const enable =
    import.meta.env.PROD ||
    import.meta.env.VITE_ENABLE_PWA === "true" ||
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1";

  if (!enable) return;

  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch((err) => {
      console.warn("[PlanetX PWA] SW register failed:", err);
    });
  });
}
