"use strict";
/* Muvim — interface. Fala com a API local (servidor.py) e desenha as telas por rota (#radar, #titulo/<id>...). */

const MES = ["jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez"];
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dt = s => new Date(s + "T12:00:00");
const HOJE = new Date(); HOJE.setHours(12, 0, 0, 0);
const dias = s => Math.round((dt(s) - HOJE) / 864e5);
const fmt = s => s ? `${dt(s).getDate()} ${MES[dt(s).getMonth()]}` : "";
const fmtAno = s => s ? `${fmt(s)} ${s.slice(0, 4)}` : "";
const em = s => { const n = dias(s); return n === 0 ? "hoje" : n === 1 ? "amanhã" : n === -1 ? "ontem" : n < 0 ? `há ${-n} dias` : `em ${n} dias`; };
const pt = n => Number(n || 0).toLocaleString("pt-BR");
const nome = t => t.titulo_pt && t.titulo_pt !== t.titulo ? t.titulo_pt : t.titulo;
const linkT = id => "#titulo/" + encodeURIComponent(id);
const dataPrinc = t => t.data_br || t.data_eua;
const juntar = xs => xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " e " + xs[xs.length - 1];
const ondeData = t => t.tipo === "serie" ? "" : t.data_br ? "no Brasil" : "nos EUA";

async function api(caminho, corpo) {
  const op = corpo ? { method: "POST", headers: { "Content-Type": "application/json", "X-Muvim": "1" }, body: JSON.stringify(corpo) } : {};
  const r = await fetch(caminho, op);
  const j = await r.json();
  if (!r.ok || j.erro) throw new Error(j.erro || r.statusText);
  return j;
}

function render(html) { $("tela").innerHTML = html; }
function carregando() { render('<div class="carregando">Carregando…</div>'); }
function falha(e) { render(`<div class="vazio">Não deu para carregar: ${esc(e.message)}. O servidor está rodando?</div>`); }

/* ---------- peças ---------- */
function ticket(t) {
  const d = dataPrinc(t), dd = dt(d);
  const meta = t.tipo === "serie"
    ? `<span class="svc">${esc(t.servico || "")}</span>${t.temporada === 1 ? '<span class="pill new">Série nova</span>' : `<span class="pill ret">Temporada ${t.temporada ?? "?"}</span>`}`
    : `Cinema ${ondeData(t)} · ${esc(t.estudio || "")}`;
  return `<a class="ticket" href="${linkT(t.id)}"><div class="stub"><b class="num">${dd.getDate()}</b><span>${MES[dd.getMonth()]}</span></div>
  <div class="body"><div style="min-width:0"><h4>${esc(nome(t))}</h4><div class="meta">${meta} ${t.nota_imdb ? `<span class="star">★ ${t.nota_imdb}</span>` : ""}</div></div>${t.poster ? `<img src="${t.poster}" alt="" loading="lazy">` : ""}</div></a>`;
}

function cartaoSerie(s) {
  return `<a class="scard" href="${linkT(s.id)}"><div class="ph">${s.poster ? `<img src="${s.poster}" alt="" loading="lazy">` : '<div style="aspect-ratio:16/10"></div>'}<span class="cd">${em(s.data_eua)}</span></div>
  <div class="in"><div><span class="svc">${esc(s.servico || "")}</span>${s.temporada === 1 ? '<span class="pill new">Série nova</span>' : `<span class="pill ret">Temporada ${s.temporada}</span>`}</div>
  <h4>${esc(nome(s))}</h4><p>${esc(s.sinopse_pt || s.sinopse_en || "")}</p>
  <div style="font-size:12px;color:var(--muted)">${s.nota_imdb ? `<span class="star">★ ${s.nota_imdb}</span> IMDb · ${pt(s.votos_imdb)} votos` : "Ainda sem nota no IMDb"}</div></div></a>`;
}

/* ---------- Radar ---------- */
async function vRadar() {
  const R = await api("/api/radar");
  const k = R.kpis, ag = R.aguardado;
  const hojeIso = R.hoje;
  const semanas = R.semanas.map((w, i) => {
    const atual = hojeIso >= w.inicio && hojeIso <= w.fim;
    return `<div class="wk${atual ? " now" : ""}"><div class="wk-h"><b>${fmt(w.inicio)}</b><span>sem ${i + 1}</span></div>
    <div class="posters">${w.itens.map(x => `<a class="pchip${x.tipo === "serie" ? " tv" : ""}" href="${linkT(x.id)}" title="${esc(nome(x))}"><img src="${x.poster}" alt="${esc(nome(x))}" loading="lazy"><span class="day">${dt(x.data_eua).getDate()}/${dt(x.data_eua).getMonth() + 1}</span></a>`).join("")}</div>
    <div class="density"><i style="height:${Math.max(3, w.n_filmes * 3)}px"></i><i class="tv" style="height:${Math.max(3, w.n_series * 5)}px"></i><span>${w.n_filmes} filmes<br>${w.n_series} séries</span></div></div>`;
  }).join("");
  const choques = R.choques.map(c => `<div class="clash"><div class="vs">${c.filmes.map(f => f.poster ? `<a href="${linkT(f.id)}"><img src="${f.poster}" alt="${esc(nome(f))}"></a>` : "").join("<b>×</b>")}</div>
    <div><div class="eyebrow" style="color:var(--rose)">Choque de estreias</div><h3>${esc(juntar(c.filmes.map(nome)))} no mesmo dia</h3>
    <p>${c.comuns.length ? `${esc(juntar(c.comuns))} ${c.comuns.length > 1 ? "estão" : "está"} em mais de um deles. ` : ""}${c.filmes.length > 2 ? "Lançamentos grandes" : "Dois lançamentos grandes"} disputando as mesmas salas no mesmo fim de semana.</p></div>
    <div class="date"><b class="num">${dt(c.dia).getDate()}</b><span class="eyebrow">${MES[dt(c.dia).getMonth()]} · EUA</span></div></div>`).join("");
  const anivs = R.aniversarios.map(a => {
    const contexto = a.proximos.length ? `Estreia ${a.proximos.map(p => `<a href="${linkT(p.id)}">${esc(p.titulo)}</a> em ${fmt(p.data_eua)}`).join(" e ")}.`
      : a.conhecido.length ? `Conhecido por ${a.conhecido.map(esc).join(", ")}.` : esc(a.descricao);
    const morto = /died/i.test(a.descricao);
    return `<div><b class="num">${morto ? "†" : (new Date().getFullYear() - a.ano)}</b><p><strong>${esc(a.nome)}</strong> <span class="muted">· ${a.ano}</span><small>${contexto}</small></p></div>`;
  }).join("");
  render(`<section class="view">
    <div class="opener"><div><div class="eyebrow">Radar · próximas 12 semanas</div><h1>O que <em>vem aí</em></h1>
      <p>Estreias de cinema e de temporadas, guardadas no seu PC e atualizadas todo dia.</p>
      <div class="kpis"><div class="kpi"><b class="num">${pt(k.filmes)}</b><span>filmes estreando<br>em 12 semanas</span></div>
      <div class="kpi"><b class="num">${pt(k.series)}</b><span>temporadas<br>chegando</span></div>
      <div class="kpi"><b class="num">${pt(k.pessoas)}</b><span>atores com<br>2+ estreias</span></div>
      <a class="kpi" href="#mudou" style="text-decoration:none"><b class="num">${pt(k.mudancas)}</b><span>mudanças<br>desde ontem</span></a></div></div>
      ${ag ? `<a class="next" href="${linkT(ag.id)}">${ag.poster ? `<img src="${ag.poster}" alt="">` : ""}<div class="in"><div class="eyebrow">Mais aguardado</div><div class="big num">${dias(ag.data_eua)}</div><div class="eyebrow" style="margin-top:-4px">dias para</div><h3>${esc(nome(ag))}</h3><p>${fmtAno(ag.data_eua)} nos EUA${ag.data_br ? ` · ${fmtAno(ag.data_br)} no Brasil` : ""}. Popularidade medida por quantas Wikipedias já têm artigo: ${ag.hype}.</p></div></a>` : ""}
    </div>
    <div><div class="sec-h"><h2>Faixa do tempo</h2><p>Cada coluna é uma semana. A barra embaixo mostra quantas estreias caem nela.</p></div>
      <div class="reel"><div class="reel-in">${semanas}</div></div>
      <div class="legend"><span><i style="background:var(--amber)"></i>Filme (data nos EUA)</span><span><i style="background:var(--teal)"></i>Série (estreia de temporada)</span><span><i style="background:color-mix(in srgb,var(--amber) 30%,transparent)"></i>Semana atual</span></div></div>
    ${choques ? `<div class="clashes">${choques}</div>` : ""}
    <div class="two"><div><div class="sec-h"><h2>Próximos 7 dias</h2></div><div class="list">${R.esta_semana.map(ticket).join("") || '<div class="vazio">Nada nos próximos 7 dias.</div>'}</div></div>
      <div><div class="sec-h"><h2>Aniversários hoje</h2></div><div class="bday">${anivs || '<div class="vazio">Sem aniversariantes de cinema na coleta de hoje.</div>'}</div></div></div>
  </section>`);
}

/* ---------- Séries ---------- */
async function vSeries() {
  const S = await api("/api/series");
  render(`<section class="view"><div><div class="sec-h"><h2>Temporadas chegando</h2><p>Estreias de temporada nos streamings e na TV brasileira, com nota do IMDb.</p></div>
  <div class="sgrid">${S.map(cartaoSerie).join("") || '<div class="vazio">Nenhuma estreia de temporada na coleta.</div>'}</div></div></section>`);
}

/* ---------- Pessoas ---------- */
async function vPessoas() {
  const P = await api("/api/pessoas");
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
  const M = await api("/api/mudancas?dias=14");
  const campos = [["tudo", "Tudo"], ["data", "Datas"], ["novo", "Novos no radar"], ["nota_imdb", "Notas"], ["onde_br", "Onde assistir"], ["temporada", "Temporadas"]];
  const vis = M.filter(m => filtroMudou === "tudo" || m.campo === filtroMudou || (filtroMudou === "data" && m.campo.startsWith("data")));
  const porDia = {};
  vis.forEach(m => (porDia[m.dia] ??= []).push(m));
  const fmtVal = (c, v) => !v ? "—" : c.startsWith("data") ? fmtAno(v) : c === "onde_br" ? (() => { try { return JSON.parse(v).join(", "); } catch { return v; } })() : v;
  const item = m => {
    const desc = m.campo === "novo" ? `Entrou no radar${m.depois ? ` · estreia ${fmtAno(m.depois)}` : ""}`
      : `${esc(m.rotulo)}: <s>${esc(fmtVal(m.campo, m.antes))}</s> → <b>${esc(fmtVal(m.campo, m.depois))}</b>`;
    return `<a class="chg" href="${linkT(m.id)}">${m.poster ? `<img src="${m.poster}" alt="" loading="lazy">` : '<div class="ph"></div>'}<div><b>${esc(m.titulo)}</b><div class="muted" style="font-size:13px">${desc}</div></div><span class="tag ${esc(m.campo)}">${esc(m.rotulo)}</span></a>`;
  };
  render(`<section class="view"><div><div class="sec-h"><h2>O que mudou</h2><p>Últimos 14 dias. Cada coleta compara com a anterior e registra o que mudou.</p></div>
  <div class="filtros">${campos.map(([c, r]) => `<button class="btn small" data-filtro="${c}" aria-pressed="${filtroMudou === c}">${r}</button>`).join("")}</div>
  <div class="feed" style="margin-top:20px">${Object.entries(porDia).map(([d, ms]) => {
    const n = dias(d);
    return `<div><h3>${n === 0 ? "Hoje" : n === -1 ? "Ontem" : fmtAno(d)} <span class="muted num" style="font-size:14px">${ms.length}</span></h3>${ms.slice(0, 80).map(item).join("")}</div>`;
  }).join("") || '<div class="vazio">Nada mudou ainda. A partir da segunda coleta, adiamentos, novas datas e notas aparecem aqui.</div>'}</div></div></section>`);
  document.querySelectorAll("[data-filtro]").forEach(b => b.onclick = () => { filtroMudou = b.dataset.filtro; vMudou(); });
}

/* ---------- Ligações ---------- */
let ultimaLigacao = ["Florence Pugh", "Fernanda Torres"];
async function vLigacoes() {
  render(`<section class="view"><div><div class="sec-h"><h2>Ligações</h2><p>O caminho mais curto entre duas pessoas: cada passo é um filme ou série em que as duas estão no elenco principal ou na direção (IMDb).</p></div>
  <form class="link-form" id="fl"><label>De<input id="la" list="sug" value="${esc(ultimaLigacao[0])}" autocomplete="off"></label><span class="and">→</span>
  <label>Até<input id="lb" list="sug" value="${esc(ultimaLigacao[1])}" autocomplete="off"></label><button class="btn primary">Ligar</button></form>
  <datalist id="sug"></datalist><div id="caminho"><div class="carregando">Procurando…</div></div></div></section>`);
  const sug = async e => { const v = e.target.value; if (v.length < 2) return; try { $("sug").innerHTML = (await api("/api/sugerir-pessoas?q=" + encodeURIComponent(v))).map(n => `<option value="${esc(n)}">`).join(""); } catch {} };
  $("la").oninput = sug; $("lb").oninput = sug;
  $("fl").onsubmit = e => { e.preventDefault(); ultimaLigacao = [$("la").value, $("lb").value]; ligar(); };
  ligar();
}
async function ligar() {
  const [a, b] = ultimaLigacao;
  $("caminho").innerHTML = '<div class="carregando">Procurando…</div>';
  try {
    const R = await api(`/api/conexao?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
    const c = R.caminho;
    $("caminho").innerHTML = `<div style="display:flex;gap:16px;align-items:baseline;margin-top:28px"><span class="steps num">${R.passos}</span><span class="muted">${R.passos === 1 ? "passo" : "passos"} de ${esc(c[0].pessoa)} até ${esc(c[c.length - 1].pessoa)}</span></div>
    <div class="path">${c.map((p, i) => `${p.via ? `<span class="via"><span>${esc(p.via)}</span><span class="num">${p.ano || ""}</span></span>` : ""}<span class="p${i === 0 || i === c.length - 1 ? " end" : ""}">${esc(p.pessoa)}</span>`).join("")}</div>`;
  } catch (e) {
    $("caminho").innerHTML = `<div class="vazio" style="margin-top:20px">${esc(e.message)}</div>`;
  }
}

/* ---------- Minha lista ---------- */
async function vLista() {
  const L = await api("/api/lista");
  render(`<section class="view"><div><div class="sec-h"><h2>Minha lista</h2><p>Você recebe um alerta quando um destes muda de data, ganha onde assistir ou tem episódio novo.</p></div>
  <div class="list">${L.map(ticketLista).join("") || '<div class="vazio">Sua lista está vazia. Abra um filme ou série e use “+ Quero ver”.</div>'}</div></div></section>`);
}
function ticketLista(t) {
  const d = dataPrinc(t);
  if (d) return ticket(t);
  return `<a class="ticket" href="${linkT(t.id)}"><div class="stub"><b>—</b><span>sem data</span></div><div class="body"><div><h4>${esc(nome(t))}</h4><div class="meta">${t.tipo === "serie" ? esc(t.servico || "Série") : "Filme"}</div></div>${t.poster ? `<img src="${t.poster}" alt="">` : ""}</div></a>`;
}

/* ---------- Título ---------- */
async function vTitulo(id) {
  const T = await api("/api/titulo?id=" + encodeURIComponent(id));
  const serie = T.tipo === "serie";
  const sinopse = T.sinopse_pt || T.sinopse_en || "";
  const fonteSin = T.sinopse_pt ? (T.sinopse_pt_fonte || "") : T.sinopse_en ? "Wikipedia em inglês, sem tradução ainda" : "";
  const fatos = [
    !serie && T.data_eua && ["Estreia EUA", fmtAno(T.data_eua)],
    T.data_br && ["Estreia Brasil", fmtAno(T.data_br)],
    serie && T.data_eua && [`Temporada ${T.temporada}`, fmtAno(T.data_eua)],
    serie && T.servico && ["Onde", T.servico],
    T.onde_br && ["Streaming no Brasil", T.onde_br.join(", ")],
    T.direcao && ["Direção", T.direcao],
    T.estudio && ["Estúdio", T.estudio],
    T.generos?.length && ["Gêneros", T.generos.join(", ")],
    serie && T.estreou && ["No ar desde", T.estreou.slice(0, 4)],
    T.nota_imdb && ["IMDb", `★ ${T.nota_imdb} · ${pt(T.votos_imdb)} votos`],
    T.hype && !serie && ["Wikipedias com artigo", T.hype],
  ].filter(Boolean);
  const cruz = {};
  T.cruzamentos.forEach(c => (cruz[c.id] ??= { ...c, pessoas: [] }).pessoas.push(c.pessoa));
  const links = [
    T.imdb_id && `<a class="btn" href="https://www.imdb.com/title/${esc(T.imdb_id)}/" target="_blank" rel="noopener">IMDb ↗</a>`,
    T.wiki_pagina && `<a class="btn" href="https://en.wikipedia.org/wiki/${encodeURIComponent(T.wiki_pagina.replace(/ /g, "_"))}" target="_blank" rel="noopener">Wikipedia ↗</a>`,
    T.tvmaze_id && `<a class="btn" href="https://www.tvmaze.com/shows/${T.tvmaze_id}" target="_blank" rel="noopener">TVmaze ↗</a>`,
  ].filter(Boolean).join("");
  render(`<section class="view">
  <div class="title-hero">${T.poster ? `<img src="${T.poster}" alt="Pôster de ${esc(nome(T))}">` : `<div class="noimg">${esc(nome(T).slice(0, 1))}</div>`}
    <div><div class="eyebrow">${serie ? "Série" : "Filme"}${T.data_eua ? ` · ${em(dataPrinc(T))}` : ""}</div>
    <h1>${esc(nome(T))}</h1>${nome(T) !== T.titulo ? `<div class="orig">${esc(T.titulo)}</div>` : ""}
    <div class="sin">${esc(sinopse)}${fonteSin ? `<small>Sinopse: ${esc(fonteSin)}</small>` : ""}</div>
    <div class="facts">${fatos.map(([k, v]) => `<div><span>${k}</span><b>${esc(v)}</b></div>`).join("")}</div>
    <div class="acts"><button class="btn primary" id="quero" aria-pressed="${T.na_lista}">${T.na_lista ? "✓ Na minha lista" : "+ Quero ver"}</button>${links}</div></div></div>
  ${serie && T.episodios?.length ? maratonaHTML(T) : ""}
  ${T.elenco.length ? `<div><div class="sec-h"><h2>Elenco</h2></div><div class="cast">${T.elenco.map(e => `<div><b>${esc(e.pessoa)}</b><span>${esc(e.papel || "")}</span></div>`).join("")}</div></div>` : ""}
  ${T.curiosidades.length ? `<div><div class="sec-h"><h2>Curiosidades</h2><p>${T.curiosidades[0].gerado_por === "claude" ? "Escritas pelo Claude a partir do artigo" : "Trechos do artigo da Wikipedia, ainda em inglês"}. Cada uma mostra de onde veio.</p></div>
    <div class="trivia">${T.curiosidades.map(c => `<article>${c.gerado_por === "claude" ? `<h4>${esc(c.titulo)}</h4>` : ""}<p>${esc(c.texto)}</p><div class="src">Fonte: ${esc(c.fonte)}</div></article>`).join("")}</div></div>` : ""}
  ${T.franquia.length ? `<div><div class="sec-h"><h2>A franquia em notas</h2><p>Títulos com o mesmo nome no IMDb. Âmbar é cinema, verde é TV.</p></div><div class="chart">${graficoFranquia(T.franquia)}</div></div>` : ""}
  ${Object.keys(cruz).length ? `<div><div class="sec-h"><h2>O elenco em outros lançamentos</h2></div><div class="list">${Object.values(cruz).map(c => `<a class="ticket" href="${linkT(c.id)}"><div class="stub"><b class="num">${dt(c.data_eua).getDate()}</b><span>${MES[dt(c.data_eua).getMonth()]}</span></div><div class="body"><div><h4>${esc(c.titulo)}</h4><div class="meta">com ${esc(c.pessoas.join(", "))}</div></div></div></a>`).join("")}</div></div>` : ""}
  ${T.mudancas.length ? `<div><div class="sec-h"><h2>Histórico</h2><p>O que mudou neste título desde que entrou no radar.</p></div><div class="hist">${T.mudancas.map(m => `<div><span class="num muted">${fmtAno(m.dia)}</span><span>${esc(m.campo)}: <s class="muted">${esc(m.antes)}</s> → ${esc(m.depois)}</span></div>`).join("")}</div></div>` : ""}
  </section>`);
  $("quero").onclick = async () => {
    const r = await api("/api/lista", { id: T.id, acao: T.na_lista ? "remove" : "add" });
    T.na_lista = r.na_lista;
    $("quero").setAttribute("aria-pressed", T.na_lista);
    $("quero").textContent = T.na_lista ? "✓ Na minha lista" : "+ Quero ver";
  };
  if (serie && T.episodios?.length) ligarMaratona(T);
}

function graficoFranquia(F) {
  const W = Math.max(560, F.length * 120), H = 270, L = 40, R = 16, T = 22, B = 58, bw = (W - L - R) / F.length;
  const min = Math.max(0, Math.floor(Math.min(...F.map(f => f.nota)) - 1));
  const y = v => T + (H - T - B) * (1 - (v - min) / (10 - min));
  let g = "";
  for (let v = min; v <= 10; v++) g += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)" stroke-dasharray="${v === min ? 0 : 3} 4"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end" font-size="11" fill="var(--muted)" font-family="var(--f-mono)">${v}</text>`;
  F.forEach((f, i) => {
    const x = L + i * bw + bw * .2, w = bw * .6, top = y(f.nota), cinema = f.tipo === "movie";
    const nm = f.nome.length > 18 ? f.nome.slice(0, 17) + "…" : f.nome;
    const votos = f.votos >= 1e6 ? (f.votos / 1e6).toFixed(2).replace(".", ",") + " mi" : Math.round(f.votos / 1e3) + " mil";
    g += `<rect x="${x}" y="${top}" width="${w}" height="${y(min) - top}" rx="3" fill="${cinema ? "var(--amber)" : "var(--teal)"}"/>
    <text x="${x + w / 2}" y="${top - 7}" text-anchor="middle" font-size="14" font-weight="700" fill="var(--fg)" font-family="var(--f-mono)">${f.nota.toFixed(1)}</text>
    <text x="${x + w / 2}" y="${H - B + 18}" text-anchor="middle" font-size="12" font-weight="600" fill="var(--fg)"><title>${esc(f.nome)}</title>${esc(nm)}</text>
    <text x="${x + w / 2}" y="${H - B + 34}" text-anchor="middle" font-size="11" fill="var(--muted)" font-family="var(--f-mono)">${f.ano || ""} · ${cinema ? "filme" : "TV"}</text>
    <text x="${x + w / 2}" y="${H - B + 49}" text-anchor="middle" font-size="10" fill="var(--faint)" font-family="var(--f-mono)">${votos} votos</text>`;
  });
  return `<svg viewBox="0 0 ${W} ${H}" style="min-width:${W}px" role="img" aria-label="Notas do IMDb da franquia">${g}</svg>`;
}

/* ---------- Maratona ---------- */
function maratonaHTML(T) {
  const temps = [...new Set(T.episodios.map(e => e.temporada))];
  return `<div><div class="sec-h"><h2>Planejar maratona</h2><p>Quanto falta para ficar em dia${T.data_eua && dias(T.data_eua) > 0 ? ` antes da temporada ${T.temporada}` : ""}.</p></div>
  <div class="marathon"><div class="row"><span>Já vi até</span>
    <select id="mt">${['<option value="0">nada ainda</option>', ...temps.map(t => `<option value="${t}">temporada ${t}</option>`)].join("")}</select>
    <select id="me"></select>${T.na_lista ? '<button class="btn small" id="msalvar">Salvar</button>' : '<span class="muted" style="font-size:13px">Adicione à lista para guardar o progresso.</span>'}</div>
    <div class="seasons" id="mbar" aria-hidden="true"></div><div class="res" id="mres"></div></div></div>`;
}
function ligarMaratona(T) {
  const hoje = new Date().toISOString().slice(0, 10);
  const alvo = T.data_eua && T.data_eua > hoje ? T.data_eua : null;
  const eps = T.episodios;
  const mt = $("mt"), me = $("me");
  const preencherEp = () => {
    const t = +mt.value;
    me.innerHTML = t ? eps.filter(e => e.temporada === t).map(e => `<option value="${e.numero}">episódio ${e.numero}</option>`).join("") : "";
    me.hidden = !t;
    if (t) me.value = eps.filter(e => e.temporada === t).slice(-1)[0].numero;
  };
  const calc = () => {
    const t = +mt.value, n = +me.value || 0;
    const visto = e => t && (e.temporada < t || (e.temporada === t && e.numero <= n));
    const lancado = e => e.data && e.data <= hoje;
    const falta = eps.filter(e => lancado(e) && !visto(e) && (!alvo || e.data < alvo));
    const min = falta.reduce((s, e) => s + (e.duracao || 45), 0);
    const h = Math.floor(min / 60), m = min % 60;
    const ate = alvo ? Math.max(1, dias(alvo)) : null;
    $("mbar").innerHTML = eps.map(e => `<i class="${visto(e) ? "vi" : lancado(e) ? "fa" : "fu"}" title="T${e.temporada}E${e.numero} ${esc(e.nome || "")}"></i>`).join("");
    $("mres").innerHTML = `<div><b class="num">${falta.length}</b><span>episódios para ver</span></div>
      <div><b class="num">${h}h${String(m).padStart(2, "0")}</b><span>de maratona</span></div>
      ${ate ? `<div><b class="num">${Math.ceil(min / ate)} min</b><span>por dia até ${fmt(alvo)}</span></div>` : ""}`;
  };
  mt.onchange = () => { preencherEp(); calc(); };
  me.onchange = calc;
  if (T.assistido && T.assistido.assistido_temp) {
    mt.value = T.assistido.assistido_temp; preencherEp(); me.value = T.assistido.assistido_ep;
  } else preencherEp();
  calc();
  const sv = $("msalvar");
  if (sv) sv.onclick = async () => { await api("/api/lista", { id: T.id, acao: "assistido", temp: +mt.value || null, ep: +me.value || null }); sv.textContent = "Salvo"; };
}

/* ---------- Bastidores ---------- */
const NOMES_FONTES = { "wikipedia-listas": "Wikipedia · listas de estreias", "wikipedia-detalhes": "Wikipedia · resumos e pôsteres", wikidata: "Wikidata · IMDb e popularidade",
  tvmaze: "TVmaze · séries", tmdb: "TMDB · Brasil", "imdb-notas": "IMDb · notas", aniversarios: "Wikimedia · aniversários", posteres: "Pôsteres",
  curiosidades: "Curiosidades por extração", "curadoria-claude": "Curadoria pelo Claude", "imdb-grafo": "IMDb · ligações", alertas: "Alertas" };
async function vBastidores() {
  const B = await api("/api/bastidores");
  const c = B.contagens;
  const cartao = f => {
    const sem = (f.fonte === "tmdb" && f.mensagem === "sem chave") || (f.fonte === "curadoria-claude" && /sem login|não encontrado/.test(f.mensagem || ""));
    const cls = f.status === "erro" ? "erro" : sem ? "off" : f.status === "rodando" ? "warn" : "ok";
    const rot = f.status === "erro" ? "Erro" : sem ? "Desligada" : f.status === "rodando" ? "Rodando" : "Ok";
    return `<article><h4>${esc(NOMES_FONTES[f.fonte] || f.fonte)}<span class="st ${cls}">${rot}</span></h4><div class="big num">${pt(f.itens)}</div>
      <p>${esc(f.mensagem || "")}</p><p class="num" style="font-size:11px">${esc((f.fim || f.inicio || "").replace("T", " "))}</p></article>`;
  };
  render(`<section class="view">
  <div><div class="sec-h"><h2>No seu banco</h2><p>Última coleta completa: ${B.ultima_coleta ? fmtAno(B.ultima_coleta) : "nenhuma ainda"}${B.coletando ? " · coletando agora…" : ""}</p></div>
  <div class="counts">${[[c.filmes, "filmes"], [c.series, "séries"], [c.posteres, "pôsteres"], [c.com_pt, "sinopses em português"], [c.curiosidades, "títulos com curiosidades"], [c.episodios, "episódios"], [c.grafo_pessoas, "pessoas no grafo"], [c.mudancas, "mudanças registradas"]]
    .map(([n, r]) => `<div class="kpi"><b class="num">${pt(n)}</b><span>${r}</span></div>`).join("")}</div>
  <div class="acts" style="margin-top:20px"><button class="btn primary" id="coletar" ${B.coletando ? "disabled" : ""}>${B.coletando ? "Coletando…" : "Atualizar agora"}</button></div></div>
  <div><div class="sec-h"><h2>Fontes</h2><p>Resultado da última execução de cada etapa.</p></div><div class="srcs">${B.fontes.map(cartao).join("") || '<div class="vazio">Nenhuma coleta registrada.</div>'}</div></div>
  <div class="note">${B.tmdb ? "TMDB ligado: datas do Brasil, títulos em português e onde assistir." : "TMDB desligado. Para ligar, crie a conta gratuita, gere a chave e salve só o valor em D:\\Segredos\\Muvim\\tmdb.txt."}<br>
  ${B.claude ? "Claude Code encontrado. Se a curadoria disser “sem login”, rode claude uma vez no terminal e faça /login." : "Claude Code não encontrado neste PC."}</div>
  </section>`);
  $("coletar").onclick = async () => { await api("/api/coletar", {}); $("coletar").textContent = "Coletando…"; $("coletar").disabled = true; };
}

/* ---------- busca e alertas (gaveta) ---------- */
function gaveta(html) { $("painel").innerHTML = `<button class="btn small" id="fechar" style="float:right">Fechar</button>` + html; $("gaveta").hidden = false; $("fechar").onclick = fechar; $("fechar").focus(); }
function fechar() { $("gaveta").hidden = true; }
$("sombra").onclick = fechar;
document.addEventListener("keydown", e => { if (e.key === "Escape") fechar(); });
$("painel").addEventListener("click", e => { if (e.target.closest("a[href^='#']")) fechar(); });

$("busca").onsubmit = async e => {
  e.preventDefault();
  const q = $("q").value.trim();
  if (!q) return;
  const R = await api("/api/busca?q=" + encodeURIComponent(q));
  gaveta(`<div class="eyebrow">Busca</div><h3>“${esc(q)}”</h3>
  ${R.titulos.length ? `<div class="list">${R.titulos.map(t => dataPrinc(t) ? ticket(t) : ticketLista(t)).join("")}</div>` : ""}
  ${R.pessoas.map(p => `<h3 style="font-size:24px;margin-top:22px">${esc(p.pessoa)}</h3><div class="list">${p.titulos.map(t => dataPrinc(t) ? ticket(t) : ticketLista(t)).join("")}</div>`).join("")}
  ${!R.titulos.length && !R.pessoas.length ? `<p class="muted">Nada no banco local com esse nome. Para ligar duas pessoas quaisquer, use <a href="#ligacoes">Ligações</a>.</p>` : ""}`);
};

async function atualizarSino() {
  try {
    const A = await api("/api/alertas");
    const n = A.filter(a => !a.lido).length;
    $("sino-n").hidden = !n; $("sino-n").textContent = n;
    return A;
  } catch { return []; }
}
$("sino").onclick = async () => {
  const A = await atualizarSino();
  gaveta(`<div class="eyebrow">Minha lista</div><h3>Alertas</h3>${A.map(a => `<a class="alert${a.lido ? "" : " novo"}" href="${linkT(a.titulo_id)}" style="text-decoration:none"><b>${esc(a.texto)}</b><small>${esc(a.criado_em.replace("T", " "))}</small></a>`).join("") || '<p class="muted">Nenhum alerta. Eles aparecem quando algo da sua lista muda.</p>'}`);
  if (A.some(a => !a.lido)) { await api("/api/alertas/lidos", {}); atualizarSino(); }
};

/* ---------- rotas ---------- */
const ROTAS = { radar: vRadar, series: vSeries, pessoas: vPessoas, mudou: vMudou, ligacoes: vLigacoes, lista: vLista, bastidores: vBastidores };
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
$("today").textContent = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
addEventListener("hashchange", navegar);
navegar();
atualizarSino();
