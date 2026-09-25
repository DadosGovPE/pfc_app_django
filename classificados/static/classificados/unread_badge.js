document.addEventListener("DOMContentLoaded", () => {
  const badges = document.querySelectorAll("[data-classificados-unread-badge]");
  const url = badges[0]?.dataset.unreadUrl;
  if (!url) return;

  async function refreshUnreadCount() {
    if (document.hidden) return;
    try {
      const response = await fetch(url, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok) return;
      const { count } = await response.json();
      if (!Number.isInteger(count) || count < 0) return;
      const label = `${count} comentário${count === 1 ? "" : "s"} não lido${count === 1 ? "" : "s"}`;
      badges.forEach((badge) => {
        badge.textContent = count;
        badge.setAttribute("aria-label", label);
        badge.classList.toggle("d-none", count === 0);
      });
    } catch (_) {
      // Keep the last known count until the next successful refresh.
    }
  }

  window.setInterval(refreshUnreadCount, 60000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshUnreadCount();
  });
});
