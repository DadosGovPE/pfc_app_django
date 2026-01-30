(function () {
  function getSelect() {
    return document.querySelector('select[name="content_type"]');
  }

  function setHelpValue(text) {
    const el = document.getElementById("id_help_primeiro_nivel");
    if (el) el.value = text || "";
  }

  async function fetchHelp(selectEl) {
    if (!selectEl) return;

    const endpoint = selectEl.getAttribute("data-fields-help-url");
    const ctId = selectEl.value;

    if (!endpoint) {
      setHelpValue("Endpoint não configurado (data-fields-help-url).");
      return;
    }
    if (!ctId) {
      setHelpValue("Selecione um model para listar campos do 1º nível.");
      return;
    }

    const url = endpoint + "?ct_id=" + encodeURIComponent(ctId);

    try {
      const resp = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
      if (!resp.ok) {
        setHelpValue("Falha ao carregar campos (HTTP " + resp.status + ").");
        return;
      }
      const data = await resp.json();
      setHelpValue(data.help || "");
    } catch (e) {
      setHelpValue("Não foi possível carregar os campos.");
    }
  }

  function bindOnce() {
    const selectEl = getSelect();
    if (!selectEl) return false;

    if (selectEl.dataset.mensageriaBound === "1") return true;
    selectEl.dataset.mensageriaBound = "1";

    // 1) dispara no load
    fetchHelp(selectEl);

    // 2) listeners (se funcionarem, ótimo)
    selectEl.addEventListener("change", function () {
      fetchHelp(getSelect());
    });

    document.addEventListener(
      "change",
      function (e) {
        if (e.target && e.target.matches('select[name="content_type"]')) {
          fetchHelp(e.target);
        }
      },
      true
    );

    // 3) WATCHER (resolve quando eventos não disparam)
    let last = selectEl.value;
    setInterval(function () {
      const curSelect = getSelect();
      if (!curSelect) return;

      const cur = curSelect.value;
      if (cur !== last) {
        last = cur;
        fetchHelp(curSelect);
      }
    }, 300);

    return true;
  }

  function init() {
    bindOnce();

    // rebind se o DOM mudar
    const obs = new MutationObserver(function () {
      bindOnce();
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
