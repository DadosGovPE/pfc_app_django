(() => {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

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

  document.addEventListener("DOMContentLoaded", () => {
    initCarousels();
    updateCountdowns();
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
    const region = document.querySelector("#leilao-global-status");
    if (!region) return;
    region.textContent = "Não foi possível atualizar o lance. Tente novamente.";
    region.classList.add("is-visible");
  });
})();
