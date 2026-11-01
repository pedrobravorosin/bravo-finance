"use strict";
const $ = (s) => document.querySelector(s);
const brl = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
const brl0 = (v) => v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const pct = (v) => (isFinite(v) ? (v * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) : "0") + "%";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const rotulo = (id) => { const [y, m] = id.split("-"); return `${MESES[+m - 1]}/${y.slice(2)}`; };
const addMes = (id, k) => { let [y, m] = id.split("-").map(Number); m += k; y += Math.floor((m - 1) / 12); m = ((m - 1) % 12 + 12) % 12 + 1; return `${y}-${String(m).padStart(2, "0")}`; };
const soma = (arr) => arr.reduce((a, t) => a + t.valor, 0);
const COMER = ["Restaurantes", "Bares e baladas", "Delivery"];

// ---------- Catálogo de cards ----------
const METRICAS = {
  total:        { nome: "Gasto (segue a visão)" },
  acumAno:      { nome: "Acumulado no ano" },
  acumPeriodo:  { nome: "Acumulado no período" },
  media3:       { nome: "Média dos últimos 3 meses" },
  projAno:      { nome: "Projeção para o ano" },
  media:        { nome: "Média mensal no período" },
  comer:        { nome: "Comer e beber fora" },
  parcelas:     { nome: "Parcelas a vencer" },
  parcelasMes:  { nome: "Parcelas neste mês" },
  vista:        { nome: "Compras à vista no mês" },
  assinaturas:  { nome: "Assinaturas no mês" },
  tarifas:      { nome: "Juros, tarifas e IOF" },
  maior:        { nome: "Maior compra do mês" },
  ticket:       { nome: "Valor médio por compra" },
  qtd:          { nome: "Número de compras" },
  limite:       { nome: "Uso do limite" },
  topEst:       { nome: "Onde mais gastou" },
};
const PAINEIS = {
  total:   { nome: "Gastos ao longo dos meses" },
  catmes:  { nome: "Categorias ao longo dos meses" },
  cat:     { nome: "Para onde foi o dinheiro" },
  parc:    { nome: "Parcelas já comprometidas" },
  top:     { nome: "Maiores estabelecimentos" },
  rec:     { nome: "Assinaturas e gastos recorrentes" },
  lanc:    { nome: "Lançamentos" },
  fat:     { nome: "Faturas salvas" },
};
const PADRAO = () => ({
  kpis: [
    { id: "k1", m: "total" }, { id: "k2", m: "acumAno" }, { id: "k3", m: "media3" },
    { id: "k4", m: "comer" }, { id: "k5", m: "parcelas" }, { id: "k6", m: "assinaturas" },
  ],
  paineis: [
    { id: "total" }, { id: "catmes" }, { id: "cat" }, { id: "parc" },
    { id: "top" }, { id: "rec" }, { id: "lanc", wide: true }, { id: "fat", wide: true },
  ],
  filtros: {},
});

let DB = { faturas: [], categorias: [] };
let PREFS = PADRAO();
let sel = null;
let editando = false;
const charts = {};
const F = { de: "", ate: "", cats: null, banco: "", cartao: "", tipo: "", busca: "", visao: "mes" }; // cats null = todas
const VISOES = { mes: "Mês", acum: "Acumulado no período", ano: "Acumulado no ano", media3: "Média de 3 meses" };

// ---------- API ----------
async function api(path, opts = {}) {
  const r = await fetch(path, { ...opts, headers: { "X-Faturas": "1", ...(opts.headers || {}) } });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.erro || `Erro ${r.status}`);
  return j;
}
let salvarTimer = null;
function salvarPrefs() {
  PREFS.filtros = { ...F, cats: F.cats ? [...F.cats] : null };
  clearTimeout(salvarTimer);
  salvarTimer = setTimeout(() => {
    api("/api/preferencias", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(PREFS) })
      .catch((e) => aviso("Não consegui salvar a personalização: " + e.message, true));
  }, 400);
}

function aviso(msg, erro = false) {
  const a = $("#aviso");
  a.textContent = msg; a.hidden = !msg; a.classList.toggle("erro", erro);
}

async function carregar(manter) {
  DB = await api("/api/faturas");
  DB.faturas.sort((a, b) => a.meta.id.localeCompare(b.meta.id));
  const all = ids();
  if (!all.includes(manter)) manter = all[all.length - 1];
  sel = manter;
  montarControles();
  render();
}

async function carregarPrefs() {
  try {
    const p = await api("/api/preferencias");
    if (p && Array.isArray(p.kpis) && Array.isArray(p.paineis)) {
      PREFS = { ...PADRAO(), ...p };
      for (const id of Object.keys(PAINEIS)) if (!PREFS.paineis.some((x) => x.id === id)) PREFS.paineis.push({ id, hidden: true });
      PREFS.paineis = PREFS.paineis.filter((x) => PAINEIS[x.id]);
    }
    if (p && p.filtros) Object.assign(F, p.filtros, { cats: p.filtros.cats ? new Set(p.filtros.cats) : null });
    if (!VISOES[F.visao]) F.visao = "mes";
  } catch { /* usa o padrão */ }
}

function pedirSenha(nome, errada) {
  return new Promise((ok) => {
    const box = $("#senhaBox"), inp = $("#senhaInput");
    $("#senhaTitulo").textContent = errada ? `Senha errada para ${nome}.` : `${nome} tem senha.`;
    box.hidden = false; inp.value = ""; inp.focus();
    const fim = (v) => { box.hidden = true; box.onsubmit = null; $("#senhaPular").onclick = null; ok(v); };
    box.onsubmit = (e) => { e.preventDefault(); fim(inp.value); };
    $("#senhaPular").onclick = () => fim(null);
  });
}

async function enviarUm(f) {
  let senha = null;
  for (let tentativa = 0; tentativa < 4; tentativa++) {
    const headers = { "Content-Type": "application/pdf" };
    if (senha) headers["X-Senha"] = encodeURIComponent(senha);
    const r = await fetch("/api/faturas", { method: "POST", headers: { "X-Faturas": "1", ...headers }, body: f });
    const j = await r.json().catch(() => ({}));
    if (r.ok) return j;
    if (!j.senha) throw new Error(j.erro || `Erro ${r.status}`);
    senha = await pedirSenha(f.name, tentativa > 0);
    if (senha === null) throw new Error("ignorada (sem senha)");
  }
  throw new Error("senha errada");
}

async function enviar(files) {
  const pdfs = [...files].filter((f) => /\.pdf$/i.test(f.name) || f.type === "application/pdf");
  if (!pdfs.length) return aviso("Envie arquivos PDF.", true);
  const linhas = []; let ultimo = null, falhou = false;
  for (const [i, f] of pdfs.entries()) {
    aviso(`Lendo ${i + 1} de ${pdfs.length}…`);
    try {
      const r = await enviarUm(f);
      const m = r.meta; ultimo = m.id;
      const dif = Math.abs(m.soma_lancamentos - m.total);
      linhas.push(`✓ ${m.banco}, ${rotulo(m.id)}: ${brl(m.total)}, ${m.n_lancamentos} lançamentos${r.substituida ? " (substituiu a versão anterior)" : ""}` +
        (dif > 0.05 ? `\n   Confira: a soma dos lançamentos (${brl(m.soma_lancamentos)}) difere do total da fatura em ${brl(dif)}. Pode ser saldo do mês anterior ou alguma linha que não consegui ler.` : "") +
        (m.avisos?.length ? `\n   Observação: ${m.avisos.join("; ")}.` : ""));
    } catch (e) { falhou = true; linhas.push(`✗ ${f.name}: ${e.message}`); }
  }
  aviso(linhas.join("\n"), falhou);
  await carregar(ultimo || sel);
}

// ---------- Filtros ----------
const ids = () => DB.faturas.map((f) => f.meta.id);
function periodo() {
  const all = ids(); if (!all.length) return [];
  const de = all.includes(F.de) ? F.de : all[0];
  const ate = all.includes(F.ate) ? F.ate : all[all.length - 1];
  return DB.faturas.filter((f) => f.meta.id >= de && f.meta.id <= ate);
}
const filtrosAtivos = () => !!(F.cats || F.banco || F.cartao || F.tipo || F.busca.trim());
function passa(t) {
  if (t.tipo === "pagamento") return false;
  if (F.cats && !F.cats.has(t.categoria)) return false;
  if (F.banco && t.banco !== F.banco) return false;
  if (F.cartao && chaveCartao(t) !== F.cartao) return false;
  if (F.tipo === "vista" && t.parcela) return false;
  if (F.tipo === "parcelado" && !t.parcela) return false;
  const q = F.busca.trim().toUpperCase();
  if (q && !t.estabelecimento.includes(q)) return false;
  return true;
}
const txs = (f) => (f ? f.transacoes.filter(passa) : []);
const valorFatura = (f) => (filtrosAtivos() ? soma(txs(f)) : f.meta.total);
function porCategoria(f) { const m = {}; for (const t of txs(f)) m[t.categoria] = (m[t.categoria] || 0) + t.valor; return m; }

const multiBanco = () => new Set(DB.faturas.flatMap((f) => f.transacoes.map((t) => t.banco))).size > 1;
const chaveCartao = (t) => (t.cartao ? `${t.banco || ""}|${t.cartao}` : "");
const nomeCartao = (t) => (t.cartao ? (multiBanco() && t.banco ? `${t.banco} final ${t.cartao}` : `final ${t.cartao}`) : "");

function montarControles() {
  const all = ids();
  $("#mes").innerHTML = all.slice().reverse().map((id) => `<option value="${id}">${rotulo(id)}</option>`).join("");
  if (sel) $("#mes").value = sel;
  const opt = all.map((id) => `<option value="${id}">${rotulo(id)}</option>`).join("");
  $("#fDe").innerHTML = opt; $("#fAte").innerHTML = opt;
  $("#fDe").value = all.includes(F.de) ? F.de : all[0] || "";
  $("#fAte").value = all.includes(F.ate) ? F.ate : all[all.length - 1] || "";
  const bancos = [...new Set(DB.faturas.flatMap((f) => f.transacoes.map((t) => t.banco)).filter(Boolean))].sort();
  $("#fBancoBox").hidden = bancos.length < 2;
  $("#fBanco").innerHTML = `<option value="">Todos</option>` + bancos.map((b) => `<option value="${esc(b)}">${esc(b)}</option>`).join("");
  $("#fBanco").value = bancos.includes(F.banco) ? F.banco : "";
  const mapa = new Map();
  for (const f of DB.faturas) for (const t of f.transacoes) if (t.cartao) mapa.set(chaveCartao(t), nomeCartao(t));
  const cartoes = [...mapa.entries()].sort((a, b) => a[1].localeCompare(b[1]));
  $("#fCartao").innerHTML = `<option value="">Todos</option>` + cartoes.map(([k, n]) => `<option value="${esc(k)}">${esc(n)}</option>`).join("");
  $("#fCartao").value = mapa.has(F.cartao) ? F.cartao : "";
  marcarSegmentos();
  $("#fBusca").value = F.busca || "";
  $("#fCat").innerHTML = DB.categorias.map((c) => `<label><input type="checkbox" value="${esc(c)}" ${!F.cats || F.cats.has(c) ? "checked" : ""}> ${esc(c)}</label>`).join("");
  resumoCats();
}
function marcarSegmentos() {
  for (const b of document.querySelectorAll("[data-visao]")) b.setAttribute("aria-pressed", String(b.dataset.visao === F.visao));
  for (const b of document.querySelectorAll("[data-tipo]")) b.setAttribute("aria-pressed", String(b.dataset.tipo === (F.tipo || "")));
  const all = ids(), atual = presetAtual(all);
  for (const b of document.querySelectorAll("[data-periodo]")) b.setAttribute("aria-pressed", String(b.dataset.periodo === atual));
}
function presetDatas(p, all) {
  const ult = all[all.length - 1];
  if (!ult) return ["", ""];
  if (p === "tudo") return [all[0], ult];
  if (p === "ano") return [all.find((x) => x.slice(0, 4) === ult.slice(0, 4)), ult];
  const n = +p, de = all.find((x) => x >= addMes(ult, -(n - 1)));
  return [de, ult];
}
function presetAtual(all) {
  const de = all.includes(F.de) ? F.de : all[0], ate = all.includes(F.ate) ? F.ate : all[all.length - 1];
  for (const p of ["3", "6", "12", "ano", "tudo"]) { const [a, b] = presetDatas(p, all); if (a === de && b === ate) return p; }
  return "";
}
function resumoCats() {
  const n = F.cats ? F.cats.size : DB.categorias.length;
  $("#fCatResumo").textContent = !F.cats ? "Todas" : n === 0 ? "Nenhuma" : n === 1 ? [...F.cats][0] : `${n} categorias`;
}
function lerCats() {
  const marcadas = [...document.querySelectorAll("#fCat input:checked")].map((i) => i.value);
  F.cats = marcadas.length === DB.categorias.length ? null : new Set(marcadas);
  resumoCats();
}

// ---------- Visões: mês, acumulado e média ----------
// Quais faturas entram no "escopo" do mês em destaque, conforme a visão escolhida.
function faturasDoEscopo(visao = F.visao) {
  const fs = periodo();
  const ate = fs.filter((x) => x.meta.id <= sel);
  if (visao === "acum") return ate;
  if (visao === "ano") return DB.faturas.filter((x) => x.meta.id <= sel && x.meta.id.slice(0, 4) === sel.slice(0, 4));
  if (visao === "media3") return DB.faturas.filter((x) => x.meta.id <= sel && x.meta.id >= addMes(sel, -2));
  return DB.faturas.filter((x) => x.meta.id === sel);
}
function rotuloEscopo(fs, visao = F.visao) {
  if (!fs.length) return "";
  const a = rotulo(fs[0].meta.id), b = rotulo(fs[fs.length - 1].meta.id);
  if (visao === "mes") return b;
  if (visao === "ano") return `${sel.slice(0, 4)} até ${b}`;
  if (visao === "media3") return `média de ${a === b ? b : a + " a " + b}`;
  return a === b ? b : `${a} a ${b}`;
}
// Transforma uma série mensal conforme a visão (acumulado, acumulado no ano, média móvel de 3 meses).
function serieVisao(meses, valores, visao = F.visao) {
  let acc = 0;
  return valores.map((v, i) => {
    if (visao === "acum") return (acc += v);
    if (visao === "ano") { if (i > 0 && meses[i].slice(0, 4) !== meses[i - 1].slice(0, 4)) acc = 0; return (acc += v); }
    if (visao === "media3") { const j = valores.slice(Math.max(0, i - 2), i + 1); return j.reduce((a, b) => a + b, 0) / j.length; }
    return v;
  });
}

// ---------- Métricas dos cards ----------
function contexto() {
  const fs = periodo();
  const f = DB.faturas.find((x) => x.meta.id === sel);
  const prev = DB.faturas[DB.faturas.indexOf(f) - 1];
  const esc0 = faturasDoEscopo();
  const div = F.visao === "media3" ? esc0.length || 1 : 1;
  const t = esc0.flatMap(txs);
  return { fs, f, prev, t, esc: esc0, div, S: (arr) => soma(arr) / div, compras: t.filter((x) => x.valor > 0 && x.tipo === "compra") };
}
function delta(atual, anterior, nomePrev) {
  if (!anterior) return "";
  const d = (atual - anterior) / anterior;
  return `<span class="${d > 0 ? "up" : "down"}">${d > 0 ? "▲" : "▼"} ${pct(Math.abs(d))}</span> vs ${nomePrev}`;
}
function calcular(m, c) {
  const nm = rotulo(sel), np = c.prev && F.visao === "mes" ? rotulo(c.prev.meta.id) : "";
  const mesmo = F.visao === "mes";
  const onde = mesmo ? "do mês" : F.visao === "media3" ? "por mês" : "do período";
  const tot = c.S(c.t);
  if (m.startsWith("cat:")) {
    const cat = m.slice(4);
    const v = c.S(c.t.filter((x) => x.categoria === cat));
    const vp = c.prev && mesmo ? soma(txs(c.prev).filter((x) => x.categoria === cat)) : null;
    const dl = delta(v, vp, np);
    return { titulo: cat, valor: brl0(v), det: `${pct(v / tot)} ${onde}${dl ? " · " + dl : ""}` };
  }
  switch (m) {
    case "total": {
      if (!mesmo) {
        const v = c.esc.reduce((a, x) => a + valorFatura(x), 0) / c.div;
        const tit = { acum: "Acumulado", ano: `Acumulado em ${sel.slice(0, 4)}`, media3: "Média mensal (3 meses)" }[F.visao];
        return { titulo: (filtrosAtivos() ? "Filtrado · " : "") + tit, valor: brl0(v), det: rotuloEscopo(c.esc) };
      }
      const v = valorFatura(c.f), vp = c.prev ? valorFatura(c.prev) : null;
      return { titulo: filtrosAtivos() ? `Gasto filtrado de ${nm}` : `Fatura de ${nm}`, valor: brl0(v), det: delta(v, vp, np) || "Sem mês anterior" };
    }
    case "acumAno": {
      const fs = faturasDoEscopo("ano"), v = fs.reduce((a, x) => a + valorFatura(x), 0);
      const fsAnt = DB.faturas.filter((x) => x.meta.id.slice(0, 4) === String(+sel.slice(0, 4) - 1) && x.meta.id.slice(5) <= sel.slice(5));
      const vAnt = fsAnt.length === fs.length ? fsAnt.reduce((a, x) => a + valorFatura(x), 0) : null;
      return { titulo: `Acumulado em ${sel.slice(0, 4)}`, valor: brl0(v), det: delta(v, vAnt, `mesmo período de ${+sel.slice(0, 4) - 1}`) || `${fs.length} ${fs.length === 1 ? "mês" : "meses"}, até ${nm}` };
    }
    case "acumPeriodo": {
      const fs = faturasDoEscopo("acum"), v = fs.reduce((a, x) => a + valorFatura(x), 0);
      return { titulo: "Acumulado no período", valor: brl0(v), det: rotuloEscopo(fs, "acum") };
    }
    case "media3": {
      const fs = faturasDoEscopo("media3"), v = fs.reduce((a, x) => a + valorFatura(x), 0) / (fs.length || 1);
      const ant = DB.faturas.filter((x) => x.meta.id <= addMes(sel, -3) && x.meta.id >= addMes(sel, -5));
      const vAnt = ant.length === 3 ? ant.reduce((a, x) => a + valorFatura(x), 0) / 3 : null;
      return { titulo: "Média dos últimos 3 meses", valor: brl0(v), det: delta(v, vAnt, "3 meses antes") || rotuloEscopo(fs, "acum") };
    }
    case "projAno": {
      const fs = faturasDoEscopo("ano"), v = fs.reduce((a, x) => a + valorFatura(x), 0);
      const m3 = faturasDoEscopo("media3"), med = m3.reduce((a, x) => a + valorFatura(x), 0) / (m3.length || 1);
      const faltam = 12 - +sel.slice(5);
      return { titulo: `Projeção para ${sel.slice(0, 4)}`, valor: brl0(v + med * faltam), det: faltam ? `acumulado + ${faltam} ${faltam === 1 ? "mês" : "meses"} na média recente` : "ano completo" };
    }
    case "media": {
      const v = c.fs.reduce((a, x) => a + valorFatura(x), 0) / (c.fs.length || 1);
      return { titulo: `Média de ${c.fs.length} ${c.fs.length === 1 ? "mês" : "meses"}`, valor: brl0(v), det: c.fs.length ? `${rotulo(c.fs[0].meta.id)} a ${rotulo(c.fs[c.fs.length - 1].meta.id)}` : "" };
    }
    case "comer": { const v = c.S(c.t.filter((x) => COMER.includes(x.categoria))); return { valor: brl0(v), det: `${pct(v / tot)} dos gastos ${onde}` }; }
    case "parcelas": return { valor: brl0(c.f.meta.parcelas_futuras ?? 0), det: "Saldo já comprometido" };
    case "parcelasMes": { const v = c.S(c.t.filter((x) => x.parcela)); return { valor: brl0(v), det: `${pct(v / tot)} ${onde}` }; }
    case "vista": { const v = c.S(c.t.filter((x) => !x.parcela && x.tipo === "compra")); return { valor: brl0(v), det: `${pct(v / tot)} ${onde}` }; }
    case "assinaturas": return { valor: brl0(c.S(c.t.filter((x) => x.categoria === "Assinaturas"))), det: mesmo ? "Serviços digitais e recorrentes" : `Serviços digitais · ${rotuloEscopo(c.esc)}` };
    case "tarifas": { const v = c.S(c.t.filter((x) => x.categoria === "Tarifas e juros")); return { valor: brl(v), det: v > 0.01 ? "Confira o que foi cobrado" : "Nada cobrado. Ótimo." }; }
    case "maior": {
      const t = c.compras.slice().sort((a, b) => b.valor - a.valor)[0];
      return { valor: t ? brl0(t.valor) : "—", det: t ? esc(t.descricao) + (t.parcela ? ` (${esc(t.parcela)})` : "") : "" };
    }
    case "ticket": return { valor: brl(c.compras.length ? soma(c.compras) / c.compras.length : 0), det: `${c.compras.length} compras` };
    case "qtd": return { valor: String(Math.round(c.compras.length / c.div)), det: mesmo ? `compras em ${nm}` : `compras ${onde}` };
    case "limite": {
      const l = c.f.meta.limite;
      return { valor: l ? pct(c.f.meta.total / l) : "—", det: l ? `${brl0(c.f.meta.total)} de ${brl0(l)}` : "Limite não encontrado na fatura" };
    }
    case "topEst": {
      const a = {}; for (const t of c.compras) a[t.estabelecimento] = (a[t.estabelecimento] || 0) + t.valor;
      const [e, v] = Object.entries(a).sort((x, y) => y[1] - x[1])[0] || [];
      return { valor: e ? brl0(v) : "—", det: e ? esc(e) : "" };
    }
  }
  return { valor: "—", det: "" };
}
function opcoesMetrica(atual) {
  const base = Object.entries(METRICAS).map(([k, v]) => `<option value="${k}"${k === atual ? " selected" : ""}>${esc(v.nome)}</option>`).join("");
  const cats = DB.categorias.map((c) => `<option value="cat:${esc(c)}"${"cat:" + c === atual ? " selected" : ""}>Categoria: ${esc(c)}</option>`).join("");
  return `<optgroup label="Indicadores">${base}</optgroup><optgroup label="Categorias">${cats}</optgroup>`;
}
const nomeMetrica = (m) => (m.startsWith("cat:") ? m.slice(4) : METRICAS[m]?.nome || m);

function renderKpis(c) {
  const lista = PREFS.kpis;
  $("#kpis").innerHTML = lista.map((k, i) => {
    const r = calcular(k.m, c);
    const auto = F.visao === "mes" ? nomeMetrica(k.m) : nomeMetrica(k.m).replace(/ (no|neste) mês$/, "");
    const titulo = k.titulo || r.titulo || auto;
    return `<div class="kpi" data-kpi="${esc(k.id)}">
      <div class="l">${editando ? `<input class="titulo-edit" data-kpi-titulo="${esc(k.id)}" value="${esc(titulo)}" aria-label="Nome do card">` : esc(titulo)}</div>
      <div class="v">${r.valor}</div><div class="d">${r.det || ""}</div>
      <div class="ferramentas">
        <select data-kpi-metrica="${esc(k.id)}" aria-label="O que este card mostra">${opcoesMetrica(k.m)}</select>
        <button class="mini" data-kpi-mover="${esc(k.id)}" data-dir="-1" ${i === 0 ? "disabled" : ""} title="Mover para a esquerda">◀</button>
        <button class="mini" data-kpi-mover="${esc(k.id)}" data-dir="1" ${i === lista.length - 1 ? "disabled" : ""} title="Mover para a direita">▶</button>
        ${k.titulo ? `<button class="mini" data-kpi-renomear="${esc(k.id)}">Nome automático</button>` : ""}
        <button class="mini perigo" data-kpi-remover="${esc(k.id)}">Remover</button>
      </div></div>`;
  }).join("");
}

// ---------- Painéis ----------
function cascaPainel(p, i, visiveis) {
  const ferr = `<div class="ferramentas">
      <button class="mini" data-p-mover="${p.id}" data-dir="-1" ${i === 0 ? "disabled" : ""} title="Mover para antes">◀</button>
      <button class="mini" data-p-mover="${p.id}" data-dir="1" ${i === visiveis.length - 1 ? "disabled" : ""} title="Mover para depois">▶</button>
      <button class="mini" data-p-largura="${p.id}">${p.wide ? "Meia largura" : "Largura total"}</button>
      ${p.titulo ? `<button class="mini" data-p-renomear="${p.id}">Nome original</button>` : ""}
      <button class="mini perigo" data-p-esconder="${p.id}">Esconder</button></div>`;
  const nome = p.titulo || PAINEIS[p.id].nome;
  const h = editando ? `<input class="titulo-edit" data-p-titulo="${p.id}" value="${esc(nome)}" aria-label="Nome do painel">` : `${esc(nome)} <span class="muted" data-sub="${p.id}"></span>`;
  return `<article class="card${p.wide ? " wide" : ""}" data-painel="${p.id}"><div class="card-head"><h2>${h}</h2>${ferr}</div><div class="corpo" id="corpo-${p.id}"></div></article>`;
}
const setSub = (id, txt) => { const el = document.querySelector(`[data-sub="${id}"]`); if (el) el.textContent = txt; };

function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function baseOpts(extra = {}) {
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { display: false, labels: { color: css("--text2"), boxWidth: 10, boxHeight: 10, useBorderRadius: true, borderRadius: 2 } },
      tooltip: { callbacks: { label: (c) => ` ${c.dataset.label ? c.dataset.label + ": " : ""}${brl(c.parsed.y ?? c.parsed.x)}` } },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: css("--text2") }, border: { color: css("--border") } },
      y: { grid: { color: css("--grid") }, border: { display: false }, ticks: { color: css("--muted"), precision: 0, maxTicksLimit: 8, callback: (v) => brl0(v) } },
    },
    ...extra,
  };
}
function chart(id, cfg) { const el = document.getElementById(id); if (el) charts[id] = new Chart(el, cfg); }
const bar = { borderRadius: 4, borderSkipped: "start", maxBarThickness: 44 };
const selCat = (est, c) => `<select data-est="${esc(est)}" aria-label="Categoria">${DB.categorias.map((x) => `<option${x === c ? " selected" : ""}>${esc(x)}</option>`).join("")}</select>`;
const vazioTxt = (t) => `<p class="muted">${t}</p>`;

const RENDER = {
  total(c, el) {
    setSub("total", (F.visao !== "mes" ? `· ${VISOES[F.visao].toLowerCase()}` : "") + (filtrosAtivos() ? " · filtrado" : ""));
    el.innerHTML = `<div class="chart"><canvas id="cTotal" aria-label="Gastos ao longo dos meses"></canvas></div>`;
    const meses = c.fs.map((x) => x.meta.id), mensal = c.fs.map(valorFatura);
    const ds = [{ type: "bar", label: "No mês", data: mensal, ...bar, order: 2,
      backgroundColor: meses.map((id) => (F.visao === "mes" ? (id === sel ? css("--s2") : css("--s1")) : css("--s1") + (id === sel ? "" : "44"))) }];
    if (F.visao !== "mes") ds.push({ type: "line", label: VISOES[F.visao], data: serieVisao(meses, mensal), order: 1,
      borderColor: css("--s2"), backgroundColor: css("--s2"), borderWidth: 2.5, tension: 0.25, cubicInterpolationMode: "monotone",
      pointRadius: meses.map((id) => (id === sel ? 5 : 2.5)),
      // no acumulado do ano, a linha recomeça em janeiro (sem ligar dezembro a janeiro)
      segment: { borderColor: (ctx) => (F.visao === "ano" && meses[ctx.p1DataIndex].slice(5) === "01" ? "transparent" : undefined) } });
    const o = baseOpts(); o.plugins.legend.display = F.visao !== "mes"; o.plugins.legend.position = "bottom";
    chart("cTotal", { data: { labels: meses.map(rotulo), datasets: ds }, options: o });
  },
  catmes(c, el) {
    el.innerHTML = `<div class="chart"><canvas id="cCatMes" aria-label="Categorias por mês"></canvas></div>`;
    const tot = {}; for (const x of c.fs) for (const [k, v] of Object.entries(porCategoria(x))) tot[k] = (tot[k] || 0) + v;
    const top = Object.entries(tot).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).slice(0, 7).map(([k]) => k);
    const series = [...top, "Demais"].map((k, i) => ({
      label: k, ...bar, borderRadius: 0, borderColor: css("--surface"), borderWidth: { top: 2 },
      backgroundColor: css(`--s${i < top.length ? i + 1 : 8}`),
      data: serieVisao(c.fs.map((x) => x.meta.id), c.fs.map((x) => { const m = porCategoria(x); return k === "Demais" ? Object.entries(m).filter(([n]) => !top.includes(n)).reduce((a, [, v]) => a + v, 0) : (m[k] || 0); })),
    })).filter((s) => s.data.some((v) => v > 0));
    setSub("catmes", F.visao !== "mes" ? `· ${VISOES[F.visao].toLowerCase()}` : "");
    const o = baseOpts(); o.scales.x.stacked = o.scales.y.stacked = true; o.plugins.legend.display = true; o.plugins.legend.position = "bottom";
    chart("cCatMes", { type: "bar", data: { labels: c.fs.map((x) => rotulo(x.meta.id)), datasets: series }, options: o });
  },
  cat(c, el) {
    setSub("cat", `· ${rotuloEscopo(c.esc)}`);
    const cat = {}; for (const t of c.t) cat[t.categoria] = (cat[t.categoria] || 0) + t.valor / c.div;
    const tot = Object.values(cat).reduce((a, b) => a + b, 0);
    const cs = Object.entries(cat).filter(([, v]) => v > 0.004).sort((a, b) => b[1] - a[1]);
    if (!cs.length) { el.innerHTML = vazioTxt("Nada com esses filtros."); return; }
    el.innerHTML = `<div class="chart" style="height:${Math.max(200, cs.length * 30 + 40)}px"><canvas id="cCat" aria-label="Gastos por categoria no mês"></canvas></div>`;
    const o = baseOpts({ indexAxis: "y" });
    o.scales = { x: { grid: { color: css("--grid") }, border: { display: false }, ticks: { color: css("--muted"), precision: 0, maxTicksLimit: 8, callback: (v) => brl0(v) } },
      y: { grid: { display: false }, ticks: { color: css("--text2") }, border: { color: css("--border") } } };
    o.plugins.tooltip.callbacks.label = (x) => ` ${brl(x.parsed.x)} (${pct(x.parsed.x / tot)})`;
    chart("cCat", { type: "bar", data: { labels: cs.map(([k]) => k), datasets: [{ data: cs.map(([, v]) => v), ...bar, backgroundColor: css("--s1") }] }, options: o });
  },
  parc(c, el) {
    const proj = {};
    for (const t of c.t) {
      if (!t.parcela || t.tipo !== "compra") continue;
      const [a, b] = t.parcela.split("/").map(Number);
      for (let i = 1; i <= b - a; i++) { const id = addMes(sel, i); proj[id] = (proj[id] || 0) + t.valor; }
    }
    const pm = Object.keys(proj).sort();
    if (!pm.length) { el.innerHTML = vazioTxt("Nenhuma parcela futura com esses filtros."); return; }
    el.innerHTML = `<p class="muted small">Só o que já foi parcelado até ${rotulo(sel)}, antes de qualquer compra nova.</p><div class="chart"><canvas id="cParc" aria-label="Parcelas futuras por mês"></canvas></div>`;
    chart("cParc", { type: "bar", data: { labels: pm.map(rotulo), datasets: [{ label: "Parcelas", data: pm.map((m) => proj[m]), ...bar, backgroundColor: css("--s2") }] }, options: baseOpts() });
  },
  top(c, el) {
    setSub("top", `· ${rotuloEscopo(c.esc)}`);
    const agg = {};
    for (const t of c.t) { if (t.valor <= 0) continue; const a = (agg[t.estabelecimento] ||= { n: 0, v: 0, c: t.categoria }); a.n++; a.v += t.valor / c.div; }
    const linhas = Object.entries(agg).sort((a, b) => b[1].v - a[1].v).slice(0, 25);
    el.innerHTML = linhas.length ? `<div class="tbl"><table><thead><tr><th>Estabelecimento</th><th class="n">Vezes</th><th class="n">Total</th><th>Categoria</th></tr></thead><tbody>` +
      linhas.map(([e, a]) => `<tr><td>${esc(e)}</td><td class="n">${a.n}</td><td class="n">${brl(a.v)}</td><td>${selCat(e, a.c)}</td></tr>`).join("") + "</tbody></table></div>" : vazioTxt("Nada com esses filtros.");
  },
  rec(c, el) {
    const cobr = {};
    for (const x of DB.faturas) for (const t of txs(x)) if (!t.parcela && t.valor > 0) ((cobr[t.estabelecimento] ||= {})[x.meta.id] ||= []).push(t.valor);
    const rec = {};
    for (const [e, pm] of Object.entries(cobr)) {
      const atual = pm[sel]; if (!atual) continue;
      const cat = c.t.find((t) => t.estabelecimento === e).categoria;
      const parecidos = Object.values(pm).filter((v) => v.length === 1 && Math.abs(v[0] - atual[0]) <= 0.1 * atual[0]).length;
      if (cat === "Assinaturas" || (atual.length === 1 && parecidos >= 2)) rec[e] = { v: atual.reduce((a, b) => a + b, 0), n: Object.keys(pm).length, c: cat };
    }
    const recs = Object.entries(rec).sort((a, b) => b[1].v - a[1].v);
    el.innerHTML = `<p class="muted small">Categoria Assinaturas, mais cobranças únicas que se repetem com valor parecido em outras faturas.</p>` + (recs.length ?
      `<div class="tbl"><table><thead><tr><th>Estabelecimento</th><th class="n">Neste mês</th><th class="n">Faturas</th><th>Categoria</th></tr></thead><tbody>` +
      recs.map(([e, r]) => `<tr><td>${esc(e)}</td><td class="n">${brl(r.v)}</td><td class="n">${r.n} de ${DB.faturas.length}</td><td><span class="tag">${esc(r.c)}</span></td></tr>`).join("") +
      `<tr><td><b>Total</b></td><td class="n"><b>${brl(recs.reduce((a, [, r]) => a + r.v, 0))}</b></td><td></td><td></td></tr></tbody></table></div>` : vazioTxt("Nada recorrente com esses filtros."));
  },
  lanc(c, el) {
    setSub("lanc", `· ${F.visao === "media3" ? rotuloEscopo(c.esc, "acum") : rotuloEscopo(c.esc)} · ${c.t.length} lançamentos · ${brl(soma(c.t))}`);
    const rows = c.t.slice().sort((a, b) => (b.data || "").localeCompare(a.data || "")).slice(0, 1500);
    el.innerHTML = `<p class="muted small">Mude a categoria de um estabelecimento e a correção vale para todas as faturas.</p>` + (rows.length ?
      `<div class="tbl long"><table><thead><tr><th>Data</th><th>Estabelecimento</th><th>Parcela</th><th>Cartão</th><th class="n">Valor</th><th>Categoria</th></tr></thead><tbody>` +
      rows.map((t) => `<tr><td>${t.data ? t.data.slice(8) + "/" + t.data.slice(5, 7) : ""}</td><td>${esc(t.descricao)}</td><td>${esc(t.parcela || "")}</td><td>${esc(nomeCartao(t))}</td><td class="n">${brl(t.valor)}</td><td>${selCat(t.estabelecimento, t.categoria)}</td></tr>`).join("") +
      "</tbody></table></div>" : vazioTxt("Nenhum lançamento com esses filtros."));
  },
  fat(c, el) {
    const lista = (DB.arquivos || []).slice().sort((a, b) => b.mes.localeCompare(a.mes) || a.banco.localeCompare(b.banco));
    el.innerHTML = `<div class="tbl"><table><thead><tr><th>Fatura</th><th>Banco</th><th>Vencimento</th><th class="n">Total</th><th class="n">Lançamentos</th><th>Leitura</th><th></th></tr></thead><tbody>` +
      lista.map((x) => {
        const dif = x.soma_lancamentos == null ? 0 : Math.abs(x.soma_lancamentos - x.total);
        const leitura = dif > 0.05 ? `<span class="tag alerta" title="A soma dos lançamentos (${brl(x.soma_lancamentos)}) difere do total">confira (${brl(dif)})</span>`
          : x.avisos?.length ? `<span class="tag" title="${esc(x.avisos.join("; "))}">ok, com observação</span>` : `<span class="tag">ok</span>`;
        return `<tr><td>${rotulo(x.mes)}</td><td>${esc(x.banco)}</td><td>${x.vencimento.split("-").reverse().join("/")}</td><td class="n">${brl(x.total)}</td><td class="n">${x.n_lancamentos}</td><td>${leitura}</td><td class="n"><button class="btn link" data-del="${esc(x.chave)}" data-del-nome="${esc(x.banco + ", " + rotulo(x.mes))}">Remover</button></td></tr>`;
      }).join("") + "</tbody></table></div>";
  },
};

function render() {
  const has = DB.faturas.length > 0;
  $("#vazio").hidden = has; $("#painel").hidden = !has;
  document.body.classList.toggle("editando", editando);
  $("#barraEdicao").hidden = !editando;
  $("#editar").setAttribute("aria-pressed", String(editando));
  $("#editar").textContent = editando ? "Concluir" : "Personalizar";
  if (!has) return;

  const c = contexto();
  const all = ids(), ativos = [];
  if ((F.de && F.de !== all[0]) || (F.ate && F.ate !== all[all.length - 1])) ativos.push(`período ${rotulo(c.fs[0].meta.id)} a ${rotulo(c.fs[c.fs.length - 1].meta.id)}`);
  if (F.cats) ativos.push(F.cats.size === 1 ? [...F.cats][0] : `${F.cats.size} categorias`);
  if (F.banco) ativos.push(F.banco);
  if (F.cartao) ativos.push("cartão " + ($("#fCartao").selectedOptions[0]?.textContent || ""));
  if (F.tipo) ativos.push(F.tipo === "vista" ? "à vista" : "parcelado");
  document.querySelectorAll(".filtros [data-ativo]").forEach((x) => x.removeAttribute("data-ativo"));
  if (F.cats) $("#fCatBox").setAttribute("data-ativo", "");
  if (F.banco) $("#fBanco").setAttribute("data-ativo", "");
  if (F.cartao) $("#fCartao").setAttribute("data-ativo", "");
  if (F.busca.trim()) $("#fBusca").setAttribute("data-ativo", "");
  if (F.busca.trim()) ativos.push(`“${F.busca.trim()}”`);
  $("#fResumo").textContent = ativos.length ? `Filtrando: ${ativos.join(" · ")}. Cards, gráficos e tabelas mostram só o que passa nos filtros.` : "";
  $("#fResumo").hidden = !ativos.length;
  $("#fLimpar").hidden = !ativos.length;

  renderKpis(c);
  for (const k of Object.keys(charts)) { charts[k].destroy(); delete charts[k]; }
  const visiveis = PREFS.paineis.filter((p) => !p.hidden);
  $("#paineis").innerHTML = visiveis.map((p, i) => cascaPainel(p, i, visiveis)).join("");
  for (const p of visiveis) RENDER[p.id](c, document.getElementById(`corpo-${p.id}`));

  const ocultos = PREFS.paineis.filter((p) => p.hidden);
  $("#addPainel").innerHTML = `<option value="">${ocultos.length ? "+ Reexibir painel…" : "Nenhum painel escondido"}</option>` +
    ocultos.map((p) => `<option value="${p.id}">${esc(p.titulo || PAINEIS[p.id].nome)}</option>`).join("");
  $("#addPainel").disabled = !ocultos.length;
}

// ---------- Eventos ----------
const swap = (lista, i, j) => { if (i < 0 || j < 0 || i >= lista.length || j >= lista.length) return false; [lista[i], lista[j]] = [lista[j], lista[i]]; return true; };
const mudou = () => { salvarPrefs(); render(); };

document.addEventListener("change", async (e) => {
  const t = e.target, d = t.dataset;
  if (t.id === "mes") { sel = t.value; render(); }
  else if (t.id === "arquivo") { await enviar(t.files); t.value = ""; }
  else if (t.id === "fDe" || t.id === "fAte") {
    F.de = $("#fDe").value; F.ate = $("#fAte").value;
    if (F.de > F.ate) { if (t.id === "fDe") F.ate = F.de; else F.de = F.ate; $("#fDe").value = F.de; $("#fAte").value = F.ate; }
    if (sel < F.de || sel > F.ate) { sel = F.ate; $("#mes").value = sel; }
    marcarSegmentos(); mudou();
  }
  else if (t.id === "fCartao") { F.cartao = t.value; mudou(); }
  else if (t.id === "fBanco") { F.banco = t.value; mudou(); }
  else if (t.closest("#fCat")) { lerCats(); mudou(); }
  else if (d.kpiMetrica) { const k = PREFS.kpis.find((x) => x.id === d.kpiMetrica); k.m = t.value; delete k.titulo; mudou(); }
  else if (d.kpiTitulo) { const k = PREFS.kpis.find((x) => x.id === d.kpiTitulo); const v = t.value.trim(); if (v) k.titulo = v; else delete k.titulo; mudou(); }
  else if (d.pTitulo) { const p = PREFS.paineis.find((x) => x.id === d.pTitulo); const v = t.value.trim(); if (v && v !== PAINEIS[p.id].nome) p.titulo = v; else delete p.titulo; mudou(); }
  else if (t.id === "addPainel" && t.value) {
    const p = PREFS.paineis.find((x) => x.id === t.value); p.hidden = false;
    PREFS.paineis = [...PREFS.paineis.filter((x) => x !== p), p]; mudou();
  }
  else if (d.est) {
    try {
      await api("/api/categorias", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ estabelecimento: d.est, categoria: t.value }) });
      aviso(`Categoria de ${d.est} agora é ${t.value}, em todas as faturas.`); await carregar(sel);
    } catch (err) { aviso(err.message, true); }
  }
});

document.addEventListener("click", async (e) => {
  const b = e.target.closest("button"); if (!b) return;
  const d = b.dataset;
  if (d.del) {
    const nome = d.delNome || d.del;
    if (!confirm(`Remover a fatura ${nome} do painel? O PDF salvo também será apagado.`)) return;
    await api(`/api/faturas/${encodeURIComponent(d.del)}`, { method: "DELETE" }); aviso(`Fatura ${nome} removida.`); await carregar(sel);
  }
  else if (b.id === "editar") { editando = !editando; render(); }
  else if (b.id === "concluir") { editando = false; render(); }
  else if (b.id === "fLimpar") { Object.assign(F, { de: "", ate: "", cats: null, banco: "", cartao: "", tipo: "", busca: "" }); montarControles(); mudou(); }
  else if (d.visao) { F.visao = d.visao; marcarSegmentos(); mudou(); }
  else if (d.tipo !== undefined) { F.tipo = d.tipo; marcarSegmentos(); mudou(); }
  else if (d.periodo) {
    const [de, ate] = presetDatas(d.periodo, ids()); F.de = de; F.ate = ate;
    $("#fDe").value = de; $("#fAte").value = ate;
    if (sel < de || sel > ate) { sel = ate; $("#mes").value = sel; }
    marcarSegmentos(); mudou();
  }
  else if (b.hasAttribute("data-cat-todas")) { F.cats = null; montarControles(); mudou(); }
  else if (b.hasAttribute("data-cat-nenhuma")) { F.cats = new Set(); montarControles(); mudou(); }
  else if (b.id === "addKpi") { PREFS.kpis.push({ id: "k" + Date.now().toString(36), m: "maior" }); mudou(); document.querySelector("#kpis .kpi:last-child select")?.focus(); }
  else if (b.id === "restaurar") {
    if (!confirm("Voltar os cards e painéis para o padrão? Seus filtros continuam.")) return;
    const f = PREFS.filtros; PREFS = PADRAO(); PREFS.filtros = f; mudou();
  }
  else if (d.kpiMover) { const i = PREFS.kpis.findIndex((x) => x.id === d.kpiMover); if (swap(PREFS.kpis, i, i + +d.dir)) mudou(); }
  else if (d.kpiRemover) { PREFS.kpis = PREFS.kpis.filter((x) => x.id !== d.kpiRemover); mudou(); }
  else if (d.kpiRenomear) { delete PREFS.kpis.find((x) => x.id === d.kpiRenomear).titulo; mudou(); }
  else if (d.pMover) {
    const vis = PREFS.paineis.filter((p) => !p.hidden), i = vis.findIndex((p) => p.id === d.pMover), j = i + +d.dir;
    if (j < 0 || j >= vis.length) return;
    if (swap(PREFS.paineis, PREFS.paineis.indexOf(vis[i]), PREFS.paineis.indexOf(vis[j]))) mudou();
  }
  else if (d.pLargura) { const p = PREFS.paineis.find((x) => x.id === d.pLargura); p.wide = !p.wide; mudou(); }
  else if (d.pEsconder) { PREFS.paineis.find((x) => x.id === d.pEsconder).hidden = true; mudou(); }
  else if (d.pRenomear) { delete PREFS.paineis.find((x) => x.id === d.pRenomear).titulo; mudou(); }
});

let buscaTimer = null;
$("#fBusca").addEventListener("input", (e) => { clearTimeout(buscaTimer); buscaTimer = setTimeout(() => { F.busca = e.target.value; mudou(); }, 250); });
document.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.target.classList?.contains("titulo-edit")) e.target.blur(); });
document.addEventListener("click", (e) => { const box = $("#fCatBox"); if (box.open && !box.contains(e.target)) box.open = false; });

let dragN = 0;
const temArquivo = (e) => [...(e.dataTransfer?.types || [])].includes("Files");
addEventListener("dragenter", (e) => { if (!temArquivo(e)) return; e.preventDefault(); dragN++; $("#drop").hidden = false; });
addEventListener("dragleave", (e) => { if (!temArquivo(e)) return; if (--dragN <= 0) { dragN = 0; $("#drop").hidden = true; } });
addEventListener("dragover", (e) => { if (temArquivo(e)) e.preventDefault(); });
addEventListener("drop", (e) => { if (!temArquivo(e)) return; e.preventDefault(); dragN = 0; $("#drop").hidden = true; enviar(e.dataTransfer.files); });
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", render);

Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
carregarPrefs().then(() => carregar()).catch((e) => aviso("Não consegui falar com o servidor local: " + e.message, true));

// Avisa o servidor local de que a janela está aberta (ele pode desligar sozinho quando ela fecha).
setInterval(() => { fetch("/api/saude", { cache: "no-store" }).catch(() => {}); }, 20000);
