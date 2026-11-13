// GRANTH-AI web app (no build step). All answers come from /api/ask; this file never composes answers itself.
import { openStore, downloadBook, Store } from './offline-store.mjs';
import { createVoiceInput, speakGujarati } from './voice.mjs';
import * as imageprep from './imageprep.mjs';

const view = document.getElementById('view');
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ABSTAIN = 'આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી.';
const TIMEOUT_MS = 15000;
const MODES = [['auto', 'આપમેળે'], ['one_line', 'એક વાક્યમાં ઉત્તર'], ['definition', 'વ્યાખ્યા'], ['short', 'ટૂંકો ઉત્તર'],
  ['detailed', 'વિગતવાર ઉત્તર'], ['points', 'મુદ્દાસર ઉત્તર'], ['difference', 'બે બાબતો વચ્ચેનો તફાવત'], ['formula', 'સૂત્ર આધારિત ઉત્તર']];
const FEEDBACK = [['incorrect_answer', 'ઉત્તર ખોટો છે'], ['incorrect_page', 'પૃષ્ઠ ક્રમાંક ખોટો છે'], ['missing_content', 'પાઠ્યપુસ્તકનું લખાણ ખૂટે છે'], ['ocr_error', 'ગુજરાતી અક્ષરોમાં ભૂલ (OCR)']];

// ---------------------------------------------------------------- state
const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (_) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* private mode */ } },
};
let sel = store.get('granth.sel', {});
let catalog = null;
let offlineDb = null;
function session() {
  let s = store.get('granth.session');
  if (!s) { s = 's-' + (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2)); store.set('granth.session', s); }
  return s;
}
function saveSel() { store.set('granth.sel', sel); }
async function db() { if (!offlineDb) offlineDb = await openStore(); return offlineDb; }

async function api(path, opts = {}) {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), opts.timeout || TIMEOUT_MS);
  try {
    const res = await fetch(path, { method: opts.method || 'GET', signal: ctl.signal,
      headers: { ...(opts.body ? { 'Content-Type': 'application/json' } : {}), ...(opts.headers || {}) },
      body: opts.body ? JSON.stringify(opts.body) : undefined });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) { const e = new Error(data.error || `HTTP ${res.status}`); e.status = res.status; throw e; }
    return data;
  } catch (e) {
    if (e.name === 'AbortError') { const t = new Error('સર્વર તરફથી સમયસર જવાબ મળ્યો નથી. ફરી પ્રયત્ન કરો.'); t.offline = true; throw t; }
    if (e.status) throw e;
    const n = new Error('ઇન્ટરનેટ જોડાણ નથી.'); n.offline = true; throw n;
  } finally { clearTimeout(timer); }
}

async function loadCatalog() {
  try {
    catalog = await api('/api/catalog');
    store.set('granth.catalog', catalog);
  } catch (e) {
    catalog = store.get('granth.catalog', null);
    if (!catalog) throw e;
  }
  return catalog;
}

function currentEdition() {
  if (!catalog || !sel.edition_id) return null;
  for (const b of catalog.textbooks) for (const e of b.editions) if (e.edition_id === sel.edition_id) return { book: b, edition: e };
  return null;
}

// ---------------------------------------------------------------- rendering helpers
const loading = (msg = 'લોડ થઈ રહ્યું છે…') => `<p role="status"><span class="spinner"></span> ${esc(msg)}</p>`;
const errorCard = (msg) => `<div class="card err" role="alert">${esc(msg)}</div>`;

function renderText(text) {
  const lines = String(text || '').split('\n');
  let html = '';
  let rows = [];
  const flush = () => {
    if (rows.length) {
      html += '<table class="tb">' + rows.map((r) => '<tr>' + r.replace(/^\||\|$/g, '').split('|').map((c) => `<td>${esc(c.trim())}</td>`).join('') + '</tr>').join('') + '</table>';
      rows = [];
    }
  };
  for (const line of lines) {
    if (line.trim().startsWith('|')) rows.push(line.trim());
    else { flush(); if (line.trim()) html += `<p>${esc(line)}</p>`; }
  }
  flush();
  return html;
}

function highlight(text, parts) {
  let html = esc(text);
  for (const p of parts || []) {
    for (const piece of String(p).split('\n')) {
      const e = esc(piece.trim());
      if (e.length > 3 && html.includes(e)) html = html.replace(e, `<mark>${e}</mark>`);
    }
  }
  return html;
}

function selectionSummary() {
  const cur = currentEdition();
  if (!cur) return `<div class="note">હજી કોઈ પાઠ્યપુસ્તક પસંદ થયું નથી. <a href="#/select">પુસ્તક પસંદ કરો</a></div>`;
  const ch = sel.chapter_id && sel.chapter_title ? ` · પ્રકરણ ${esc(sel.chapter_number)}: ${esc(sel.chapter_title)}` : ' · આખું પુસ્તક';
  return `<div class="note" id="sel-summary"><strong>પસંદ કરેલું પુસ્તક:</strong> ${esc(cur.book.title)} — ધોરણ ${esc(cur.book.standard)}, ${esc(cur.book.subject)}, ${esc(cur.book.medium)} માધ્યમ, આવૃત્તિ ${esc(cur.edition.edition_label)}${ch}
    <br><span class="muted">${esc(cur.book.board)}</span> · <a href="#/select">બદલો</a></div>`;
}

function citationHtml(c) {
  return `<dl class="src">
    <dt>બોર્ડ</dt><dd>${esc(c.board)}</dd><dt>માધ્યમ</dt><dd>${esc(c.medium)}</dd><dt>ધોરણ</dt><dd>${esc(c.standard)}</dd>
    <dt>વિષય</dt><dd>${esc(c.subject)}</dd><dt>પુસ્તક</dt><dd>${esc(c.book_title)} (${esc(c.edition)})</dd>
    <dt>પ્રકરણ</dt><dd>${esc(c.chapter_number)}: ${esc(c.chapter_title)}</dd>
    ${c.section_title ? `<dt>વિભાગ</dt><dd>${esc(c.section_title)}</dd>` : ''}
    <dt>પૃષ્ઠ</dt><dd><a href="#/page/${c.edition_id}/${c.page_number}" class="pagelink">${esc(c.page_number)}</a></dd></dl>`;
}

function evidenceHtml(evidence, parts) {
  const quotes = (parts || []).map((p) => p.text);
  return evidence.map((e) => `<blockquote data-chunk="${e.chunk_id}">${highlight(e.text, quotes)}
    <br><span class="muted">પૃષ્ઠ ${esc(e.page_number)} · ${esc(e.section_title || e.chapter_title || '')} · નિષ્કર્ષણ વિશ્વાસ ${Math.round((e.extraction_confidence || 0) * 100)}%
    · <a href="#/page/${e.edition_id}/${e.page_number}">આખું પૃષ્ઠ જુઓ</a></span></blockquote>`).join('');
}

function resultHtml(r, opts = {}) {
  const banner = opts.offlineSaved ? `<div class="note">ઑફલાઇન: આ ઉપકરણ પર સંગ્રહિત, અગાઉ ચકાસાયેલો ઉત્તર (${esc(opts.offlineSaved.slice(0, 10))}).</div>` : '';
  if (r.status === 'answered') {
    const cacheBadge = r.cache && r.cache.hit ? '<span class="badge ok">સંગ્રહિત ચકાસાયેલો ઉત્તર (cache)</span>' : '';
    const gen = r.answer.generated ? '<span class="badge warn">AI દ્વારા શબ્દરચના – પુરાવા સાથે ચકાસેલી</span>' : '<span class="badge ok">પાઠ્યપુસ્તકના શબ્દોમાં</span>';
    return `${banner}<section class="card answer" id="answer" data-status="answered">
      <h2>ઉત્તર <span class="muted">(${esc(r.mode_label || '')}${r.marks ? `, ${r.marks} ગુણ` : ''})</span></h2>
      <div class="text" id="answer-text">${renderText(r.answer.text)}</div>
      ${r.note ? `<div class="note" id="answer-note">${esc(r.note)}</div>` : ''}
      ${r.edition_note ? `<div class="note">${esc(r.edition_note)}</div>` : ''}
      <p><span class="badge ok">✔ પુરાવા સાથે ચકાસેલું</span>${gen}${cacheBadge}</p>
      <div class="row"><button type="button" id="speak" class="small">🔊 ઉત્તર સાંભળો</button><span id="speak-msg" class="muted"></span></div>
      <h3>સ્રોત</h3>${r.citations.map(citationHtml).join('<hr>')}
      <h3>પુરાવો (પાઠ્યપુસ્તકનું લખાણ)</h3><div id="evidence">${evidenceHtml(r.evidence, r.answer.parts)}</div>
      ${feedbackHtml(r)}</section>`;
  }
  if (r.status === 'edition_conflict') {
    return `${banner}<section class="card conflict" id="answer" data-status="edition_conflict"><h2>આવૃત્તિઓમાં તફાવત</h2><p>${esc(r.message)}</p>
      ${r.editions.map((e) => `<div class="card"><h3>આવૃત્તિ: ${esc(e.edition)}</h3><div class="text">${renderText(e.answer.text)}</div>
        ${e.citations.map(citationHtml).join('')}${evidenceHtml(e.evidence, e.answer.parts)}</div>`).join('')}${feedbackHtml(r)}</section>`;
  }
  return `${banner}<section class="card abstain" id="answer" data-status="abstained" role="status"><h2>ઉત્તર આપી શકાતો નથી</h2>
    <p id="abstain-msg"><strong>${esc(r.message || ABSTAIN)}</strong></p>
    ${r.reason_gu ? `<p class="muted">${esc(r.reason_gu)}</p>` : ''}
    ${r.unmatched_terms && r.unmatched_terms.length ? `<p class="muted">પુસ્તકમાં ન મળેલા શબ્દો: ${r.unmatched_terms.map(esc).join(', ')}</p>` : ''}
    <p class="muted">GRANTH-AI પાઠ્યપુસ્તક બહારની માહિતી પરથી ઉત્તર બનાવતું નથી. જોડણી તપાસો, બીજું પ્રકરણ કે પુસ્તક પસંદ કરો.</p>${feedbackHtml(r)}</section>`;
}

function feedbackHtml(r) {
  if (!r.answer_id) return '';
  return `<details class="fb"><summary>આ ઉત્તર વિશે જાણ કરો</summary>
    <div class="row">${FEEDBACK.map(([k, l]) => `<button type="button" class="small fbk" data-kind="${k}" data-q="${r.question_id}" data-a="${r.answer_id}">${l}</button>`).join('')}</div>
    <p class="muted fb-msg" role="status"></p></details>`;
}

function bindResult(root, r) {
  const speak = $('#speak', root);
  if (speak) speak.onclick = () => {
    const out = speakGujarati(r.answer.text);
    $('#speak-msg', root).textContent = out.spoken ? '' : (out.reason === 'no-gujarati-voice'
      ? 'આ ઉપકરણમાં ગુજરાતી અવાજ ઉપલબ્ધ નથી.' : 'આ બ્રાઉઝરમાં વાંચી સંભળાવવાની સુવિધા નથી.');
  };
  for (const b of $$('.fbk', root)) b.onclick = async () => {
    const msg = b.closest('.fb').querySelector('.fb-msg');
    try {
      const out = await api('/api/feedback', { method: 'POST', body: { kind: b.dataset.kind, question_id: +b.dataset.q, answer_id: +b.dataset.a } });
      msg.textContent = out.message;
    } catch (e) { msg.textContent = e.message; }
  };
}

// ---------------------------------------------------------------- ask pipeline (typed / voice / camera all end here)
async function askQuestion(question, extra, out) {
  const scope = { edition_id: sel.edition_id, chapter_id: sel.chapter_id || null, mode: extra.mode || 'auto', marks: extra.marks || null };
  out.innerHTML = loading('પાઠ્યપુસ્તકમાં શોધી રહ્યું છે…');
  try {
    const r = await api('/api/ask', { method: 'POST', body: { question, edition_id: scope.edition_id, chapter_id: scope.chapter_id,
      mode: scope.mode, marks: scope.marks, session_id: session(), input_method: extra.input_method || 'typed' } });
    out.innerHTML = resultHtml(r);
    bindResult(out, r);
    db().then((d) => d.saveAnswer(question, scope, r)).catch(() => {});
    return r;
  } catch (e) {
    if (!e.offline) { out.innerHTML = errorCard(e.message); return null; }
    // low-internet mode: verified answer saved on this device, else plain text search in a downloaded book
    try {
      const d = await db();
      const saved = await d.getAnswer(question, scope);
      if (saved) { out.innerHTML = resultHtml(saved.result, { offlineSaved: saved.saved_at }); bindResult(out, saved.result); return saved.result; }
      const book = sel.edition_id ? await d.getBook(sel.edition_id) : null;
      if (book && book.verified) {
        const hits = await d.searchBook(sel.edition_id, question);
        out.innerHTML = `<section class="card abstain" id="answer" data-status="offline-search"><h2>ઑફલાઇન</h2>
          <p>${esc(e.message)} ઉત્તર બનાવવા સર્વર જરૂરી છે. નીચે ડાઉનલોડ કરેલા પુસ્તકમાંથી માત્ર <strong>શોધ પરિણામ</strong> છે (ચકાસાયેલો ઉત્તર નથી).</p>
          ${hits.length ? '<ul class="clean">' + hits.map((h) => `<li><a href="#/read/${sel.edition_id}/${h.page_number}">પૃષ્ઠ ${h.page_number}</a> — ${esc(h.snippet)}</li>`).join('') + '</ul>' : '<p>ડાઉનલોડ કરેલા પુસ્તકમાં મેળ મળ્યો નથી.</p>'}</section>`;
        return null;
      }
    } catch (_) { /* fall through */ }
    out.innerHTML = `<div class="card err" id="answer" data-status="offline" role="alert">${esc(e.message)} આ પ્રશ્નનો સંગ્રહિત ઉત્તર આ ઉપકરણ પર નથી. પુસ્તક <a href="#/library">ઑફલાઇન પુસ્તકાલય</a>માં ડાઉનલોડ કરશો તો જોડાણ વિના વાંચી અને શોધી શકશો.</div>`;
    return null;
  }
}

// ---------------------------------------------------------------- views
const views = {};

views.home = async () => {
  await loadCatalog().catch(() => {});
  const about = await api('/api/about').catch(() => null);
  view.innerHTML = `<h1>GRANTH-AI માં સ્વાગત છે</h1>
    <p>તમારું પાઠ્યપુસ્તક પસંદ કરો અને ગુજરાતીમાં પ્રશ્ન પૂછો. ઉત્તર <strong>માત્ર પસંદ કરેલા પાઠ્યપુસ્તકના લખાણમાંથી</strong>, પ્રકરણ અને પૃષ્ઠ ક્રમાંક સાથે મળશે.</p>
    ${selectionSummary()}
    <form id="quick" class="card"><label for="q">ઝડપી પ્રશ્ન</label>
      <textarea id="q" lang="gu" placeholder="દા.ત. પ્રકાશસંશ્લેષણ શું છે?" maxlength="500"></textarea>
      <div class="row"><button class="primary" type="submit">પ્રશ્ન પૂછો</button></div></form>
    <div class="grid">
      <a class="tile" href="#/select"><b>📚 પુસ્તક પસંદગી</b>બોર્ડ → માધ્યમ → ધોરણ → વિષય → પુસ્તક → પ્રકરણ</a>
      <a class="tile" href="#/ask"><b>🎤 📷 ⌨️ પ્રશ્ન પૂછો</b>બોલીને, ફોટો પાડીને કે લખીને</a>
      <a class="tile" href="#/exam"><b>📝 પરીક્ષા તૈયારી</b>ગુણ પ્રમાણે ઉત્તર, પુનરાવર્તન, મહાવરો</a>
      <a class="tile" href="#/dictionary"><b>📖 શબ્દકોશ</b>પાઠ્યપુસ્તકના અઘરા શબ્દો</a>
      <a class="tile" href="#/library"><b>⬇️ ઑફલાઇન પુસ્તકાલય</b>ઇન્ટરનેટ વિના વાંચો</a>
      <a class="tile" href="#/history"><b>🕘 ઇતિહાસ</b>અગાઉ પૂછેલા પ્રશ્નો</a>
    </div>
    ${about ? `<div class="note" id="sample-notice">${esc(about.sample_notice.gu)}</div>` : ''}`;
  $('#quick').onsubmit = (ev) => {
    ev.preventDefault();
    const q = $('#q').value.trim();
    if (!q) return;
    sessionStorage.setItem('granth.pending', q);
    location.hash = '#/ask';
  };
};

views.select = async () => {
  view.innerHTML = loading();
  try { await loadCatalog(); } catch (e) { view.innerHTML = errorCard(e.message); return; }
  const books = catalog.textbooks;
  const uniq = (arr) => [...new Set(arr)];
  const step = (title, key, options, label = (x) => x) => `<h2>${title}</h2><div class="chips" data-step="${key}">${options.map((o) =>
    `<button type="button" class="chip ${String(sel[key]) === String(o) ? 'on' : ''}" data-key="${key}" data-val="${esc(o)}">${esc(label(o))}</button>`).join('') || '<span class="muted">—</span>'}</div>`;
  const f1 = books.filter((b) => !sel.board || b.board === sel.board);
  const f2 = f1.filter((b) => !sel.medium || b.medium === sel.medium);
  const f3 = f2.filter((b) => !sel.standard || b.standard === +sel.standard);
  const f4 = f3.filter((b) => !sel.subject || b.subject === sel.subject);
  let html = `<h1>પાઠ્યપુસ્તક પસંદ કરો</h1>${selectionSummary()}`;
  html += step('1. બોર્ડ', 'board', uniq(books.map((b) => b.board)));
  if (sel.board) html += step('2. માધ્યમ', 'medium', uniq(f1.map((b) => b.medium)));
  if (sel.medium) html += step('3. ધોરણ', 'standard', uniq(f2.map((b) => b.standard)).sort((a, b) => a - b), (s) => `ધોરણ ${s}`);
  if (sel.standard) html += step('4. વિષય', 'subject', uniq(f3.map((b) => b.subject)));
  if (sel.subject) {
    html += `<h2>5. પાઠ્યપુસ્તક અને આવૃત્તિ</h2>`;
    for (const b of f4) {
      html += `<div class="card"><strong>${esc(b.title)}</strong><div class="chips">` + b.editions.map((e) => e.available
        ? `<button type="button" class="chip ed ${sel.edition_id === e.edition_id ? 'on' : ''}" data-ed="${e.edition_id}" data-book="${b.textbook_id}">આવૃત્તિ ${esc(e.edition_label)} · ${e.chapter_count} પ્રકરણ <span class="badge ${sel.edition_id === e.edition_id ? '' : 'ok'}">અધિકૃત</span></button>`
        : `<button type="button" class="chip" disabled title="${esc(catalog.unavailable_message)}">🔒 ${esc(e.edition_label)} — પરવાનગી: ${esc(e.permission_status)}</button>`).join('') + `</div>
        <p class="muted">જુદી જુદી આવૃત્તિઓનું લખાણ ક્યારેય ભેળવવામાં આવતું નથી. એક આવૃત્તિ પસંદ કરો.</p></div>`;
    }
    if (!f4.length) html += `<p class="muted">${esc(catalog.unavailable_message)}</p>`;
  }
  if (sel.edition_id) html += `<h2>6. પ્રકરણ</h2><div id="chapters">${loading()}</div>`;
  view.innerHTML = html;
  const order = ['board', 'medium', 'standard', 'subject'];
  for (const b of $$('.chip[data-key]')) b.onclick = () => {
    const k = b.dataset.key;
    sel[k] = k === 'standard' ? +b.dataset.val : b.dataset.val;
    for (const later of order.slice(order.indexOf(k) + 1)) delete sel[later];
    delete sel.edition_id; delete sel.textbook_id; delete sel.chapter_id; delete sel.chapter_title; delete sel.chapter_number;
    saveSel(); views.select();
  };
  for (const b of $$('.chip.ed')) b.onclick = () => {
    sel.edition_id = +b.dataset.ed; sel.textbook_id = +b.dataset.book;
    delete sel.chapter_id; delete sel.chapter_title; delete sel.chapter_number;
    saveSel(); views.select();
  };
  if (sel.edition_id) {
    try {
      const data = await api(`/api/editions/${sel.edition_id}/chapters`);
      $('#chapters').innerHTML = `<div class="chips"><button type="button" class="chip ch ${!sel.chapter_id ? 'on' : ''}" data-ch="">આખું પુસ્તક</button>` +
        data.chapters.map((c) => `<button type="button" class="chip ch ${sel.chapter_id === c.id ? 'on' : ''}" data-ch="${c.id}" data-no="${c.number}" data-title="${esc(c.title)}">${c.number}. ${esc(c.title)} <span class="muted">(પૃ. ${c.page_start}–${c.page_end})</span></button>`).join('') +
        `</div><div class="row"><a class="btn primary" id="go-ask" href="#/ask">પ્રશ્ન પૂછો →</a><a class="btn" href="#/chapters">પ્રકરણો જુઓ</a></div>`;
      for (const b of $$('.chip.ch')) b.onclick = () => {
        if (b.dataset.ch) { sel.chapter_id = +b.dataset.ch; sel.chapter_title = b.dataset.title; sel.chapter_number = +b.dataset.no; }
        else { delete sel.chapter_id; delete sel.chapter_title; delete sel.chapter_number; }
        saveSel(); views.select();
      };
    } catch (e) { $('#chapters').innerHTML = errorCard(e.message); }
  }
};

function needBook() {
  if (sel.edition_id) return false;
  view.innerHTML = `<h1>પહેલાં પુસ્તક પસંદ કરો</h1>${selectionSummary()}`;
  return true;
}

function questionForm({ withModes = true, examTitle = '' } = {}) {
  return `<form id="askform" class="card" autocomplete="off">
    <label for="question">${examTitle || 'તમારો પ્રશ્ન (ગુજરાતીમાં)'}</label>
    <textarea id="question" lang="gu" maxlength="500" placeholder="દા.ત. પ્રકાશસંશ્લેષણ શું છે?" required></textarea>
    <div class="row">
      <button type="button" id="mic" aria-pressed="false">🎤 બોલીને પૂછો</button>
      <label class="btn" for="camera" style="margin:0;font-weight:400">📷 કૅમેરા</label>
      <input id="camera" type="file" accept="image/*" capture="environment" hidden>
      <label class="btn" for="gallery" style="margin:0;font-weight:400">🖼️ ગૅલેરી</label>
      <input id="gallery" type="file" accept="image/jpeg,image/png,image/webp" hidden>
    </div>
    <p id="input-msg" class="muted" role="status" aria-live="polite"></p>
    <div id="imgpanel" hidden></div>
    ${withModes ? `<div class="two"><div><label for="mode">ઉત્તરનો પ્રકાર</label><select id="mode">${MODES.map(([v, l]) => `<option value="${v}">${l}</option>`).join('')}</select></div>
      <div><label for="marks">ગુણ</label><select id="marks"><option value="">—</option>${[1, 2, 3, 4, 5].map((m) => `<option value="${m}">${m} ગુણ</option>`).join('')}</select></div></div>` : ''}
    <div class="row" style="margin-top:10px"><button class="primary" type="submit" id="submit">પાઠ્યપુસ્તકમાંથી ઉત્તર મેળવો</button></div>
  </form><div id="result" aria-live="polite"></div>`;
}

function bindQuestionForm() {
  const q = $('#question');
  const msg = $('#input-msg');
  let method = 'typed';
  q.addEventListener('input', () => { if (!q.dataset.assisted) method = 'typed'; delete q.dataset.assisted; });

  // --- voice: transcript goes into the editable box; the student must press submit
  const mic = $('#mic');
  const voice = createVoiceInput({
    onTranscript: (text, final) => {
      q.value = text; q.dataset.assisted = '1'; method = 'voice';
      msg.textContent = final ? 'ઓળખાયેલો પ્રશ્ન ઉપર છે. જરૂર હોય તો સુધારો અને પછી “ઉત્તર મેળવો” દબાવો.' : 'સાંભળી રહ્યું છે…';
    },
    onError: (code, text) => { msg.textContent = text; msg.dataset.error = code; },
    onState: (s) => { mic.classList.toggle('listening', s === 'listening'); mic.setAttribute('aria-pressed', String(s === 'listening')); mic.textContent = s === 'listening' ? '⏹ બંધ કરો' : '🎤 બોલીને પૂછો'; },
  });
  if (!voice.supported) mic.title = 'આ બ્રાઉઝરમાં ઉપલબ્ધ નથી';
  mic.onclick = () => { delete msg.dataset.error; if (voice.listening) voice.stop(); else { msg.textContent = 'માઇક્રોફોન શરૂ થઈ રહ્યો છે… (બ્રાઉઝર અવાજ ઓળખવા તેની ઑનલાઇન સેવા વાપરી શકે છે)'; voice.start(); } };

  // --- camera / gallery: on-device OCR, text goes into the editable box
  const panel = $('#imgpanel');
  let bitmap = null;
  let rotation = 0;
  const openImage = async (file) => {
    const ok = imageprep.validateImageFile(file);
    if (!ok.ok) { msg.textContent = ok.message; return; }
    try { bitmap = await createImageBitmap(file); } catch (_) { msg.textContent = 'ચિત્ર ખોલી શકાયું નથી.'; return; }
    rotation = 0;
    panel.hidden = false;
    panel.innerHTML = `<h3>ચિત્રમાંથી પ્રશ્ન</h3><canvas id="preview" class="preview" aria-label="ચિત્રનું પૂર્વદર્શન"></canvas>
      <div class="row"><button type="button" id="rot-l" class="small">⟲ ડાબે ફેરવો</button><button type="button" id="rot-r" class="small">⟳ જમણે ફેરવો</button></div>
      <div class="two">${[['top', 'ઉપરથી કાપો'], ['bottom', 'નીચેથી કાપો'], ['left', 'ડાબેથી કાપો'], ['right', 'જમણેથી કાપો']].map(([k, l]) =>
        `<div><label for="crop-${k}">${l} (%)</label><input type="range" id="crop-${k}" class="crop" data-side="${k}" min="0" max="45" value="0"></div>`).join('')}</div>
      <div class="row"><button type="button" id="run-ocr" class="primary">અક્ષરો વાંચો (OCR)</button><button type="button" id="img-close" class="small">રદ કરો</button></div>
      <p class="muted">ચિત્ર આ ઉપકરણ પર જ વંચાય છે; ક્યાંય મોકલવામાં આવતું નથી. છાપેલા અક્ષરો માટે ચકાસેલું છે; હસ્તાક્ષર માટે ચકાસેલું નથી.</p>`;
    const margins = () => Object.fromEntries($$('.crop', panel).map((i) => [i.dataset.side, +i.value]));
    const draw = () => {
      const c = imageprep.renderToCanvas(bitmap, { rotation, margins: margins(), maxSide: 1600 });
      const p = $('#preview'); p.width = c.width; p.height = c.height; p.getContext('2d').drawImage(c, 0, 0);
      return c;
    };
    draw();
    $('#rot-l').onclick = () => { rotation -= 90; draw(); };
    $('#rot-r').onclick = () => { rotation += 90; draw(); };
    for (const i of $$('.crop', panel)) i.oninput = draw;
    $('#img-close').onclick = () => { panel.hidden = true; panel.innerHTML = ''; };
    $('#run-ocr').onclick = async () => {
      const canvas = draw();
      msg.innerHTML = '<span class="spinner"></span> અક્ષરો વંચાઈ રહ્યા છે… (પહેલી વાર થોડો સમય લાગે)';
      try {
        const text = await runOcr(canvas);
        if (!text) { msg.textContent = 'ચિત્રમાંથી કોઈ લખાણ વાંચી શકાયું નથી. ચિત્ર સ્પષ્ટ કરો અથવા પ્રશ્ન ટાઇપ કરો.'; return; }
        q.value = text; q.dataset.assisted = '1'; method = 'camera';
        msg.textContent = 'વાંચેલું લખાણ ઉપર છે. ભૂલ હોય તો સુધારો અને પછી “ઉત્તર મેળવો” દબાવો.';
        q.focus();
      } catch (e) { msg.textContent = 'OCR ચાલી શક્યું નથી: ' + e.message + ' — પ્રશ્ન ટાઇપ કરો.'; }
    };
  };
  for (const id of ['camera', 'gallery']) $('#' + id).onchange = (ev) => { if (ev.target.files[0]) openImage(ev.target.files[0]); ev.target.value = ''; };

  $('#askform').onsubmit = async (ev) => {
    ev.preventDefault();
    const text = q.value.trim();
    if (!text) return;
    $('#submit').disabled = true;
    await askQuestion(text, { mode: $('#mode') ? $('#mode').value : 'auto', marks: $('#marks') && $('#marks').value ? +$('#marks').value : null, input_method: method }, $('#result'));
    $('#submit').disabled = false;
  };
  return { setQuestion: (t) => { q.value = t; } };
}

let ocrWorker = null;
async function runOcr(canvas) {
  if (!window.Tesseract) {
    await new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = '/vendor/tesseract/tesseract.min.js';
      s.onload = resolve;
      s.onerror = () => reject(new Error('OCR એન્જિન લોડ થયું નથી (vendor files ખૂટે છે અથવા જોડાણ નથી)'));
      document.head.appendChild(s);
    });
  }
  if (!ocrWorker) {
    ocrWorker = await window.Tesseract.createWorker(['guj', 'eng'], 1, { workerPath: '/vendor/tesseract/worker.min.js',
      corePath: '/vendor/tesseract/core', langPath: '/vendor/tessdata', gzip: true, workerBlobURL: false });
  }
  const { data } = await ocrWorker.recognize(canvas);
  return imageprep.cleanOcrText(data.text);
}
window.granthRunOcr = runOcr;      // used by the automated browser test

views.ask = async () => {
  await loadCatalog().catch(() => {});
  if (needBook()) return;
  view.innerHTML = `<h1>પ્રશ્ન પૂછો</h1>${selectionSummary()}${questionForm()}`;
  const form = bindQuestionForm();
  const pending = sessionStorage.getItem('granth.pending');
  if (pending) { sessionStorage.removeItem('granth.pending'); form.setQuestion(pending); $('#askform').requestSubmit(); }
};

views.chapters = async () => {
  await loadCatalog().catch(() => {});
  if (needBook()) return;
  view.innerHTML = `<h1>પ્રકરણો</h1>${selectionSummary()}<div id="list">${loading()}</div>`;
  try {
    const data = await api(`/api/editions/${sel.edition_id}/chapters`);
    $('#list').innerHTML = data.chapters.map((c) => `<div class="card"><h2>પ્રકરણ ${c.number}: ${esc(c.title)}</h2>
      <p class="muted">પૃષ્ઠ ${c.page_start}–${c.page_end}</p>
      <ul>${c.sections.map((s) => `<li>${esc(s.number)} ${esc(s.title)} <a href="#/page/${sel.edition_id}/${s.page_start}">(પૃ. ${s.page_start})</a></li>`).join('')}</ul>
      <div class="row"><button type="button" class="small pick" data-ch="${c.id}" data-no="${c.number}" data-title="${esc(c.title)}" data-go="ask">આ પ્રકરણમાંથી પ્રશ્ન પૂછો</button>
      <button type="button" class="small pick" data-ch="${c.id}" data-no="${c.number}" data-title="${esc(c.title)}" data-go="exam">પુનરાવર્તન / મહાવરો</button>
      <button type="button" class="small pick" data-ch="${c.id}" data-no="${c.number}" data-title="${esc(c.title)}" data-go="dictionary">શબ્દો</button>
      <a class="btn small" href="#/page/${sel.edition_id}/${c.page_start}">વાંચો</a></div></div>`).join('');
    for (const b of $$('.pick')) b.onclick = () => {
      sel.chapter_id = +b.dataset.ch; sel.chapter_number = +b.dataset.no; sel.chapter_title = b.dataset.title; saveSel();
      location.hash = '#/' + b.dataset.go;
    };
  } catch (e) { $('#list').innerHTML = errorCard(e.message); }
};

views.exam = async () => {
  await loadCatalog().catch(() => {});
  if (needBook()) return;
  view.innerHTML = `<h1>પરીક્ષા તૈયારી</h1>${selectionSummary()}
    <div class="card"><div class="two"><div><label for="ex-ch">પ્રકરણ</label><select id="ex-ch"><option value="">આખું પુસ્તક</option></select></div>
      <div><label for="ex-topic">મુદ્દો (વિભાગ)</label><select id="ex-topic"><option value="">—</option></select></div></div>
      <p class="muted">દરેક ઉત્તર પાઠ્યપુસ્તકના લખાણમાંથી જ બને છે. માગેલા ગુણ જેટલું લખાણ પુસ્તકમાં ન હોય તો તે સ્પષ્ટ જણાવાય છે; વધારાના મુદ્દા ઉમેરાતા નથી.</p></div>
    ${questionForm({ examTitle: 'પરીક્ષાનો પ્રશ્ન' })}
    <div class="row"><button type="button" id="btn-rev">📋 પ્રકરણનું પુનરાવર્તન</button><button type="button" id="btn-prac">✍️ મહાવરાના પ્રશ્નો</button></div>
    <div id="study"></div>`;
  const form = bindQuestionForm();
  $('#mode').value = 'short'; $('#marks').value = '2';
  const chSel = $('#ex-ch');
  const topic = $('#ex-topic');
  let chapters = [];
  try {
    chapters = (await api(`/api/editions/${sel.edition_id}/chapters`)).chapters;
    chSel.innerHTML += chapters.map((c) => `<option value="${c.id}" ${sel.chapter_id === c.id ? 'selected' : ''}>${c.number}. ${esc(c.title)}</option>`).join('');
  } catch (e) { $('#study').innerHTML = errorCard(e.message); }
  const fillTopics = () => {
    const c = chapters.find((x) => x.id === +chSel.value);
    topic.innerHTML = '<option value="">—</option>' + (c ? c.sections.map((s) => `<option value="${esc(s.title)}">${esc(s.number)} ${esc(s.title)}</option>`).join('') : '');
  };
  fillTopics();
  chSel.onchange = () => {
    const c = chapters.find((x) => x.id === +chSel.value);
    if (c) { sel.chapter_id = c.id; sel.chapter_number = c.number; sel.chapter_title = c.title; } else { delete sel.chapter_id; delete sel.chapter_title; delete sel.chapter_number; }
    saveSel(); fillTopics(); $('#study').innerHTML = '';
  };
  topic.onchange = () => { if (topic.value) form.setQuestion(topic.value.replace(/\?$/, '') + ' વિશે સમજાવો'); };
  const study = $('#study');
  $('#btn-rev').onclick = async () => {
    if (!sel.chapter_id) { study.innerHTML = '<div class="note">પહેલાં પ્રકરણ પસંદ કરો.</div>'; return; }
    study.innerHTML = loading();
    try {
      const r = await api(`/api/chapters/${sel.chapter_id}/revision`);
      const item = (x) => `<li>${renderText(x.text)}<span class="muted">પૃષ્ઠ <a href="#/page/${sel.edition_id}/${x.page_number}">${x.page_number}</a>${x.section_title ? ' · ' + esc(x.section_title) : ''}</span></li>`;
      const block = (title, arr) => arr.length ? `<h3>${title}</h3><ul class="clean">${arr.map(item).join('')}</ul>` : '';
      study.innerHTML = `<section class="card" id="revision"><h2>પુનરાવર્તન: પ્રકરણ ${r.chapter.number} – ${esc(r.chapter.title)}</h2><p class="note">${esc(r.note)}</p>
        ${block('વ્યાખ્યાઓ', r.definitions)}${block('સૂત્રો', r.formulas)}${block('કોષ્ટકો', r.tables)}${block('ઉદાહરણો', r.examples)}${block('આકૃતિઓ', r.figures)}</section>`;
    } catch (e) { study.innerHTML = errorCard(e.message); }
  };
  $('#btn-prac').onclick = async () => {
    if (!sel.chapter_id) { study.innerHTML = '<div class="note">પહેલાં પ્રકરણ પસંદ કરો.</div>'; return; }
    study.innerHTML = loading();
    try {
      const r = await api(`/api/chapters/${sel.chapter_id}/practice`);
      study.innerHTML = `<section class="card" id="practice"><h2>મહાવરાના પ્રશ્નો</h2><p class="note">${esc(r.disclaimer)}</p>
        <ol>${r.questions.map((q) => `<li><p>${esc(q.question)}</p><details><summary>પાઠ્યપુસ્તકનો ઉત્તર જુઓ</summary>
          ${q.answer ? `<blockquote>${renderText(q.answer)}</blockquote>` : `<p>${esc(q.answer_hint || '')}</p>`}
          <p class="muted">પૃષ્ઠ <a href="#/page/${sel.edition_id}/${q.page_number}">${q.page_number}</a>${q.section_title ? ' · ' + esc(q.section_title) : ''}</p></details></li>`).join('')}</ol></section>`;
    } catch (e) { study.innerHTML = errorCard(e.message); }
  };
};

function wordHtml(w, saved) {
  return `<div class="card word" data-id="${w.id}"><h3>${esc(w.word)} <span class="badge ${w.kind === 'context_only' ? 'warn' : 'ok'}">${esc(w.kind_label)}</span></h3>
    ${w.explanation ? `<p>${esc(w.explanation)}</p>` : '<p class="muted">પાઠ્યપુસ્તકમાં આ શબ્દનો અર્થ આપેલો નથી; GRANTH-AI અર્થ બનાવતું નથી. નીચે માત્ર સંદર્ભ છે.</p>'}
    <blockquote>${esc(w.context)}</blockquote>
    <p class="muted">સ્રોત: પ્રકરણ ${esc(w.chapter_number ?? '')} ${esc(w.chapter_title ?? '')} · પૃષ્ઠ <a href="#/page/${w.edition_id}/${w.page_number}">${w.page_number}</a></p>
    <button type="button" class="small ${saved ? 'unsave' : 'save'}" data-id="${w.id}">${saved ? '✖ સાચવેલામાંથી કાઢો' : '⭐ શબ્દ સાચવો'}</button></div>`;
}

views.dictionary = async () => {
  await loadCatalog().catch(() => {});
  if (needBook()) return;
  view.innerHTML = `<h1>પાઠ્યપુસ્તક શબ્દકોશ</h1>${selectionSummary()}
    <form id="dform" class="card"><label for="dq">શબ્દ શોધો</label><div class="row"><input type="search" id="dq" lang="gu" placeholder="દા.ત. હરિતદ્રવ્ય" style="flex:1"><button class="primary" type="submit">શોધો</button></div>
      <p class="muted">“પાઠ્યપુસ્તકની વ્યાખ્યા” અને “સરળ સમજૂતી” અલગ લેબલ સાથે બતાવાય છે. બંને પાઠ્યપુસ્તકમાંથી જ છે; બહારનો કોઈ શબ્દકોશ વપરાયો નથી.</p></form>
    <div class="row"><button type="button" id="d-chapter">આ પ્રકરણના શબ્દો</button><button type="button" id="d-saved">⭐ સાચવેલા શબ્દો</button></div>
    <div id="dres"></div>`;
  const out = $('#dres');
  const show = (words, saved, empty) => {
    out.innerHTML = words.length ? words.map((w) => wordHtml(w, saved)).join('') : `<div class="card abstain" id="d-empty">${empty}</div>`;
    for (const b of $$('.save', out)) b.onclick = async () => { await api('/api/saved-words', { method: 'POST', body: { vocabulary_id: +b.dataset.id, session_id: session() } }); b.textContent = '✔ સાચવ્યો'; b.disabled = true; };
    for (const b of $$('.unsave', out)) b.onclick = async () => { await api(`/api/saved-words/${b.dataset.id}?session=${encodeURIComponent(session())}`, { method: 'DELETE' }); $('#d-saved').click(); };
  };
  let seq = 0;
  const guard = async (fn) => { const mine = ++seq; out.innerHTML = loading(); try { const args = await fn(); if (mine === seq) show(...args); } catch (e) { if (mine === seq) out.innerHTML = errorCard(e.message); } };
  $('#dform').onsubmit = (ev) => { ev.preventDefault(); const q = $('#dq').value.trim(); if (!q) return;
    guard(async () => [(await api(`/api/vocabulary/search?q=${encodeURIComponent(q)}&edition=${sel.edition_id}`)).words, false, 'આ શબ્દ પસંદ કરેલા પાઠ્યપુસ્તકના શબ્દકોશમાં મળ્યો નથી. GRANTH-AI પોતાની રીતે અર્થ બનાવતું નથી.']); };
  $('#d-chapter').onclick = () => { if (!sel.chapter_id) { out.innerHTML = '<div class="note">પહેલાં <a href="#/chapters">પ્રકરણ પસંદ કરો</a>.</div>'; return; }
    guard(async () => [(await api(`/api/chapters/${sel.chapter_id}/vocabulary`)).words, false, 'આ પ્રકરણમાં શબ્દો મળ્યા નથી.']); };
  $('#d-saved').onclick = () => guard(async () => [(await api(`/api/saved-words?session=${encodeURIComponent(session())}`)).words, true, 'હજી કોઈ શબ્દ સાચવ્યો નથી.']);
  if (sel.chapter_id) $('#d-chapter').click();
};

const fmtBytes = (n) => (n == null ? '—' : n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : `${(n / 1048576).toFixed(1)} MB`);

views.library = async () => {
  view.innerHTML = `<h1>ઑફલાઇન પુસ્તકાલય</h1><div id="lib">${loading()}</div>`;
  const lib = $('#lib');
  let d;
  try { d = await db(); } catch (e) { lib.innerHTML = errorCard('આ બ્રાઉઝરમાં ઑફલાઇન સંગ્રહ ઉપલબ્ધ નથી: ' + e.message); return; }
  await loadCatalog().catch(() => {});
  const render = async (message = '') => {
    const books = await d.listBooks();
    const usage = await d.storageUsage();
    const have = new Set(books.map((b) => b.edition_id));
    let html = message;
    html += `<section class="card" id="storage"><h2>સંગ્રહ</h2><p>ડાઉનલોડ કરેલાં પુસ્તકો: <strong>${usage.books}</strong> · પુસ્તકોનું કદ: <strong id="book-bytes">${fmtBytes(usage.book_bytes)}</strong>
      ${usage.quota ? ` · ઉપકરણ પર વપરાશ: ${fmtBytes(usage.usage)} / ${fmtBytes(usage.quota)}` : ''}</p>
      ${usage.low ? '<p class="note" id="storage-warning">ચેતવણી: ઉપકરણમાં જગ્યા ઓછી છે. નવાં પુસ્તકો ડાઉનલોડ ન થાય તો જૂનાં કાઢી નાખો.</p>' : ''}</section>`;
    html += '<h2>ડાઉનલોડ કરેલાં પુસ્તકો</h2>';
    if (!books.length) html += '<p class="muted" id="no-books">હજી કોઈ પુસ્તક ડાઉનલોડ કર્યું નથી.</p>';
    for (const b of books) {
      const p = await d.getProgress(b.edition_id);
      html += `<div class="card book" data-ed="${b.edition_id}"><h3>${esc(b.edition.title)} <span class="badge ok">✔ ઑફલાઇન ઉપલબ્ધ (ચકાસેલું)</span></h3>
        <p class="muted">ધોરણ ${esc(b.edition.standard)} · ${esc(b.edition.subject)} · આવૃત્તિ ${esc(b.edition.edition_label)} · ${b.page_count} પૃષ્ઠ · ${fmtBytes(b.size_bytes)} · ${esc(b.downloaded_at.slice(0, 10))}</p>
        <div class="bar" title="વાંચન પ્રગતિ"><i style="width:${p.percent}%"></i></div><p class="muted">વાંચન પ્રગતિ: ${p.pages_read}/${p.page_count} પૃષ્ઠ (${p.percent}%)</p>
        <div class="row"><a class="btn primary open" href="#/read/${b.edition_id}/${p.last_page || 1}">${p.last_page ? 'આગળ વાંચો' : 'ખોલો'}</a>
        <button type="button" class="small del" data-ed="${b.edition_id}">🗑 કાઢી નાખો</button></div></div>`;
    }
    html += '<h2>ડાઉનલોડ માટે ઉપલબ્ધ (માત્ર અધિકૃત પુસ્તકો)</h2>';
    if (!catalog) html += '<p class="muted">ઑફલાઇન છો – યાદી લાવી શકાતી નથી. ડાઉનલોડ કરેલાં પુસ્તકો ઉપર ઉપલબ્ધ છે.</p>';
    else for (const b of catalog.textbooks) for (const e of b.editions) {
      html += `<div class="card"><strong>${esc(b.title)}</strong> — ધોરણ ${b.standard}, ${esc(b.subject)}, આવૃત્તિ ${esc(e.edition_label)}
        <div class="row">${!e.available ? `<span class="badge warn">🔒 પરવાનગી: ${esc(e.permission_status)} – ડાઉનલોડ ઉપલબ્ધ નથી</span>`
          : have.has(e.edition_id) ? '<span class="badge ok">ડાઉનલોડ થયેલું</span>'
          : `<button type="button" class="dl" data-ed="${e.edition_id}">⬇️ ડાઉનલોડ કરો (${e.page_count} પૃષ્ઠ)</button>`}</div></div>`;
    }
    lib.innerHTML = html;
    for (const b of $$('.dl', lib)) b.onclick = async () => {
      b.disabled = true; b.innerHTML = '<span class="spinner"></span> ડાઉનલોડ થઈ રહ્યું છે…';
      try {
        const check = await downloadBook(d, +b.dataset.ed);
        await render(`<div class="note" id="dl-ok">ડાઉનલોડ પૂર્ણ અને ચકાસેલું: ${check.pages} પૃષ્ઠ ઉપકરણ પર સંગ્રહિત.</div>`);
      } catch (e) {
        const text = e.code === 'quota' ? 'ઉપકરણમાં પૂરતી જગ્યા નથી. જૂનાં પુસ્તકો કાઢીને ફરી પ્રયત્ન કરો.'
          : e.code === 'network' ? 'જોડાણ નથી – ડાઉનલોડ થયું નથી.' : e.code === 'not-authorized' || e.code === 'refused' ? 'આ પુસ્તક ડાઉનલોડ માટે અધિકૃત નથી.'
          : 'ડાઉનલોડ નિષ્ફળ: પુસ્તક ઉપકરણ પર સંગ્રહિત થયું નથી.';
        await render(`<div class="card err" id="dl-err" role="alert">${text}</div>`);
      }
    };
    for (const b of $$('.del', lib)) b.onclick = async () => {
      if (!confirm('આ પુસ્તક ઉપકરણમાંથી કાઢી નાખવું છે?')) return;
      await d.deleteBook(+b.dataset.ed);
      await render('<div class="note" id="del-ok">પુસ્તક ઉપકરણમાંથી કાઢી નાખ્યું.</div>');
    };
  };
  await render();
};

views.read = async (edition, pageNo) => {
  const id = +edition;
  const n = Math.max(1, +pageNo || 1);
  let d; let book;
  try { d = await db(); book = await d.getBook(id); } catch (_) { book = null; }
  if (!book || !book.verified) { view.innerHTML = `<h1>ઑફલાઇન વાચક</h1><div class="card err" id="not-offline">આ પુસ્તક આ ઉપકરણ પર ડાઉનલોડ થયેલું નથી. <a href="#/library">ઑફલાઇન પુસ્તકાલય</a></div>`; return; }
  let page;
  try { page = await d.getPage(id, n); } catch (_) { view.innerHTML = errorCard('આ પૃષ્ઠ ઉપકરણ પર નથી.'); return; }
  const prog = await d.setProgress(id, n);
  const ch = d.chapterForPage(book, n);
  view.innerHTML = `<h1>${esc(book.edition.title)}</h1>
    <p class="muted"><span class="badge ok" id="offline-badge">ઉપકરણ પરથી (ઑફલાઇન)</span> આવૃત્તિ ${esc(book.edition.edition_label)} · ${ch ? `પ્રકરણ ${ch.number}: ${esc(ch.title)}` : ''}</p>
    <form id="rsearch" class="row"><input type="search" id="rq" lang="gu" placeholder="આ પુસ્તકમાં શોધો" style="flex:1"><button type="submit">શોધો</button></form><div id="rhits"></div>
    <div class="row" style="margin:10px 0"><a class="btn ${n <= 1 ? 'disabled' : ''}" id="prev" href="#/read/${id}/${Math.max(1, n - 1)}">← પાછલું</a>
      <strong id="pageno">પૃષ્ઠ ${n} / ${book.page_count}</strong>
      <a class="btn" id="next" href="#/read/${id}/${Math.min(book.page_count, n + 1)}">આગળનું →</a>
      <select id="jump" aria-label="પ્રકરણ પર જાઓ"><option value="">પ્રકરણ પર જાઓ…</option>${book.chapters.map((c) => `<option value="${c.page_start}">${c.number}. ${esc(c.title)}</option>`).join('')}</select></div>
    <article class="pagebox" id="pagetext" lang="gu">${renderText(page.text)}</article>
    <p class="muted">વાંચન પ્રગતિ: ${prog.pages_read.length}/${book.page_count} પૃષ્ઠ</p>`;
  $('#jump').onchange = (ev) => { if (ev.target.value) location.hash = `#/read/${id}/${ev.target.value}`; };
  $('#rsearch').onsubmit = async (ev) => {
    ev.preventDefault();
    const hits = await d.searchBook(id, $('#rq').value);
    $('#rhits').innerHTML = `<div class="card" id="offline-hits">${hits.length ? '<ul class="clean">' + hits.map((h) => `<li><a href="#/read/${id}/${h.page_number}">પૃષ્ઠ ${h.page_number}</a> — ${esc(h.snippet)}</li>`).join('') + '</ul>' : 'કોઈ મેળ મળ્યો નથી.'}</div>`;
  };
};

views.page = async (edition, pageNo) => {
  view.innerHTML = loading();
  try {
    const p = await api(`/api/editions/${+edition}/pages/${+pageNo}`);
    const n = p.page.page_number;
    view.innerHTML = `<h1>પૃષ્ઠ સંદર્ભ</h1>
      <dl class="src"><dt>પુસ્તક</dt><dd>${esc(p.edition.title)} (${esc(p.edition.edition_label)})</dd><dt>બોર્ડ</dt><dd>${esc(p.edition.board)}</dd>
      <dt>ધોરણ / વિષય</dt><dd>${esc(p.edition.standard)} / ${esc(p.edition.subject)}</dd>
      <dt>પ્રકરણ</dt><dd>${p.chapter ? `${p.chapter.number}: ${esc(p.chapter.title)}` : '—'}</dd><dt>પૃષ્ઠ</dt><dd id="pageno">${n} / ${p.page_count}</dd>
      <dt>નિષ્કર્ષણ</dt><dd>${esc(p.page.extraction_method)} · વિશ્વાસ ${Math.round(p.page.confidence * 100)}%</dd><dt>લાઇસન્સ</dt><dd>${esc(p.edition.license || '')}</dd></dl>
      <div class="row"><a class="btn" href="#/page/${+edition}/${Math.max(1, n - 1)}">← પાછલું</a><a class="btn" href="#/page/${+edition}/${Math.min(p.page_count, n + 1)}">આગળનું →</a><button type="button" id="back">પાછા જાઓ</button></div>
      <article class="pagebox" id="pagetext" lang="gu">${renderText(p.page.text)}</article>`;
    $('#back').onclick = () => history.back();
  } catch (e) {
    view.innerHTML = e.offline ? `<div class="card err">${esc(e.message)} આ પુસ્તક ડાઉનલોડ કરેલું હોય તો <a href="#/read/${+edition}/${+pageNo}">ઑફલાઇન વાચકમાં ખોલો</a>.</div>` : errorCard(e.message);
  }
};

views.history = async () => {
  view.innerHTML = `<h1>પ્રશ્ન ઇતિહાસ</h1><div id="hist">${loading()}</div>`;
  try {
    const { history } = await api(`/api/history?session=${encodeURIComponent(session())}`);
    const label = { answered: ['ok', 'ઉત્તર મળ્યો'], abstained: ['warn', 'આધાર મળ્યો નથી'], edition_conflict: ['bad', 'આવૃત્તિ તફાવત'] };
    const icon = { typed: '⌨️', voice: '🎤', camera: '📷' };
    $('#hist').innerHTML = history.length ? history.map((h, i) => `<details class="card hist"><summary>${icon[h.input_method] || ''} ${esc(h.text)} &nbsp;<span class="badge ${label[h.status][0]}">${label[h.status][1]}</span></summary>
      <p class="muted">${esc(h.created_at.replace('T', ' ').slice(0, 16))} UTC</p><div class="hres" data-i="${i}"></div></details>`).join('') : '<p class="muted" id="no-history">હજી કોઈ પ્રશ્ન પૂછ્યો નથી.</p>';
    for (const el of $$('.hres')) { const r = history[+el.dataset.i].result; el.innerHTML = resultHtml(r); bindResult(el, r); }
  } catch (e) { $('#hist').innerHTML = errorCard(e.message); }
};

views.about = async () => {
  view.innerHTML = loading();
  const [a, st, pv, src] = await Promise.all([api('/api/about').catch(() => null), api('/api/stats').catch(() => null), api('/api/providers').catch(() => null), api('/api/sources').catch(() => null)]);
  view.innerHTML = `<h1>GRANTH-AI વિશે</h1>
    <section class="card" id="credits"><h2>શ્રેય (Credits)</h2>
      <p><strong>વિચાર આપનાર (Idea Contributor):</strong> ભાવેશભાઈ સોલંકી — BHAVESHBHAI SOLANKI</p>
      <p><strong>સ્થાપક અને વિકાસકર્તા (Founder &amp; Developer):</strong> દિવ્યેશ બાંભણિયા — DIVYESH BAMBHANIYA</p>
      <p>ભાવેશભાઈ સોલંકીએ આપેલા શૈક્ષણિક વિચાર પરથી પ્રેરિત અને દિવ્યેશ બાંભણિયા દ્વારા વિકસિત પહેલ. અમારું ધ્યેય ગુજરાતી માધ્યમના વિદ્યાર્થીઓ સુધી પાઠ્યપુસ્તક-આધારિત ચકાસાયેલું જ્ઞાન પહોંચાડવાનું છે.</p>
      <p class="muted">An initiative conceptualized from an educational idea shared by Bhaveshbhai Solanki and developed and engineered by Divyesh Bambhaniya. Our mission is to make verified textbook-based knowledge accessible to Gujarati-medium students.</p></section>
    <section class="card"><h2>નીતિ</h2><p>${esc(a ? a.policy.gu : '')}</p><p class="note">${esc(a ? a.sample_notice.gu : '')}</p>
      <p class="muted">સંસ્કરણ ${esc(a ? a.version : '')} · ઉત્તર એન્જિન ${esc(a ? a.engine_version : '')}</p></section>
    ${src ? `<section class="card"><h2>સ્રોત અને પરવાનગી</h2><ul class="clean">${src.sources.map((s) => `<li><strong>${esc(s.name)}</strong> — પરવાનગી: <span class="badge ${s.permission_status === 'AUTHORIZED' ? 'ok' : s.permission_status === 'PROHIBITED' ? 'bad' : 'warn'}">${esc(s.permission_status)}</span><br><span class="muted">${esc(s.permission_notes || '')}</span></li>`).join('')}</ul></section>` : ''}
    ${st ? `<section class="card" id="stats"><h2>ખર્ચ અને વપરાશ</h2><dl class="src"><dt>બાહ્ય AI API કૉલ</dt><dd>${st.external_api_calls}</dd><dt>સ્થાનિક શોધ</dt><dd>${st.local_retrievals}</dd>
      <dt>Cache hit / miss</dt><dd>${st.cache.hits} / ${st.cache.misses}${st.cache.hit_rate != null ? ` (${Math.round(st.cache.hit_rate * 100)}%)` : ''}</dd>
      <dt>સરેરાશ સમય</dt><dd>${st.latency_ms.avg ?? '—'} ms</dd><dt>ડેટાબેઝ</dt><dd>${fmtBytes(st.storage.database_bytes)}</dd></dl></section>` : ''}
    ${pv ? `<section class="card"><h2>AI પ્રદાતા</h2><p>જનરેટિવ AI: <strong>${pv.generative_enabled ? 'ચાલુ' : 'બંધ (માત્ર પાઠ્યપુસ્તકમાંથી શબ્દશઃ ઉત્તર)'}</strong></p>
      <ul>${pv.providers.map((p) => `<li>${esc(p.name)} — ${p.configured ? 'ગોઠવેલું' : 'ગોઠવેલું નથી'}${p.external ? ' (બાહ્ય)' : ' (સ્થાનિક)'}</li>`).join('')}</ul></section>` : ''}`;
};

views.admin = async () => {
  const token = sessionStorage.getItem('granth.admin') || '';
  view.innerHTML = `<h1>સંચાલક: સ્રોત સમીક્ષા</h1>
    <form id="aform" class="card"><label for="tok">સંચાલક ટોકન</label><div class="row"><input type="password" id="tok" value="${esc(token)}" autocomplete="off" style="flex:1"><button class="primary" type="submit">ખોલો</button></div>
    <p class="muted">ટોકન માત્ર આ ટૅબમાં રહે છે. સર્વર પર GRANTH_ADMIN_TOKEN ગોઠવેલું ન હોય તો સંચાલન બંધ રહે છે.</p></form><div id="admin"></div>`;
  const out = $('#admin');
  const load = async () => {
    const tok = $('#tok').value;
    sessionStorage.setItem('granth.admin', tok);
    out.innerHTML = loading();
    const h = { 'X-Admin-Token': tok };
    try {
      const [eds, fb] = await Promise.all([api('/api/admin/editions', { headers: h }), api('/api/admin/feedback', { headers: h })]);
      out.innerHTML = '<h2>આવૃત્તિઓ</h2>' + eds.editions.map((e) => `<div class="card"><strong>${esc(e.title)}</strong> — ${esc(e.edition_label)}<br>
        પરવાનગી: <span class="badge">${esc(e.permission_status)}</span> સમીક્ષા: <span class="badge">${esc(e.review_status)}</span> corpus v${e.corpus_version} · ${e.page_count} પૃષ્ઠ
        <br><span class="muted">${e.quality.map((q) => `${esc(q.method)}: ${q.pages} પૃષ્ઠ, સરેરાશ ગુણવત્તા ${q.avg_score}${q.avg_engine_confidence ? `, OCR વિશ્વાસ ${q.avg_engine_confidence}` : ''}`).join(' · ') || 'ingest થયું નથી'}</span>
        <div class="row">${['approved', 'rejected', 'pending'].map((d) => `<button type="button" class="small rev" data-ed="${e.id}" data-d="${d}">${d}</button>`).join('')}</div></div>`).join('') +
        '<h2>વિદ્યાર્થીઓના પ્રતિભાવ</h2>' + (fb.feedback.length ? '<ul class="clean">' + fb.feedback.map((f) => `<li><span class="badge warn">${esc(f.kind)}</span> ${esc(f.question || '')} <span class="muted">${esc(f.created_at.slice(0, 16))}</span></li>`).join('') + '</ul>' : '<p class="muted">કોઈ પ્રતિભાવ નથી.</p>');
      for (const b of $$('.rev', out)) b.onclick = async () => {
        try { await api(`/api/admin/editions/${b.dataset.ed}/review`, { method: 'POST', headers: h, body: { decision: b.dataset.d } }); load(); } catch (e) { alert(e.message); }
      };
    } catch (e) { out.innerHTML = errorCard(e.message); }
  };
  $('#aform').onsubmit = (ev) => { ev.preventDefault(); load(); };
};

// ---------------------------------------------------------------- router
async function route() {
  const parts = location.hash.replace(/^#\/?/, '').split('/').filter(Boolean);
  const name = parts[0] || 'home';
  const fn = views[name] || views.home;
  for (const a of $$('.tabs a')) a.classList.toggle('on', a.dataset.tab === name);
  try { await fn(...parts.slice(1)); } catch (e) { view.innerHTML = errorCard(e.message || String(e)); }
  view.dataset.view = name;
  view.dataset.ready = String(Date.now());
}
function net() {
  const el = document.getElementById('net');
  el.textContent = navigator.onLine ? 'ઑનલાઇન' : 'ઑફલાઇન';
  el.classList.toggle('off', !navigator.onLine);
}
window.addEventListener('hashchange', route);
window.addEventListener('online', net);
window.addEventListener('offline', net);
net();
route();
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
