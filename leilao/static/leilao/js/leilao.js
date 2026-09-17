(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let catalogSyncInProgress = false;
  let statusTimer;

  function initCarousels(root = document) {
    root.querySelectorAll("[data-product-carousel]").forEach((element) => {
      if (!window.bootstrap?.Carousel || element.dataset.carouselReady) return;
      element.dataset.carouselReady = "true";
      window.bootstrap.Carousel.getOrCreateInstance(element, {
        interval: reducedMotion.matches ? false : 3000,
        pause: "hover",
        ride: false,
        touch: true,
      });
    });
  }

  function updateCountdowns() {
    const now = Date.now();
    document.querySelectorAll(".leilao-app [data-countdown]").forEach((element) => {
      const label = element.querySelector("[data-countdown-label]");
      const remaining = new Date(element.dataset.end).getTime() - now;
      if (!label || Number.isNaN(remaining)) return;
      if (remaining <= 0) {
        label.textContent = "Leilão encerrado";
        element.classList.add("is-ended");
        return;
      }
      const seconds = Math.floor(remaining / 1000);
      const days = Math.floor(seconds / 86400);
      const hours = Math.floor((seconds % 86400) / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = seconds % 60;
      label.textContent = days > 0
        ? `Faltam ${days}d ${hours}h ${minutes}min`
        : `Faltam ${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
    });
  }

  function announce(message) {
    const region = document.querySelector("#leilao-global-status");
    if (!region) return;
    region.textContent = message;
    region.classList.add("is-visible");
    window.clearTimeout(statusTimer);
    statusTimer = window.setTimeout(() => region.classList.remove("is-visible"), 2800);
  }

  async function syncCatalog() {
    if (catalogSyncInProgress) return;
    if (document.querySelector(".leilao-app .htmx-request")) {
      window.setTimeout(syncCatalog, 300);
      return;
    }
    const currentGrid = document.querySelector("#product-grid");
    if (!currentGrid) return;
    catalogSyncInProgress = true;
    try {
      const response = await fetch(window.location.href, {
        credentials: "same-origin",
        headers: { "HX-Request": "true" },
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      currentGrid.outerHTML = await response.text();
      initCarousels(document);
      updateCountdowns();
      announce("O catálogo foi atualizado com um novo lance.");
    } catch (_error) {
      announce("Não foi possível atualizar o catálogo. A conexão tentará novamente.");
    } finally {
      catalogSyncInProgress = false;
    }
  }

  function startLiveUpdates() {
    const app = document.querySelector(".leilao-app[data-events-url]");
    const state = document.querySelector("#leilao-live-state");
    if (!app) return;
    const version = document.querySelector("#product-grid")?.dataset.catalogVersion || "";

    if (!("EventSource" in window)) {
      if (state) {
        state.classList.add("is-offline");
        state.querySelector("span").textContent = "Atualização periódica";
      }
      window.setInterval(syncCatalog, 5000);
      return;
    }

    const url = new URL(app.dataset.eventsUrl, window.location.origin);
    url.searchParams.set("version", version);
    const source = new EventSource(url);
    source.addEventListener("open", () => {
      if (!state) return;
      state.classList.remove("is-offline");
      state.querySelector("span").textContent = "Atualizações ao vivo";
    });
    source.addEventListener("catalog-update", syncCatalog);
    source.addEventListener("error", () => {
      if (!state) return;
      state.classList.add("is-offline");
      state.querySelector("span").textContent = "Reconectando atualizações";
    });
    window.addEventListener("pagehide", () => source.close(), { once: true });
  }

  document.addEventListener("DOMContentLoaded", () => {
    initCarousels();
    updateCountdowns();
    startLiveUpdates();
    window.setInterval(updateCountdowns, 1000);
  });

  document.body.addEventListener("htmx:afterSwap", (event) => {
    initCarousels(event.detail.target);
    updateCountdowns();
  });

  document.body.addEventListener("catalogReordered", (event) => {
    const grid = document.querySelector("#product-grid");
    if (!grid || !Array.isArray(event.detail.order)) return;
    event.detail.order.forEach((id) => {
      const card = grid.querySelector(`#product-${id}`);
      if (card) grid.appendChild(card);
    });
  });

  document.body.addEventListener("htmx:responseError", () => {
    announce("Não foi possível atualizar o lance. Tente novamente.");
  });
})();
