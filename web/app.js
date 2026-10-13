"use strict";
/* Muvim — interface estática. Lê os JSON gerados por exportar.py (pasta dados/).
   Lista, maratona e alertas ficam no navegador (localStorage). As Ligações são calculadas aqui. */

const MES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dt = s => new Date(s + "T12:00:00");
const HOJE = new Date(); HOJE.setHours(12, 0, 0, 0);
const HOJE_ISO = `${HOJE.getFullYear()}-${String(HOJE.getMonth() + 1).padStart(2, "0")}-${String(HOJE.getDate()).padStart(2, "0")}`;
const dias = s => Math.round((dt(s) - HOJE) / 864e5);
const fmt = s => s ? `${dt(s).getDate()} ${MES[dt(s).getMonth()]}` : "";
const fmtAno = s => s ? `${fmt(s)} ${s.slice(0, 4)}` : "";
const em = s => { const n = dias(s); return n === 0 ? "hoje" : n === 1 ? "amanhã" : n === -1 ? "ontem" : n < 0 ? `há ${-n} dias` : `em ${n} dias`; };
const pt = n => Number(n || 0).toLocaleString("pt-BR");
const nome = t => t.titulo_pt && t.titulo_pt !== t.titulo ? t.titulo_pt : t.titulo;
const linkT = id => "#titulo/" + encodeURIComponent(id);
const dataPrinc = t => t.data_br || t.data_eua;
const ondeData = t => t.tipo === "serie" ? "" : t.data_br ? "no Brasil" : "nos EUA";
const juntar = xs => xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " e " + xs[xs.length - 1];
const normalizar = s => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[-.]/g, " ").replace(/\s+/g, " ").trim();
const nota = t => t.rt != null ? `<span class="star" title="Rotten Tomatoes">🍅 ${t.rt}%</span>` : t.nota_tvmaze ? `<span class="star" title="Nota do público no TVmaze">★ ${t.nota_tvmaze}</span>` : "";

/* ---------- dados ---------- */
const cache = {};
async function carregar(arq) {
  if (!cache[arq]) cache[arq] = fetch("dados/" + arq).then(r => { if (!r.ok) throw new Error(`${arq}: ${r.status}`); return r.json(); });
  try { return await cache[arq]; } catch (e) { delete cache[arq]; throw e; }
}
let INDICE = null, POR_ID = null;
async function indice() {
  if (!INDICE) { INDICE = await carregar("indice.json"); POR_ID = Object.fromEntries(INDICE.map(t => [t.id, t])); }
  return INDICE;
}

/* ---------- guardado no navegador ---------- */
const LS = {
  get(k, d) { try { return JSON.parse(localStorage.getItem("muvim-" + k)) ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem("muvim-" + k, JSON.stringify(v)); } catch {} },
};
const lista = () => LS.get("lista", {});           // { id: { em: "2026-10-13", temp, ep } }
const naLista = id => id in lista();
function alternarLista(id) {
  const l = lista();
  if (l[id]) delete l[id]; else l[id] = { em: HOJE_ISO };
  LS.set("lista", l);
  atualizarSino();
  return !!l[id];
}

function render(html) { $("tela").innerHTML = html; }
function carregando() { render('<div class="carregando">Carregando…</div>'); }
function falha(e) { render(`<div class="vazio">Não deu para carregar: ${esc(e.message)}.</div>`); }

/* ---------- peças ---------- */
function ticket(t) {
  const d = dataPrinc(t), dd = dt(d);
  const meta = t.tipo === "serie"
    ? `<span class="svc">${esc(t.servico || "")}</span>${t.temporada === 1 ? '<span class="pill new">Série nova</span>' : `<span class="pill ret">Temporada ${t.temporada ?? "?"}</span>`}`
    : t.onde_br ? `<span class="svc">${esc(t.onde_br.join(", "))}</span>Lançamento direto no streaming`
    : `Cinema ${ondeData(t)} · ${esc(t.estudio || "")}`;
  return `<a class="ticket" href="${linkT(t.id)}"><div class="stub"><b class="num">${dd.getDate()}</b><span>${MES[dd.getMonth()]}</span></div>
  <div class="body"><div style="min-width:0"><h4>${esc(nome(t))}</h4><div class="meta">${meta} ${nota(t)}</div></div>${t.poster ? `<img src="${esc(t.poster)}" alt="" loading="lazy">` : ""}</div></a>`;
}
function ticketSemData(t) {
  return `<a class="ticket" href="${linkT(t.id)}"><div class="stub"><b>—</b><span>sem data</span></div><div class="body"><div><h4>${esc(nome(t))}</h4><div class="meta">${t.tipo === "serie" ? esc(t.servico || "Série") : "Filme"}</div></div>${t.poster ? `<img src="${esc(t.poster)}" alt="">` : ""}</div></a>`;
}
const cartaoQualquer = t => dataPrinc(t) ? ticket(t) : ticketSemData(t);

function cartaoSerie(s) {
  return `<a class="scard" href="${linkT(s.id)}"><div class="ph">${s.poster ? `<img src="${esc(s.poster)}" alt="" loading="lazy">` : '<div style="aspect-ratio:16/10"></div>'}<span class="cd">${em(s.data_eua)}</span></div>
  <div class="in"><div><span class="svc">${esc(s.servico || "")}</span>${s.temporada === 1 ? '<span class="pill new">Série nova</span>' : `<span class="pill ret">Temporada ${s.temporada}</span>`}</div>
  <h4>${esc(nome(s))}</h4><p>${esc(s.sinopse_pt || s.sinopse_en || "")}</p>
  <div style="font-size:12px;color:var(--muted)">${s.nota_tvmaze ? `<span class="star">★ ${s.nota_tvmaze}</span> no TVmaze` : "Ainda sem nota"}</div></div></a>`;
}

/* ---------- Radar ---------- */
async function vRadar() {
  const R = await carregar("radar.json");
  const k = R.kpis, ag = R.aguardado;
  const semanas = R.semanas.map((w, i) => {
    const atual = HOJE_ISO >= w.inicio && HOJE_ISO <= w.fim;
    return `<div class="wk${atual ? " now" : ""}"><div class="wk-h"><b>${fmt(w.inicio)}</b><span>sem ${i + 1}</span></div>
    <div class="posters">${w.itens.map(x => `<a class="pchip${x.tipo === "serie" ? " tv" : ""}" href="${linkT(x.id)}" title="${esc(nome(x))}"><img src="${esc(x.poster)}" alt="${esc(nome(x))}" loading="lazy"><span class="day">${dt(x.data_eua).getDate()}/${dt(x.data_eua).getMonth() + 1}</span></a>`).join("")}</div>
    <div class="density"><i style="height:${Math.max(3, w.n_filmes * 3)}px"></i><i class="tv" style="height:${Math.max(3, w.n_series * 5)}px"></i><span>${w.n_filmes} filmes<br>${w.n_series} séries</span></div></div>`;
  }).join("");
  const choques = R.choques.filter(c => c.dia >= HOJE_ISO).map(c => `<div class="clash"><div class="vs">${c.filmes.map(f => f.poster ? `<a href="${linkT(f.id)}"><img src="${esc(f.poster)}" alt="${esc(nome(f))}"></a>` : "").join("<b>×</b>")}</div>
    <div><div class="eyebrow" style="color:var(--rose)">Choque de estreias</div><h3>${esc(juntar(c.filmes.map(nome)))} no mesmo dia</h3>
    <p>${c.comuns.length ? `${esc(juntar(c.comuns))} ${c.comuns.length > 1 ? "estão" : "está"} em mais de um deles. ` : ""}${c.filmes.length > 2 ? "Lançamentos grandes" : "Dois lançamentos grandes"} disputando as mesmas salas no mesmo fim de semana.</p></div>
    <div class="date"><b class="num">${dt(c.dia).getDate()}</b><span class="eyebrow">${MES[dt(c.dia).getMonth()]} · EUA</span></div></div>`).join("");
  const proximos = R.proximos.filter(t => t.data_eua >= HOJE_ISO && dias(t.data_eua) <= 6);
  // Aniversários só valem no dia em que foram coletados
  const anivs = R.gerado === HOJE_ISO ? R.aniversarios.map(a => {
    const contexto = a.proximos.length ? `Estreia ${a.proximos.map(p => `<a href="${linkT(p.id)}">${esc(p.titulo)}</a> em ${fmt(p.data_eua)}`).join(" e ")}.`
      : a.conhecido.length ? `Conhecido por ${a.conhecido.map(esc).join(", ")}.` : esc(a.descricao);
    const morto = /died/i.test(a.descricao);
    return `<div><b class="num">${morto ? "†" : (HOJE.getFullYear() - a.ano)}</b><p><strong>${esc(a.nome)}</strong> <span class="muted">· ${a.ano}</span><small>${contexto}</small></p></div>`;
  }).join("") : "";
  render(`<section class="view">
    <div class="opener"><div><div class="eyebrow">Radar · próximas 12 semanas</div><h1>O que <em>vem aí</em></h1>
      <p>Estreias de cinema e de temporadas, de fontes abertas, atualizadas todo dia.</p>
      <div class="kpis"><div class="kpi"><b class="num">${pt(k.filmes)}</b><span>filmes estreando<br>em 12 semanas</span></div>
      <div class="kpi"><b class="num">${pt(k.series)}</b><span>temporadas<br>chegando</span></div>
      <div class="kpi"><b class="num">${pt(k.pessoas)}</b><span>atores com<br>2+ estreias</span></div>
      <a class="kpi" href="#mudou" style="text-decoration:none"><b class="num">${pt(k.mudancas)}</b><span>mudanças<br>desde ontem</span></a></div></div>
      ${ag ? `<a class="next" href="${linkT(ag.id)}">${ag.poster ? `<img src="${esc(ag.poster)}" alt="">` : ""}<div class="in"><div class="eyebrow">Mais aguardado</div><div class="big num">${dias(ag.data_eua)}</div><div class="eyebrow" style="margin-top:-4px">dias para</div><h3>${esc(nome(ag))}</h3><p>${fmtAno(ag.data_eua)} nos EUA${ag.data_br ? ` · ${fmtAno(ag.data_br)} no Brasil` : ""}. Popularidade medida por quantas Wikipedias já têm artigo: ${ag.hype}.</p></div></a>` : ""}
    </div>
    <div><div class="sec-h"><h2>Faixa do tempo</h2><p>Cada coluna é uma semana. A barra embaixo mostra quantas estreias caem nela.</p></div>
      <div class="reel"><div class="reel-in">${semanas}</div></div>
      <div class="legend"><span><i style="background:var(--amber)"></i>Filme (data nos EUA)</span><span><i style="background:var(--teal)"></i>Série (estreia de temporada)</span><span><i style="background:color-mix(in srgb,var(--amber) 30%,transparent)"></i>Semana atual</span></div></div>
    ${choques ? `<div class="clashes">${choques}</div>` : ""}
    <div class="two"><div><div class="sec-h"><h2>Próximos 7 dias</h2></div><div class="list">${proximos.map(ticket).join("") || '<div class="vazio">Nada nos próximos 7 dias.</div>'}</div></div>
      <div><div class="sec-h"><h2>Aniversários hoje</h2></div><div class="bday">${anivs || '<div class="vazio">Os aniversariantes de hoje entram na próxima coleta.</div>'}</div></div></div>
  </section>`);
}

/* ---------- Séries ---------- */
async function vSeries() {
  const S = (await carregar("series.json")).filter(s => dias(s.data_eua) >= -3);
  render(`<section class="view"><div><div class="sec-h"><h2>Temporadas chegando</h2><p>Estreias de temporada nos streamings e na TV brasileira.</p></div>
  <div class="sgrid">${S.map(cartaoSerie).join("") || '<div class="vazio">Nenhuma estreia de temporada na coleta.</div>'}</div></div></section>`);
}

/* ---------- Pessoas ---------- */
async function vPessoas() {
  const P = await carregar("pessoas.json");
  const t0 = dt(P.inicio), span = dt(P.fim) - t0;
  const pos = s => ((dt(s) - t0) / span * 100).toFixed(2) + "%";
  const ticks = [];
  for (let d = new Date(t0.getFullYear(), t0.getMonth() + 1, 1, 12); d < dt(P.fim); d.setMonth(d.getMonth() + 1)) ticks.push(d.toISOString().slice(0, 10));
  const linhas = P.pessoas.map(p => {
    const mesmoDia = new Set(p.itens.map(i => i.d)).size < p.itens.length;
    return `<div class="prow"><div class="nm">${esc(p.nome)}<small>${p.itens.length} estreias</small></div><div class="track">${ticks.map(t => `<div class="tick" style="left:${pos(t)}"></div>`).join("")}
    ${p.itens.map((i, k) => `<a class="dot${i.tipo === "serie" ? " tv" : ""}${mesmoDia ? " hot" : ""}" href="${linkT(i.id)}" style="left:${pos(i.d)};top:${k % 2 ? 70 : 30}%"><i></i>${esc(i.t)}</a>`).join("")}</div></div>`;
  }).join("");
  render(`<section class="view"><div><div class="sec-h"><h2>Agenda do elenco</h2><p>Quem tem mais de uma estreia nos próximos 120 dias, cruzando os elencos de filmes e séries.</p></div>
  ${P.pessoas.length ? `<div class="ppl"><div class="thead"><div></div><div class="track">${[P.inicio, ...ticks].map(t => `<span style="left:${pos(t)}">${fmt(t)}</span>`).join("")}</div></div>${linhas}</div>` : '<div class="vazio">Ninguém com duas estreias na janela.</div>'}
  <p class="note" style="margin-top:14px">Em vermelho: dois títulos da mesma pessoa no mesmo dia. Âmbar é filme, verde é série.</p></div></section>`);
}

/* ---------- O que mudou ---------- */
let filtroMudou = "tudo";
async function vMudou() {
  const M = await carregar("mudancas.json");
  const campos = [["tudo", "Tudo"], ["data", "Datas"], ["novo", "Novos no radar"], ["rt", "Crítica"], ["onde_br", "Streaming"], ["temporada", "Temporadas"]];
  const vis = M.filter(m => filtroMudou === "tudo" || m.campo === filtroMudou || (filtroMudou === "data" && m.campo.startsWith("data")));
  const porDia = {};
  vis.forEach(m => (porDia[m.dia] ??= []).push(m));
  const fmtVal = (c, v) => !v ? "—" : c.startsWith("data") ? fmtAno(v) : c === "onde_br" ? (() => { try { return JSON.parse(v).join(", "); } catch { return v; } })() : c === "rt" ? v + "%" : v;
  const item = m => {
    const desc = m.campo === "novo" ? `Entrou no radar${m.depois ? ` · estreia ${fmtAno(m.depois)}` : ""}`
      : `${esc(m.rotulo)}: <s>${esc(fmtVal(m.campo, m.antes))}</s> → <b>${esc(fmtVal(m.campo, m.depois))}</b>`;
    return `<a class="chg" href="${linkT(m.id)}">${m.poster ? `<img src="${esc(m.poster)}" alt="" loading="lazy">` : '<div class="ph"></div>'}<div><b>${esc(m.titulo)}</b><div class="muted" style="font-size:13px">${desc}</div></div><span class="tag ${esc(m.campo)}">${esc(m.rotulo)}</span></a>`;
  };
  render(`<section class="view"><div><div class="sec-h"><h2>O que mudou</h2><p>Últimos 30 dias. Cada coleta compara com a anterior e registra o que mudou.</p></div>
  <div class="filtros">${campos.map(([c, r]) => `<button class="btn small" data-filtro="${c}" aria-pressed="${filtroMudou === c}">${r}</button>`).join("")}</div>
  <div class="feed" style="margin-top:20px">${Object.entries(porDia).map(([d, ms]) => {
    const n = dias(d);
    return `<div><h3>${n === 0 ? "Hoje" : n === -1 ? "Ontem" : fmtAno(d)} <span class="muted num" style="font-size:14px">${ms.length}</span></h3>${ms.slice(0, 80).map(item).join("")}</div>`;
  }).join("") || '<div class="vazio">Nada mudou ainda. A partir da segunda coleta, adiamentos, novas datas e notas aparecem aqui.</div>'}</div></div></section>`);
  document.querySelectorAll("[data-filtro]").forEach(b => b.onclick = () => { filtroMudou = b.dataset.filtro; vMudou(); });
}

/* ---------- Ligações (busca no próprio navegador) ---------- */
let GRAFO = null;
async function grafo() {
  if (GRAFO) return GRAFO;
  const G = await carregar("grafo.json");
  const tp = G.t.map(() => []);                  // título -> pessoas
  G.e.forEach((ts, p) => ts.forEach(t => tp[t].push(p)));
  // Mais conhecidos primeiro, para o caminho escolhido passar por gente que se reconhece
  tp.forEach(ps => ps.sort((a, b) => G.p[b][1] - G.p[a][1]));
  const porNome = new Map();
  G.p.forEach(([n], i) => { const k = normalizar(n); if (!porNome.has(k)) porNome.set(k, i); });  // já vem por popularidade
  GRAFO = { ...G, tp, porNome };
  return GRAFO;
}
function caminho(G, a, b, maxPassos = 6) {
  if (a === b) return [[a, null]];
  const pais = [new Map([[a, null]]), new Map([[b, null]])];
  let fr = [[a], [b]];
  for (let passo = 0; passo < maxPassos; passo++) {
    const lado = fr[0].length <= fr[1].length ? 0 : 1, outro = 1 - lado;
    const prox = [], encontros = [];
    for (const p of fr[lado]) {
      for (const t of G.e[p]) {               // títulos já vêm do mais popular para o menos
        for (const q of G.tp[t]) {
          if (!pais[lado].has(q)) { pais[lado].set(q, [p, t]); prox.push(q); }
          if (pais[outro].has(q) && !encontros.includes(q)) encontros.push(q);
        }
      }
    }
    fr[lado] = prox;
    if (encontros.length) {
      const m = encontros.reduce((x, y) => G.p[y][1] > G.p[x][1] ? y : x);
      // De A até o encontro; cada pessoa leva o título que a liga à anterior
      const ida = [];
      for (let n = m; n !== undefined;) { ida.push(n); const pai = pais[0].get(n); n = pai ? pai[0] : undefined; }
      ida.reverse();
      const res = ida.map((p, i) => [p, i === 0 ? null : pais[0].get(p)[1]]);
      // Do encontro até B
      for (let n = m; pais[1].get(n);) { const [pai, t] = pais[1].get(n); res.push([pai, t]); n = pai; }
      return res;
    }
    if (!prox.length) break;
  }
  return null;
}
let ultimaLigacao = ["Florence Pugh", "Fernanda Torres"];
async function vLigacoes() {
  render(`<section class="view"><div><div class="sec-h"><h2>Ligações</h2><p>O caminho mais curto entre duas pessoas: cada passo é um filme ou série em que as duas estão no elenco ou na direção (Wikidata).</p></div>
  <form class="link-form" id="fl"><label>De<input id="la" list="sug" value="${esc(ultimaLigacao[0])}" autocomplete="off"></label><span class="and">→</span>
  <label>Até<input id="lb" list="sug" value="${esc(ultimaLigacao[1])}" autocomplete="off"></label><button class="btn primary">Ligar</button></form>
  <datalist id="sug"></datalist><div id="caminho"><div class="carregando">Carregando o grafo…</div></div></div></section>`);
  const G = await grafo();
  const sug = e => {
    const v = normalizar(e.target.value); if (v.length < 2) return;
    const achados = []; for (const [k, i] of G.porNome) { if (k.startsWith(v)) achados.push(i); if (achados.length > 300) break; }
    $("sug").innerHTML = achados.sort((x, y) => G.p[y][1] - G.p[x][1]).slice(0, 8).map(i => `<option value="${esc(G.p[i][0])}">`).join("");
  };
  $("la").oninput = sug; $("lb").oninput = sug;
  $("fl").onsubmit = e => { e.preventDefault(); ultimaLigacao = [$("la").value, $("lb").value]; ligar(G); };
  ligar(G);
}
function ligar(G) {
  const [a, b] = ultimaLigacao.map(n => G.porNome.get(normalizar(n)));
  const falta = a === undefined ? ultimaLigacao[0] : b === undefined ? ultimaLigacao[1] : null;
  if (falta) { $("caminho").innerHTML = `<div class="vazio" style="margin-top:20px">Não encontrei “${esc(falta)}”. O grafo tem pessoas com artigo em 8 ou mais Wikipedias.</div>`; return; }
  const c = caminho(G, a, b);
  if (!c) { $("caminho").innerHTML = '<div class="vazio" style="margin-top:20px">Não achei ligação em até 6 passos.</div>'; return; }
  const passos = c.length - 1;
  $("caminho").innerHTML = `<div style="display:flex;gap:16px;align-items:baseline;margin-top:28px"><span class="steps num">${passos}</span><span class="muted">${passos === 1 ? "passo" : "passos"} de ${esc(G.p[c[0][0]][0])} até ${esc(G.p[c[passos][0]][0])}</span></div>
  <div class="path">${c.map(([p, t], i) => `${t != null ? `<span class="via"><span>${esc(G.t[t][0])}</span><span class="num">${G.t[t][1] || ""}</span></span>` : ""}<span class="p${i === 0 || i === passos ? " end" : ""}">${esc(G.p[p][0])}</span>`).join("")}</div>`;
}

/* ---------- Minha lista ---------- */
async function vLista() {
  await indice();
  const L = Object.keys(lista()).map(id => POR_ID[id]).filter(Boolean)
    .sort((a, b) => (dataPrinc(a) || "9999") < (dataPrinc(b) || "9999") ? -1 : 1);
  render(`<section class="view"><div><div class="sec-h"><h2>Minha lista</h2><p>Fica guardada neste navegador. O sino avisa quando algo daqui muda de data, entra em streaming ou estreia em breve.</p></div>
  <div class="list">${L.map(cartaoQualquer).join("") || '<div class="vazio">Sua lista está vazia. Abra um filme ou série e use “+ Quero ver”.</div>'}</div></div></section>`);
}

/* ---------- Título ---------- */
async function vTitulo(id) {
  await indice();
  const ent = POR_ID[id];
  if (!ent) throw new Error("título não encontrado");
  const T = await carregar(`t/${ent.a}.json`);
  const serie = T.tipo === "serie";
  const sinopse = T.sinopse_pt || T.sinopse_en || "";
  const fonteSin = T.sinopse_pt ? (T.sinopse_pt_fonte || "") : T.sinopse_en ? "Wikipedia em inglês" : "";
  const fatos = [
    !serie && T.data_eua && ["Estreia EUA", fmtAno(T.data_eua)],
    T.data_br && ["Estreia Brasil", fmtAno(T.data_br)],
    serie && T.data_eua && [`Temporada ${T.temporada}`, fmtAno(T.data_eua)],
    serie && T.servico && ["Onde", T.servico],
    T.onde_br && ["Lançamento direto em", T.onde_br.join(", ")],
    T.direcao && ["Direção", T.direcao],
    T.estudio && ["Estúdio", T.estudio],
    T.generos?.length && ["Gêneros", T.generos.join(", ")],
    serie && T.estreou && ["No ar desde", T.estreou.slice(0, 4)],
    T.rt != null && ["Rotten Tomatoes", `🍅 ${T.rt}%`],
    T.mc != null && ["Metacritic", `${T.mc}/100`],
    T.nota_tvmaze && ["Público no TVmaze", `★ ${T.nota_tvmaze}`],
    T.hype && !serie && ["Wikipedias com artigo", T.hype],
  ].filter(Boolean);
  const cruz = {};
  (T.cruzamentos || []).forEach(c => (cruz[c.id] ??= { ...c, pessoas: [] }).pessoas.push(c.pessoa));
  const links = [
    T.wiki_pagina && `<a class="btn" href="https://en.wikipedia.org/wiki/${encodeURIComponent(T.wiki_pagina.replace(/ /g, "_"))}" target="_blank" rel="noopener">Wikipedia ↗</a>`,
    T.wikidata && `<a class="btn" href="https://www.wikidata.org/wiki/${esc(T.wikidata)}" target="_blank" rel="noopener">Wikidata ↗</a>`,
    T.tvmaze_id && `<a class="btn" href="https://www.tvmaze.com/shows/${T.tvmaze_id}" target="_blank" rel="noopener">TVmaze ↗</a>`,
  ].filter(Boolean).join("");
  const quer = naLista(T.id);
  render(`<section class="view">
  <div class="title-hero">${T.poster ? `<img src="${esc(T.poster)}" alt="Pôster de ${esc(nome(T))}">` : `<div class="noimg">${esc(nome(T).slice(0, 1))}</div>`}
    <div><div class="eyebrow">${serie ? "Série" : "Filme"}${T.data_eua ? ` · ${em(dataPrinc(T))}` : ""}</div>
    <h1>${esc(nome(T))}</h1>${nome(T) !== T.titulo ? `<div class="orig">${esc(T.titulo)}</div>` : ""}
    <div class="sin">${esc(sinopse)}${fonteSin ? `<small>Sinopse: ${esc(fonteSin)}</small>` : ""}</div>
    <div class="facts">${fatos.map(([k, v]) => `<div><span>${k}</span><b>${esc(v)}</b></div>`).join("")}</div>
    <div class="acts"><button class="btn primary" id="quero" aria-pressed="${quer}">${quer ? "✓ Na minha lista" : "+ Quero ver"}</button>${links}</div></div></div>
  ${serie && T.episodios?.length ? maratonaHTML(T) : ""}
  ${T.elenco?.length ? `<div><div class="sec-h"><h2>Elenco</h2></div><div class="cast">${T.elenco.map(e => `<div><b>${esc(e.pessoa)}</b><span>${esc(e.papel || "")}</span></div>`).join("")}</div></div>` : ""}
  ${T.curiosidades?.length ? `<div><div class="sec-h"><h2>Curiosidades</h2><p>Trechos do artigo da Wikipedia (em inglês). Cada um mostra de onde veio.</p></div>
    <div class="trivia">${T.curiosidades.map(c => `<article><p>${esc(c.texto)}</p><div class="src">Fonte: ${esc(c.fonte)}</div></article>`).join("")}</div></div>` : ""}
  ${T.franquia?.length ? `<div><div class="sec-h"><h2>A franquia na crítica</h2><p>Rotten Tomatoes de cada título da franquia, segundo o Wikidata. Âmbar é cinema, verde é TV.</p></div><div class="chart">${graficoFranquia(T.franquia)}</div></div>` : ""}
  ${Object.keys(cruz).length ? `<div><div class="sec-h"><h2>O elenco em outros lançamentos</h2></div><div class="list">${Object.values(cruz).map(c => `<a class="ticket" href="${linkT(c.id)}"><div class="stub"><b class="num">${dt(c.data_eua).getDate()}</b><span>${MES[dt(c.data_eua).getMonth()]}</span></div><div class="body"><div><h4>${esc(c.titulo)}</h4><div class="meta">com ${esc(c.pessoas.join(", "))}</div></div></div></a>`).join("")}</div></div>` : ""}
  ${T.mudancas?.length ? `<div><div class="sec-h"><h2>Histórico</h2><p>O que mudou neste título desde que entrou no radar.</p></div><div class="hist">${T.mudancas.map(m => `<div><span class="num muted">${fmtAno(m.dia)}</span><span>${esc(m.campo)}: <s class="muted">${esc(m.antes ?? "—")}</s> → ${esc(m.depois)}</span></div>`).join("")}</div></div>` : ""}
  </section>`);
  $("quero").onclick = () => {
    const on = alternarLista(T.id);
    $("quero").setAttribute("aria-pressed", on);
    $("quero").textContent = on ? "✓ Na minha lista" : "+ Quero ver";
  };
  if (serie && T.episodios?.length) ligarMaratona(T);
}

function graficoFranquia(F) {
  const W = Math.max(560, F.length * 120), H = 270, L = 40, R = 16, T = 22, B = 58, bw = (W - L - R) / F.length;
  const y = v => T + (H - T - B) * (1 - v / 100);
  let g = "";
  for (let v = 0; v <= 100; v += 20) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-dasharray="${v === 0 ? 0 : 3} 4"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)" font-family="var(--f-mono)">${v}</text>`;
  F.forEach((f, i) => {
    const x = L + i * bw + bw * .2, w = bw * .6, top = y(f.rt), cinema = f.tipo === "filme";
    const nm = f.nome.length > 18 ? f.nome.slice(0, 17) + "…" : f.nome;
    g += `<rect x="${x}" y="${top}" width="${w}" height="${y(0) - top}" rx="3" fill="${cinema ? "var(--amber)" : "var(--teal)"}"/>
    <text x="${x + w / 2}" y="${top - 7}" text-anchor="middle" font-size="14" font-weight="700" fill="var(--fg)" font-family="var(--f-mono)">${f.rt}%</text>
    <text x="${x + w / 2}" y="${H - B + 18}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--fg)"><title>${esc(f.nome)}</title>${esc(nm)}</text>
    <text x="${x + w / 2}" y="${H - B + 34}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="var(--f-mono)">${f.ano || ""} · ${cinema ? "filme" : "TV"}</text>
    <text x="${x + w / 2}" y="${H - B + 49}" text-anchor="middle" font-size="10" fill="var(--faint)" font-family="var(--f-mono)">${f.mc != null ? `Metacritic ${f.mc}` : ""}</text>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" style="min-width:${W}px" role="img" aria-label="Rotten Tomatoes da franquia">${g}</svg>`;
}

/* ---------- Maratona ---------- */
function maratonaHTML(T) {
  const temps = [...new Set(T.episodios.map(e => e[0]))];
  return `<div><div class="sec-h"><h2>Planejar maratona</h2><p>Quanto falta para ficar em dia${T.data_eua && dias(T.data_eua) > 0 ? ` antes da temporada ${T.temporada}` : ""}. O progresso fica salvo neste navegador.</p></div>
  <div class="marathon"><div class="row"><span>Já vi até</span>
    <select id="mt">${['<option value="0">nada ainda</option>', ...temps.map(t => `<option value="${t}">temporada ${t}</option>`)].join("")}</select>
    <select id="me"></select></div>
    <div class="seasons" id="mbar" aria-hidden="true"></div><div class="res" id="mres"></div></div></div>`;
}
function ligarMaratona(T) {
  const alvo = T.data_eua && T.data_eua > HOJE_ISO ? T.data_eua : null;
  const eps = T.episodios.map(([temporada, numero, nomeEp, data, duracao]) => ({ temporada, numero, nome: nomeEp, data, duracao }));
  const mt = $("mt"), me = $("me");
  const progresso = LS.get("maratona", {});
  const preencherEp = () => {
    const t = +mt.value;
    me.innerHTML = t ? eps.filter(e => e.temporada === t).map(e => `<option value="${e.numero}">episódio ${e.numero}</option>`).join("") : "";
    me.hidden = !t;
    if (t) me.value = eps.filter(e => e.temporada === t).slice(-1)[0].numero;
  };
  const calc = () => {
    const t = +mt.value, n = +me.value || 0;
    const visto = e => t && (e.temporada < t || (e.temporada === t && e.numero <= n));
    const lancado = e => e.data && e.data <= HOJE_ISO;
    const falta = eps.filter(e => lancado(e) && !visto(e) && (!alvo || e.data < alvo));
    const min = falta.reduce((s, e) => s + (e.duracao || 45), 0);
    const h = Math.floor(min / 60), m = min % 60;
    const ate = alvo ? Math.max(1, dias(alvo)) : null;
    $("mbar").innerHTML = eps.map(e => `<i class="${visto(e) ? "vi" : lancado(e) ? "fa" : "fu"}" title="T${e.temporada}E${e.numero} ${esc(e.nome || "")}"></i>`).join("");
    $("mres").innerHTML = `<div><b class="num">${falta.length}</b><span>episódios para ver</span></div>
      <div><b class="num">${h}h${String(m).padStart(2, "0")}</b><span>de maratona</span></div>
      ${ate ? `<div><b class="num">${Math.ceil(min / ate)} min</b><span>por dia até ${fmt(alvo)}</span></div>` : ""}`;
    progresso[T.id] = { temp: t || null, ep: n || null };
    LS.set("maratona", progresso);
  };
  mt.onchange = () => { preencherEp(); calc(); };
  me.onchange = calc;
  const salvo = progresso[T.id];
  if (salvo?.temp) { mt.value = salvo.temp; preencherEp(); me.value = salvo.ep; } else preencherEp();
  calc();
}

/* ---------- Rodapé: quando atualizou e de onde vêm os dados ---------- */
async function rodape() {
  let quando = "";
  try {
    const B = await carregar("bastidores.json");
    if (B.ultima_coleta) {
      const d = new Date(B.ultima_coleta + "Z");
      quando = `Atualizado em ${d.toLocaleDateString("pt-BR", { day: "numeric", month: "long" })}, às ${d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}. `;
    }
  } catch {}
  $("rodape").innerHTML = `${quando}Dados de <a href="https://www.wikipedia.org" target="_blank" rel="noopener">Wikipedia</a>,
    <a href="https://www.wikidata.org" target="_blank" rel="noopener">Wikidata</a> e <a href="https://www.tvmaze.com" target="_blank" rel="noopener">TVmaze</a>.
    Pôsteres exibidos direto das fontes. Notas da crítica: Rotten Tomatoes e Metacritic, via Wikidata.`;
}

/* ---------- busca e alertas (gaveta) ---------- */
function gaveta(html) { $("painel").innerHTML = `<button class="btn small" id="fechar" style="float:right">Fechar</button>` + html; $("gaveta").hidden = false; $("fechar").onclick = fechar; $("fechar").focus(); }
function fechar() { $("gaveta").hidden = true; }
$("sombra").onclick = fechar;
document.addEventListener("keydown", e => { if (e.key === "Escape") fechar(); });
$("painel").addEventListener("click", e => { if (e.target.closest("a[href^='#']")) fechar(); });

$("busca").onsubmit = async e => {
  e.preventDefault();
  const q = normalizar($("q").value);
  if (!q) return;
  const I = await indice();
  const tits = I.filter(t => normalizar(t.titulo).includes(q) || normalizar(t.titulo_pt).includes(q)).slice(0, 20);
  const pessoas = {};
  I.forEach(t => (t.e || []).forEach(p => { if (normalizar(p).includes(q)) (pessoas[p] ??= []).push(t); }));
  gaveta(`<div class="eyebrow">Busca</div><h3>“${esc($("q").value)}”</h3>
  ${tits.length ? `<div class="list">${tits.map(cartaoQualquer).join("")}</div>` : ""}
  ${Object.entries(pessoas).slice(0, 8).map(([p, ts]) => `<h3 style="font-size:24px;margin-top:22px">${esc(p)}</h3><div class="list">${ts.map(cartaoQualquer).join("")}</div>`).join("")}
  ${!tits.length && !Object.keys(pessoas).length ? `<p class="muted">Nada no radar com esse nome. Para ligar duas pessoas quaisquer, use <a href="#ligacoes">Ligações</a>.</p>` : ""}`);
};

/* Alertas: calculados aqui, a partir da lista do navegador e das mudanças publicadas */
async function alertas() {
  const l = lista(), ids = Object.keys(l);
  if (!ids.length) return [];
  const [I, M] = await Promise.all([indice(), carregar("mudancas.json").catch(() => [])]);
  const out = [];
  for (const m of M) {
    if (!(m.id in l) || m.campo === "novo" || m.dia < l[m.id].em) continue;
    const v = x => !x ? "—" : m.campo.startsWith("data") ? fmtAno(x) : x;
    out.push({ k: `m:${m.id}:${m.campo}:${m.depois}`, id: m.id, quando: m.dia, txt: `${m.titulo}: ${m.rotulo.toLowerCase()} ${v(m.antes)} → ${v(m.depois)}` });
  }
  for (const id of ids) {
    const t = POR_ID[id]; if (!t) continue;
    const d = dataPrinc(t);
    if (d && dias(d) >= 0 && dias(d) <= 7) {
      const txt = t.tipo === "serie" ? `${nome(t)}: temporada ${t.temporada} estreia ${em(d)} (${fmt(d)}, ${t.servico || ""})` : `${nome(t)} estreia ${em(d)} ${ondeData(t)} (${fmt(d)})`;
      out.push({ k: `e:${id}:${d}`, id, quando: HOJE_ISO, txt });
    }
  }
  return out.sort((a, b) => a.quando < b.quando ? 1 : -1);
}
async function atualizarSino() {
  const A = await alertas();
  const vistos = new Set(LS.get("alertas-vistos", []));
  const n = A.filter(a => !vistos.has(a.k)).length;
  $("sino-n").hidden = !n; $("sino-n").textContent = n;
  return A;
}
$("sino").onclick = async () => {
  const A = await atualizarSino();
  const vistos = new Set(LS.get("alertas-vistos", []));
  gaveta(`<div class="eyebrow">Minha lista</div><h3>Alertas</h3>${A.map(a => `<a class="alert${vistos.has(a.k) ? "" : " novo"}" href="${linkT(a.id)}" style="text-decoration:none"><b>${esc(a.txt)}</b><small>${fmtAno(a.quando)}</small></a>`).join("") || '<p class="muted">Nenhum alerta. Eles aparecem quando algo da sua lista muda ou está para estrear.</p>'}`);
  LS.set("alertas-vistos", [...new Set([...vistos, ...A.map(a => a.k)])].slice(-500));
  atualizarSino();
};

/* ---------- rotas ---------- */
const ROTAS = { radar: vRadar, series: vSeries, pessoas: vPessoas, mudou: vMudou, ligacoes: vLigacoes, lista: vLista };
async function navegar() {
  const h = decodeURIComponent(location.hash.slice(1)) || "radar";
  const [rota, ...resto] = h.split("/");
  document.querySelectorAll("#abas a").forEach(a => a.getAttribute("href") === "#" + rota ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  carregando();
  scrollTo({ top: 0 });
  try {
    if (rota === "titulo") await vTitulo(resto.join("/"));
    else await (ROTAS[rota] || vRadar)();
  } catch (e) { falha(e); }
}
$("today").textContent = HOJE.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
addEventListener("hashchange", navegar);
navegar();
atualizarSino();
rodape();
