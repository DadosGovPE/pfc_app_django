(() => {
"use strict";

const payload = JSON.parse(document.getElementById("dados-painel").textContent);
const DATA = payload.registros;
const TOTAL_LINHAS = payload.total_linhas;
const TOTAL_CURSOS = payload.total_cursos;

const LIM_CONF = 0.6;

const SENTS = [
  { k: "Positivo", v: "--pos" },
  { k: "Misto", v: "--mis" },
  { k: "Negativo", v: "--neg" },
  { k: "Neutro", v: "--neu" },
];
const col = k => `var(${SENTS.find(s => s.k === k).v})`;
const fmt = n => n.toLocaleString("pt-BR");
const pct = (a, b) => b ? (a / b * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1, minimumFractionDigits: 1 }) + "%" : "–";
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const mesLabel = ym => { const [y, m] = ym.split("-"); return `${MESES[+m - 1]}/${y.slice(2)}`; };
const count = arr => { const o = { Positivo: 0, Misto: 0, Negativo: 0, Neutro: 0 }; arr.forEach(d => o[d.sent]++); return o; };
const norm = s => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

DATA.forEach(d => {
  d.ano = d.mes.slice(0, 4);
  d.turma = String(d.turma ?? d.t ?? "");
  d.instrutores = d.instrutores || [];
  d.nt = norm(d.txt + " " + d.curso);
});
const datasAll = DATA.map(d => d.mes).sort();
const TEMAS = Object.entries(DATA.flatMap(d => d.temas).reduce((o, t) => (o[t] = (o[t] || 0) + 1, o), {})).sort((a, b) => b[1] - a[1]).map(x => x[0]);
const CURSOS = [...new Set(DATA.map(d => d.curso))].sort((a, b) => a.localeCompare(b, "pt-BR"));
const INSTRUTORES = new Map(DATA.flatMap(d => d.instrutores.map(i => [i.id, i.nome])));

const state = { ano: "", mes: "", curso: "", turma: "", instrutor: "", tema: "", sent: "", conf: "", q: "", shown: 30 };
const FILTROS = ["ano", "mes", "curso", "turma", "instrutor", "tema", "sent", "conf"];

/* Subconjunto dos dados: aplica todos os filtros, menos os de `skip` (cada bloco ignora o próprio filtro
   para continuar mostrando as alternativas). */
function sub(skip = []) {
  const q = norm(state.q.trim());
  const on = k => !skip.includes(k) && state[k];
  return DATA.filter(d =>
    (!on("ano") || d.ano === state.ano) &&
    (!on("mes") || d.mes === state.mes) &&
    (!on("curso") || d.curso === state.curso) &&
    (!on("turma") || d.turma === state.turma) &&
    (!on("instrutor") || d.instrutores.some(i => i.id === state.instrutor)) &&
    (!on("tema") || d.temas.includes(state.tema)) &&
    (!on("sent") || d.sent === state.sent) &&
    (!on("conf") || (state.conf === "baixa" ? d.conf < LIM_CONF : d.conf >= LIM_CONF)) &&
    (skip.includes("q") || !q || d.nt.includes(q)));
}
const filtrado = () => FILTROS.some(k => state[k]) || state.q.trim() !== "";

/* Tooltip */
const tip = document.getElementById("tip");
function showTip(e, html) {
  tip.innerHTML = html; tip.hidden = false;
  const r = tip.getBoundingClientRect();
  let x = e.clientX + 14, y = e.clientY + 14;
  if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
  tip.style.left = x + "px"; tip.style.top = y + "px";
}
const hideTip = () => { tip.hidden = true; };
const tipRows = (title, c, total) => `<b>${esc(title)}</b>` + SENTS.map(s => c[s.k] ? `<div class="row"><span class="sw" style="background:${col(s.k)}"></span>${s.k}: ${c[s.k]} (${pct(c[s.k], total)})</div>` : "").join("");
const toggle = (k, v) => { state[k] = state[k] === v ? "" : v; state.shown = 30; render(); };

/* Cabeçalho */
document.getElementById("periodo").textContent = DATA.length ? `de ${mesLabel(datasAll[0])} a ${mesLabel(datasAll[datasAll.length - 1])}` : "";
document.getElementById("nlinhas").textContent = fmt(TOTAL_LINHAS);


/* Filtros */
const opt = (v, l, sel) => `<option value="${esc(v)}"${sel ? " selected" : ""}>${esc(l)}</option>`;
function renderFiltros() {
  const valores = k => [...new Set(sub(k === "ano" ? ["ano", "mes"] : [k]).flatMap(d => {
    if (k === "instrutor") return d.instrutores.map(i => i.id);
    if (k === "tema") return d.temas;
    if (k === "conf") return [d.conf < LIM_CONF ? "baixa" : "alta"];
    return [d[k]];
  }))].filter(Boolean);
  const ordenar = itens => itens.sort((a, b) => a.localeCompare(b, "pt-BR", { numeric: true }));
  const confiancas = { baixa: `Baixa (< ${LIM_CONF * 100}%) · revisar`, alta: `Alta (≥ ${LIM_CONF * 100}%)` };
  const label = (k, v) => k === "mes" ? mesLabel(v) : k === "instrutor" ? INSTRUTORES.get(v) : k === "conf" ? confiancas[v] : v;
  const f = (id, todos, itens, k) => {
    // Mantém uma seleção visível mesmo quando a busca não encontra resultados.
    if (state[k] && !itens.some(([v]) => v === state[k])) itens.push([state[k], label(k, state[k])]);
    document.getElementById(id).innerHTML = opt("", todos, !state[k]) + itens.map(([v, l]) => opt(v, l, state[k] === v)).join("");
  };
  FILTROS.forEach(k => {
    const disponiveis = valores(k);
    const itens = k === "sent" ? SENTS.map(s => s.k).filter(v => disponiveis.includes(v)) :
      k === "conf" ? ["baixa", "alta"].filter(v => disponiveis.includes(v)) : ordenar(disponiveis);
    const opcoes = itens.map(v => [v, label(k, v)]);
    if (k === "instrutor") opcoes.sort((a, b) => a[1].localeCompare(b[1], "pt-BR"));
    f("f-" + k, k === "conf" || k === "turma" ? "Todas" : "Todos", opcoes, k);
  });
  const n = sub().length;
  document.getElementById("resumo-filtro").textContent = filtrado() ? `${fmt(n)} de ${fmt(DATA.length)} comentários` : `${fmt(DATA.length)} comentários`;
  document.getElementById("limpar").disabled = !filtrado();
}
FILTROS.forEach(k => document.getElementById("f-" + k).addEventListener("change", e => {
  state[k] = e.target.value;
  if (k === "mes" && state.mes) state.ano = state.mes.slice(0, 4);
  if (k === "ano" && state.mes && !state.mes.startsWith(state.ano)) state.mes = "";
  state.shown = 30; render();
}));
document.getElementById("q").addEventListener("input", e => { state.q = e.target.value; state.shown = 30; render(); });
document.getElementById("limpar").addEventListener("click", () => {
  FILTROS.forEach(k => { state[k] = ""; });
  Object.assign(state, { q: "", shown: 30 });
  document.getElementById("q").value = ""; render();
});

/* Resumo */
function legendHTML(c, total) {
  return SENTS.map(s => `<span><i class="sw" style="background:${col(s.k)}"></i>${s.k}${c ? ` <b>${c[s.k]}</b> <span style="color:var(--muted)">(${pct(c[s.k], total)})</span>` : ""}</span>`).join("");
}
document.getElementById("legend2").innerHTML = legendHTML();
function renderResumo() {
  const V = sub(), N = V.length, C = count(V);
  const cursos = new Set(V.map(d => d.curso)).size;
  const sem = !filtrado();
  document.getElementById("kpis").innerHTML = [
    [fmt(N), "comentários escritos", sem ? `${pct(N, TOTAL_LINHAS)} das ${fmt(TOTAL_LINHAS)} avaliações` : `de ${fmt(DATA.length)} no total`],
    [pct(C.Positivo, N), "só elogios", `${C.Positivo} comentários`],
    [pct(C.Misto + C.Negativo, N), "trazem alguma crítica", `${C.Misto} mistos + ${C.Negativo} negativos`],
    [fmt(cursos), "cursos com comentário", sem ? `de ${TOTAL_CURSOS} cursos avaliados` : `de ${fmt(CURSOS.length)} com comentário`],
  ].map(([v, l, d]) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div><div class="d">${d}</div></div>`).join("");

  const B = sub(["sent"]), c = count(B);
  document.getElementById("legend").innerHTML = legendHTML(c, B.length);
  const stack = document.getElementById("stack");
  stack.innerHTML = SENTS.filter(s => c[s.k]).map(s => `<div role="button" tabindex="0" data-s="${s.k}" class="${state.sent && state.sent !== s.k ? "dim" : ""}" aria-label="${s.k}: ${c[s.k]} comentários" style="flex:${c[s.k]} 1 0;background:${col(s.k)}"></div>`).join("");
  stack.querySelectorAll("div").forEach(el => {
    const k = el.dataset.s;
    el.addEventListener("mousemove", e => showTip(e, `<b>${k}</b><div class="row">${c[k]} comentários · ${pct(c[k], B.length)}</div>`));
    el.addEventListener("mouseleave", hideTip);
    el.addEventListener("click", () => toggle("sent", k));
    el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle("sent", k); } });
  });
}

/* Temas */
function renderThemes() {
  const B = sub(["tema"]);
  const stats = TEMAS.map(t => { const ds = B.filter(d => d.temas.includes(t)); return { t, n: ds.length, c: count(ds) }; })
    .filter(s => s.n || s.t === state.tema).sort((a, b) => b.n - a.n);
  const maxT = Math.max(1, ...stats.map(s => s.n));
  document.getElementById("themes").innerHTML = stats.map(s => `
    <button class="trow${state.tema === s.t ? " on" : ""}" data-t="${esc(s.t)}" type="button" aria-pressed="${state.tema === s.t}">
      <span class="tn">${esc(s.t)}</span>
      <span class="tbar" style="width:${s.n / maxT * 100}%">${SENTS.filter(x => s.c[x.k]).map(x => `<div style="flex:${s.c[x.k]} 1 0;background:${col(x.k)}"></div>`).join("")}</span>
      <span class="tc">${s.n}</span>
    </button>`).join("") || `<div class="empty">Sem comentários com esses filtros.</div>`;
  document.querySelectorAll(".trow").forEach(el => {
    const s = stats.find(x => x.t === el.dataset.t);
    el.addEventListener("mousemove", e => showTip(e, tipRows(s.t, s.c, s.n)));
    el.addEventListener("mouseleave", hideTip);
    el.addEventListener("click", () => { hideTip(); toggle("tema", s.t); });
  });
}

/* Pontos de atenção: calculados do filtro atual */
function renderAlerts() {
  const V = sub();
  const alertas = TEMAS.map(t => {
    const ds = V.filter(d => d.temas.includes(t)); const c = count(ds); const crit = c.Misto + c.Negativo;
    return { t, n: ds.length, c, crit };
  }).filter(a => a.crit >= 3).sort((a, b) => b.crit - a.crit || b.crit / b.n - a.crit / a.n).slice(0, 4).map(a => {
    const p = a.crit / a.n;
    const [cor, nivel] = p >= 0.6 ? ["--neg", "Prioridade alta"] : p >= 0.35 ? ["--mis", "Recorrente"] : ["--neu", "Pontual"];
    return { cor, nivel, tema: a.t, titulo: a.t,
      texto: `${a.crit} de ${a.n} comentários sobre este tema trazem crítica (${pct(a.crit, a.n)}): ${a.c.Misto} mistos e ${a.c.Negativo} negativos.` };
  });
  const baixa = V.filter(d => d.conf < LIM_CONF).length;
  if (baixa >= 3) alertas.push({ cor: "--neu", nivel: "Revisão", conf: "baixa", titulo: "Classificação com pouca certeza",
    texto: `${baixa} comentários (${pct(baixa, V.length)}) foram classificados com confiança abaixo de ${LIM_CONF * 100}%. Vale conferir; rotulá-los e retreinar o modelo melhora os resultados.` });
  document.getElementById("alerts").innerHTML = alertas.map((a, i) => `
    <div class="alert">
      <div class="stripe" style="background:var(${a.cor})"></div>
      <div>
        <div style="display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;justify-content:space-between">
          <h3>${esc(a.titulo)}</h3>
          <span class="pill"><span class="dot" style="background:var(${a.cor})"></span>${a.nivel}</span>
        </div>
        <p>${a.texto} <a href="#comentarios" data-alert="${i}" style="color:var(--accent)">Ver comentários</a></p>
      </div>
    </div>`).join("") || `<div class="empty">Nenhum ponto de atenção no filtro atual.</div>`;
  document.querySelectorAll("[data-alert]").forEach(el => el.addEventListener("click", e => {
    e.preventDefault();
    const a = alertas[+el.dataset.alert];
    if (a.tema) state.tema = a.tema; else state.conf = a.conf;
    state.shown = 30; render(); jump();
  }));
}

/* Gráfico mensal */
function monthRange(a, b) {
  const out = []; let [y, m] = a.split("-").map(Number); const [y2, m2] = b.split("-").map(Number);
  while (y < y2 || (y === y2 && m <= m2)) { out.push(`${y}-${String(m).padStart(2, "0")}`); m++; if (m > 12) { m = 1; y++; } }
  return out;
}
function renderMonthly() {
  const B = sub(["ano", "mes"]);
  const box = document.getElementById("monthly");
  if (!B.length) { box.innerHTML = `<div class="empty">Sem comentários com esses filtros.</div>`; return; }
  const ds = B.map(d => d.mes).sort();
  const months = monthRange(ds[0], ds[ds.length - 1]);
  const byMonth = months.map(ym => { const x = B.filter(d => d.mes === ym); return { ym, n: x.length, c: count(x) }; });
  const ativo = ym => (!state.mes || ym === state.mes) && (!state.ano || ym.startsWith(state.ano));
  const W = 1100, H = 280, L = 36, R = 8, T = 12, Bt = 44;
  const maxV = Math.max(1, ...byMonth.map(d => d.n));
  const step = maxV > 30 ? 10 : maxV > 10 ? 5 : 2;
  const top = Math.ceil(maxV / step) * step;
  const y = v => T + (H - T - Bt) * (1 - v / top);
  const bw = (W - L - R) / months.length;
  const barW = Math.min(26, bw * 0.62);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="Comentários por mês, empilhados por sentimento">`;
  for (let v = 0; v <= top; v += step) {
    s += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line${v ? "-soft" : ""})" stroke-width="1"/>`;
    s += `<text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)">${v}</text>`;
  }
  byMonth.forEach((d, i) => {
    const cx = L + bw * i + bw / 2;
    const op = ativo(d.ym) ? 1 : .35;
    let acc = 0;
    const segs = SENTS.filter(x => d.c[x.k]);
    segs.forEach((x, j) => {
      const v = d.c[x.k];
      const y0 = y(acc), y1 = y(acc + v);
      const h = Math.max(0, y0 - y1 - (j < segs.length - 1 ? 2 : 0));
      const isTop = j === segs.length - 1;
      const r = isTop ? Math.min(4, h / 2) : 0;
      const x0 = cx - barW / 2, yt = y1;
      if (r > 0) s += `<path d="M${x0},${y0} V${yt + r} Q${x0},${yt} ${x0 + r},${yt} H${x0 + barW - r} Q${x0 + barW},${yt} ${x0 + barW},${yt + r} V${y0} Z" fill="${col(x.k)}" opacity="${op}"/>`;
      else s += `<rect x="${x0}" y="${yt}" width="${barW}" height="${h}" fill="${col(x.k)}" opacity="${op}"/>`;
      acc += v;
    });
    const [yy, mm] = d.ym.split("-");
    if (mm === "01" || i === 0) s += `<text x="${cx}" y="${H - Bt + 30}" text-anchor="middle" font-size="11" font-weight="600" fill="var(--ink-2)">${yy}</text>`;
    s += `<text x="${cx}" y="${H - Bt + 15}" text-anchor="middle" font-size="10.5" fill="var(--muted)">${MESES[+mm - 1]}</text>`;
    if (d.n) s += `<text x="${cx}" y="${y(d.n) - 5}" text-anchor="middle" font-size="10.5" fill="var(--ink-2)" class="num">${d.n}</text>`;
    s += `<rect class="hit" role="button" tabindex="0" aria-label="${mesLabel(d.ym)}: ${d.n} comentários; filtrar mês" data-i="${i}" x="${L + bw * i}" y="${T}" width="${bw}" height="${H - T - Bt}" fill="transparent" style="cursor:${d.n ? "pointer" : "default"}"/>`;
  });
  s += `</svg>`;
  box.innerHTML = s;
  box.querySelectorAll(".hit").forEach(el => {
    const d = byMonth[+el.dataset.i];
    const lab = `${MESES[+d.ym.slice(5) - 1]} de ${d.ym.slice(0, 4)}`;
    el.addEventListener("mousemove", e => showTip(e, d.n ? tipRows(`${lab} · ${d.n} comentários`, d.c, d.n) : `<b>${lab}</b><div class="row">Sem comentários</div>`));
    el.addEventListener("mouseleave", hideTip);
    const filtrarMes = () => {
      if (!d.n) return;
      hideTip();
      if (state.mes === d.ym) state.mes = ""; else { state.mes = d.ym; state.ano = d.ym.slice(0, 4); }
      state.shown = 30; render();
    };
    el.addEventListener("click", filtrarMes);
    el.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); filtrarMes(); } });
  });
}

/* Cursos */
let sortKey = "total", sortDir = -1;
function renderCourses() {
  const B = sub(["curso"]);
  const stats = [...new Set(B.map(d => d.curso))].map(nome => {
    const ds = B.filter(d => d.curso === nome); const c = count(ds);
    return { nome, total: ds.length, c, pos: c.Positivo / ds.length, crit: (c.Misto + c.Negativo) / ds.length };
  });
  const min = +document.getElementById("minc").value;
  const rows = stats.filter(c => c.total >= min || c.nome === state.curso).sort((a, b) => {
    const va = a[sortKey], vb = b[sortKey];
    if (sortKey === "nome") return sortDir * va.localeCompare(vb, "pt-BR");
    return sortDir * (va - vb) || b.total - a.total;
  });
  document.querySelectorAll("th button").forEach(b => {
    const on = b.dataset.sort === sortKey;
    b.closest("th").setAttribute("aria-sort", on ? (sortDir > 0 ? "ascending" : "descending") : "none");
    b.textContent = b.textContent.replace(/ [▲▼]$/, "") + (on ? (sortDir > 0 ? " ▲" : " ▼") : "");
  });
  document.getElementById("courses").innerHTML = rows.map(r => `
    <tr data-c="${esc(r.nome)}" class="${state.curso === r.nome ? "on" : ""}" tabindex="0">
      <td class="course">${esc(r.nome)}</td>
      <td class="r">${r.total}</td>
      <td><div class="mini">${SENTS.filter(x => r.c[x.k]).map(x => `<div style="flex:${r.c[x.k]} 1 0;background:${col(x.k)}"></div>`).join("")}</div></td>
      <td class="r">${pct(r.c.Positivo, r.total)}</td>
      <td class="r">${pct(r.c.Misto + r.c.Negativo, r.total)}</td>
    </tr>`).join("") || `<tr><td colspan="5" class="empty">Nenhum curso com esse mínimo de comentários.</td></tr>`;
  document.querySelectorAll("#courses tr[data-c]").forEach(tr => {
    const r = stats.find(x => x.nome === tr.dataset.c);
    tr.querySelector(".mini").addEventListener("mousemove", e => showTip(e, tipRows(r.nome, r.c, r.total)));
    tr.querySelector(".mini").addEventListener("mouseleave", hideTip);
    const go = () => { hideTip(); toggle("curso", r.nome); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", e => { if (e.key === "Enter") go(); });
  });
}
document.querySelectorAll("th button").forEach(b => b.addEventListener("click", () => {
  const k = b.dataset.sort;
  if (sortKey === k) sortDir = -sortDir; else { sortKey = k; sortDir = k === "nome" ? 1 : -1; }
  renderCourses();
}));
document.getElementById("minc").addEventListener("change", renderCourses);

/* Comentários */
function renderComments() {
  const base = sub(["sent"]); const bc = count(base);
  document.getElementById("sentChips").innerHTML =
    `<button class="chip" type="button" data-s="" aria-pressed="${!state.sent}">Todos <span class="n">${base.length}</span></button>` +
    SENTS.map(s => `<button class="chip" type="button" data-s="${s.k}" aria-pressed="${state.sent === s.k}"><i class="sw" style="background:${col(s.k)}"></i>${s.k} <span class="n">${bc[s.k]}</span></button>`).join("");
  document.querySelectorAll("#sentChips .chip").forEach(b => b.addEventListener("click", () => { state.sent = b.dataset.s; state.shown = 30; render(); }));

  const list = sub();
  document.getElementById("count").textContent = `${list.length} de ${DATA.length} comentários`;
  const shown = list.slice(0, state.shown);
  document.getElementById("clist").innerHTML = shown.length ? shown.map(d => `
    <article class="c">
      <div class="stripe" style="background:${col(d.sent)}"></div>
      <div>
        <p>${esc(d.txt)}</p>
        <div class="meta"><span class="sent">${d.sent}</span><span>${esc(d.curso)}</span><span>${mesLabel(d.mes)}</span>${d.instrutores.length ? `<span>Instrutores: ${d.instrutores.map(i => esc(i.nome)).join(" · ")}</span>` : ""}${d.temas.length ? `<span class="tag">${d.temas.map(esc).join(" · ")}</span>` : ""}<span class="mono">participante ${esc(d.p)} · ${esc(d.turma ? `Turma: ${d.turma}` : "Turma não informada")} · confiança ${Math.round(d.conf * 100)}%</span></div>
      </div>
    </article>`).join("") : `<div class="empty">Nenhum comentário com esses filtros. Remova um filtro ou mude a busca.</div>`;
  const more = document.getElementById("more");
  more.hidden = list.length <= state.shown;
  more.textContent = `Mostrar mais (${list.length - state.shown} restantes)`;
}
document.getElementById("more").addEventListener("click", () => { state.shown += 40; renderComments(); });

function jump() { document.getElementById("comentarios").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }); }
function render() { renderFiltros(); renderResumo(); renderThemes(); renderAlerts(); renderMonthly(); renderCourses(); renderComments(); }
render();

})();
