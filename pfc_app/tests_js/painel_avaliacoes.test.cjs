const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const path = require("node:path");
const { test } = require("node:test");
const { JSDOM } = require("jsdom");

const app = path.resolve(__dirname, "..");
const template = readFileSync(path.join(app, "templates/pfc_app/painel_avaliacoes.html"), "utf8")
  .replace(/{%[\s\S]*?%}|{{[\s\S]*?}}/g, "");
const script = readFileSync(path.join(app, "static/pfc_app/js/painel_avaliacoes.js"), "utf8");
const ana = { id: "1", nome: "Ana" }, bruno = { id: "2", nome: "Bruno" };
const base = { p: "1", t: "1", sent: "Positivo", conf: .9, temas: ["Didática"] };
const registros = [
  { ...base, id_curso: "10", curso: "Excel", turma: "TURMA 1", mes: "2025-10", txt: "Boa prática", instrutores: [ana, bruno] },
  { ...base, id_curso: "11", curso: "Excel", turma: "TURMA 2", mes: "2026-11", txt: "Bom conteúdo", instrutores: [bruno], sent: "Misto", conf: .5 },
  { ...base, id_curso: "12", curso: "Python", turma: "TURMA 2", mes: "2026-11", txt: "Ótima didática", instrutores: [bruno] },
  { ...base, id_curso: "13", curso: "Gestão", turma: "TURMA 3", mes: "2026-12", txt: "Boa organização", instrutores: [], temas: ["Organização"] },
];

function painel(t, dados = registros) {
  const dom = new JSDOM(template, { runScripts: "outside-only" });
  t.after(() => dom.window.close());
  const { document, Event } = dom.window;
  const payload = document.createElement("script");
  payload.id = "dados-painel";
  payload.type = "application/json";
  payload.textContent = JSON.stringify({ registros: dados, total_linhas: dados.length, total_cursos: 3 });
  document.body.append(payload);
  dom.window.eval(script);
  const el = id => document.getElementById(id);
  return {
    el,
    options: k => Array.from(el(`f-${k}`).options, o => o.value).filter(Boolean),
    select(k, value) {
      el(`f-${k}`).value = value;
      assert.equal(el(`f-${k}`).value, value, `Opção disponível: ${k}=${value}`);
      el(`f-${k}`).dispatchEvent(new Event("change"));
    },
    search(value) { el("q").value = value; el("q").dispatchEvent(new Event("input")); },
    comments: () => document.querySelectorAll("#clist article").length,
  };
}

test("curso restringe instrutores e turmas; instrutor também restringe cursos", t => {
  const p = painel(t);
  p.select("curso", "Excel");
  assert.deepEqual(p.options("instrutor"), ["1", "2"]);
  assert.deepEqual(p.options("turma"), ["TURMA 1", "TURMA 2"]);
  p.select("instrutor", "1");
  assert.deepEqual(p.options("curso"), ["Excel"]);
  assert.deepEqual(p.options("turma"), ["TURMA 1"]);
  assert.equal(p.comments(), 1);
  p.select("curso", "");
  assert.deepEqual(p.options("curso"), ["Excel"]);
  p.select("instrutor", "2");
  assert.deepEqual(p.options("curso"), ["Excel", "Python"]);
});

test("turma restringe cursos e instrutores em ambas as direções", t => {
  const p = painel(t);
  p.select("turma", "TURMA 2");
  assert.deepEqual(p.options("curso"), ["Excel", "Python"]);
  assert.deepEqual(p.options("instrutor"), ["2"]);
  p.select("curso", "Python");
  assert.equal(p.comments(), 1);
  assert.deepEqual(p.options("turma"), ["TURMA 2"]);
});

test("ano, mês, sentimento, tema e confiança restringem os demais filtros", t => {
  const p = painel(t);
  p.select("ano", "2025");
  assert.deepEqual(p.options("curso"), ["Excel"]);
  assert.deepEqual(p.options("mes"), ["2025-10"]);
  p.el("limpar").click();
  p.select("sent", "Misto");
  assert.deepEqual(p.options("instrutor"), ["2"]);
  assert.deepEqual(p.options("turma"), ["TURMA 2"]);
  assert.deepEqual(p.options("conf"), ["baixa"]);
  p.el("limpar").click();
  p.select("tema", "Organização");
  assert.deepEqual(p.options("curso"), ["Gestão"]);
  assert.deepEqual(p.options("instrutor"), []);
});

test("trocar o ano limpa um mês incompatível e permite sair do período", t => {
  const p = painel(t);
  p.select("mes", "2025-10");
  assert.equal(p.el("f-ano").value, "2025");
  p.select("ano", "2026");
  assert.equal(p.el("f-mes").value, "");
  assert.deepEqual(p.options("mes"), ["2026-11", "2026-12"]);
});

test("busca sem resultados preserva seleções e limpar restaura todas as opções", t => {
  const p = painel(t);
  p.select("curso", "Excel");
  p.select("turma", "TURMA 1");
  p.select("instrutor", "1");
  p.search("inexistente");
  assert.equal(p.comments(), 0);
  assert.equal(p.el("f-instrutor").value, "1");
  assert.equal(p.el("f-turma").value, "TURMA 1");
  p.el("limpar").click();
  assert.equal(p.el("q").value, "");
  assert.equal(p.el("f-instrutor").value, "");
  assert.equal(p.el("f-turma").value, "");
  assert.equal(p.comments(), 4);
  assert.deepEqual(p.options("curso"), ["Excel", "Gestão", "Python"]);
});

test("múltiplos instrutores não duplicam os comentários nem o resumo", t => {
  const p = painel(t);
  p.select("instrutor", "2");
  assert.equal(p.comments(), 3);
  assert.equal(p.el("count").textContent, "3 de 4 comentários");
  assert.equal(p.el("kpis").querySelector(".v").textContent, "3");
});

test("IDs separam instrutores homônimos e nomes são escapados", t => {
  const nome = '<img src=x onerror="alert(1)">';
  const p = painel(t, registros.slice(0, 2).map((r, i) => ({ ...r, instrutores: [{ id: String(i + 1), nome }] })));
  assert.deepEqual(p.options("instrutor"), ["1", "2"]);
  assert.equal(p.el("clist").querySelector("img"), null);
  p.select("instrutor", "1");
  assert.equal(p.comments(), 1);
});

test("snapshots sem metadados novos e publicação vazia continuam funcionando", t => {
  const p = painel(t, registros.map(({ instrutores, turma, ...r }) => r));
  assert.equal(p.comments(), 4);
  assert.deepEqual(p.options("instrutor"), []);
  assert.deepEqual(p.options("turma"), ["1"]);
  assert.equal(painel(t, []).comments(), 0);
});
