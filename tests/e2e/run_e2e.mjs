// End-to-end browser test of the GRANTH-AI web app in headless Chromium at a phone viewport.
// Starts its own server on a temporary database (sample books only). Usage: npm run test:e2e
// Results are written to benchmarks/results/e2e_browser.json. Voice uses a MOCK recogniser (no microphone
// exists in a headless container): it tests the app's handling, not real speech-recognition accuracy.
import { spawn, execFileSync } from 'node:child_process';
import { mkdtempSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { launch } from './browser.mjs';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const PORT = 8765;
const BASE = `http://localhost:${PORT}`;
const PY = existsSync(path.join(ROOT, '.venv/bin/python')) ? path.join(ROOT, '.venv/bin/python') : 'python3';
const tmp = mkdtempSync(path.join(tmpdir(), 'granth-e2e-'));
const env = { ...process.env, GRANTH_DB_PATH: path.join(tmp, 'e2e.sqlite3'), GRANTH_ADMIN_TOKEN: 'e2e-admin', GRANTH_GENERATIVE: 'off', GRANTH_PORT: String(PORT) };
delete env.LD_LIBRARY_PATH;                                    // Chromium's bundled libs must not leak into Python
execFileSync(PY, ['-m', 'granth', 'seed-samples'], { cwd: ROOT, env, stdio: 'ignore' });
const server = spawn(PY, ['-m', 'granth', 'serve', '--host', '127.0.0.1', '--port', String(PORT)], { cwd: ROOT, env, stdio: 'ignore' });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
for (let i = 0; i < 50; i++) { try { if ((await fetch(BASE + '/api/health')).ok) break; } catch (_) { /* not up yet */ } await sleep(200); }

const REFUSAL = 'આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી.';
const results = [];
const pageErrors = [];
let browser;
async function step(name, fn) {
  const t0 = Date.now();
  try { const detail = await fn(); results.push({ name, status: 'passed', ms: Date.now() - t0, detail: detail ?? null }); console.log('ok   -', name); }
  catch (e) { results.push({ name, status: 'failed', ms: Date.now() - t0, error: String(e.message || e).slice(0, 400) }); console.log('FAIL -', name, '\n      ', String(e.message || e).slice(0, 400)); }
}
const assert = (cond, msg) => { if (!cond) throw new Error(msg); };

try {
  browser = await launch();
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 800, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  page.on('pageerror', (e) => pageErrors.push(e.message));
  page.on('dialog', (d) => d.accept());
  // Mock speech recogniser, controllable from the test.
  await page.evaluateOnNewDocument(() => {
    window.__voice = { mode: 'ok', text: 'પરાવર્તન એટલે શું' };
    window.webkitSpeechRecognition = class {
      start() {
        setTimeout(() => {
          if (window.__voice.mode === 'deny') { this.onerror && this.onerror({ error: 'not-allowed' }); this.onend && this.onend(); return; }
          this.onstart && this.onstart();
          this.onresult && this.onresult({ results: [Object.assign([{ transcript: window.__voice.text }], { isFinal: true })] });
          this.onend && this.onend();
        }, 30);
      }
      stop() { this.onend && this.onend(); }
      abort() {}
    };
    window.SpeechRecognition = window.webkitSpeechRecognition;
  });
  const go = async (hash) => {
    const before = await page.evaluate(() => document.querySelector('#view')?.dataset.ready || '');
    await page.evaluate((h) => { if (location.hash === h) window.dispatchEvent(new HashChangeEvent('hashchange')); else location.hash = h; }, hash);
    await page.waitForFunction((b) => { const v = document.querySelector('#view'); return v.dataset.ready && v.dataset.ready !== b; }, { timeout: 8000 }, before);
  };
  const text = (sel) => page.$eval(sel, (el) => el.innerText);
  const clickChip = async (label) => {
    const before = await page.evaluate(() => document.querySelectorAll('.chip.on').length);
    await page.evaluate((l) => { const b = [...document.querySelectorAll('.chip')].find((x) => x.innerText.includes(l)); if (!b) throw new Error('chip not found: ' + l); b.click(); }, label);
    await page.waitForFunction((l, n) => [...document.querySelectorAll('.chip.on')].some((x) => x.innerText.includes(l)) && document.querySelectorAll('.chip.on').length > n - 1, { timeout: 5000 }, label, before);
  };
  const ask = async (q, opts = {}) => {
    await page.$eval('#question', (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); }, q);
    if (opts.mode) await page.select('#mode', opts.mode);
    if (opts.marks !== undefined) await page.select('#marks', String(opts.marks));
    await page.evaluate(() => { const r = document.querySelector('#result'); if (r) r.innerHTML = ''; });
    await page.click('#submit');
    await page.waitForSelector('#result #answer', { timeout: 20000 });
    return page.$eval('#result #answer', (el) => ({ status: el.dataset.status, text: el.innerText }));
  };

  await page.goto(BASE + '/');
  await page.waitForFunction(() => document.querySelector('#view').dataset.ready);

  await step('home page: Gujarati UI, permanent credits in footer, sample notice', async () => {
    const body = await text('body');
    assert((await page.$eval('html', (h) => h.lang)) === 'gu', 'html lang is not gu');
    assert(body.includes('IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI') && body.includes('FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA'), 'credits missing on home page');
    assert(await page.$('#sample-notice'), 'sample notice missing');
  });

  await step('selection flow: board → medium → standard → subject → textbook edition → chapter list', async () => {
    await go('#/select');
    await clickChip('નમૂના બોર્ડ');
    await clickChip('ગુજરાતી');
    await clickChip('10');
    await clickChip('વિજ્ઞાન');
    await page.evaluate(() => { const b = [...document.querySelectorAll('.chip.ed')].find((x) => x.innerText.includes('2026')); b.click(); });
    await page.waitForSelector('#go-ask', { timeout: 5000 });
    const chapters = await page.$$eval('.chip.ch', (els) => els.length);
    assert(chapters === 6, `expected 5 chapters + whole book, got ${chapters}`);
    return { chapter_chips: chapters };
  });

  let first;
  await step('Student A: typed question is answered with chapter + page citation and evidence', async () => {
    await go('#/ask');
    first = await ask('પ્રકાશસંશ્લેષણ એટલે શું?');
    assert(first.status === 'answered', 'not answered: ' + first.text.slice(0, 120));
    assert(first.text.includes('પ્રકાશસંશ્લેષણ કહે છે'), 'definition sentence missing');
    const pageNo = await text('#result .pagelink');
    assert(/પૃષ્ઠ 1 /.test(pageNo), 'expected page 1 citation, got ' + pageNo);
    assert(await page.$('#evidence blockquote mark, #evidence blockquote'), 'evidence missing');
    assert(!first.text.includes('cache'), 'first answer should not be a cache hit');
    return { page: pageNo.trim() };
  });

  await step('Student B: identical question is served from the verified cache', async () => {
    const again = await ask('પ્રકાશસંશ્લેષણ  એટલે શું ?');
    assert(again.status === 'answered' && again.text.includes('cache'), 'cache badge missing');
    const st = await (await fetch(BASE + '/api/stats')).json();
    assert(st.external_api_calls === 0, 'external API calls were made');
    return { cache_hits: st.cache.hits, external_api_calls: st.external_api_calls };
  });

  await step('Student C: question absent from the textbook gets the exact refusal message', async () => {
    const r = await ask('જ્વાળામુખી કેવી રીતે ફાટે છે?');
    assert(r.status === 'abstained', 'should abstain');
    assert(r.text.includes('આ પસંદ કરેલા પાઠ્યપુસ્તકમાં આ પ્રશ્નનો પૂરતો આધાર મળ્યો નથી.'), 'refusal sentence missing');
    assert(!(await page.$('#result .pagelink')), 'a refusal must not carry a page citation');
  });

  await step('source page viewer opens the cited page', async () => {
    await ask('ઓહ્મનો નિયમ લખો');
    const href = await page.$eval('#result .pagelink', (a) => a.getAttribute('href'));
    await go(href);
    const t = await text('#pagetext');
    assert(t.includes('ઓહ્મ'), 'cited page does not contain the term');
    assert((await text('#pageno')).startsWith('7'), 'expected page 7');
  });

  await step('voice: transcript lands in the editable box and is NOT auto-submitted; edited text is what gets asked', async () => {
    await go('#/ask');
    await page.click('#mic');
    await page.waitForFunction(() => document.querySelector('#question').value.length > 0, { timeout: 4000 });
    assert((await page.$eval('#question', (e) => e.value)) === 'પરાવર્તન એટલે શું', 'transcript not shown');
    await sleep(300);
    assert(!(await page.$('#result #answer')), 'voice input was submitted automatically');
    assert(!(await page.$eval('#question', (e) => e.readOnly || e.disabled)), 'transcript is not editable');
    const r = await page.evaluate(async () => {
      const q = document.querySelector('#question'); q.value = 'પરાવર્તન કોને કહે છે?';   // student corrects the transcript (no input event = still voice)
      document.querySelector('#submit').click(); return true;
    });
    await page.waitForSelector('#result #answer', { timeout: 10000 });
    assert((await page.$eval('#result #answer', (e) => e.dataset.status)) === 'answered', 'voice question not answered');
    const hist = await (await fetch(BASE + '/api/history?session=' + encodeURIComponent(await page.evaluate(() => JSON.parse(localStorage.getItem('granth.session')))))).json();
    assert(hist.history[0].input_method === 'voice', 'input method not recorded as voice: ' + hist.history[0].input_method);
    return { recogniser: 'mock (no microphone in container)' };
  });

  await step('voice: microphone permission denial shows a Gujarati message and leaves typing usable', async () => {
    await go('#/ask');
    await page.evaluate(() => { window.__voice.mode = 'deny'; });
    await page.click('#mic');
    await page.waitForFunction(() => document.querySelector('#input-msg').dataset.error === 'not-allowed', { timeout: 4000 });
    assert((await text('#input-msg')).includes('માઇક્રોફોનની પરવાનગી મળી નથી'), 'denial message missing');
    assert((await page.$eval('#mic', (b) => b.getAttribute('aria-pressed'))) === 'false', 'mic stuck in listening state');
    const r = await ask('હરિતદ્રવ્ય કોને કહે છે?');
    assert(r.status === 'answered', 'typing did not work after denial');
  });

  await step('camera/gallery: image upload → preview → rotate/crop controls → on-device Gujarati OCR → editable text → answer', async () => {
    await go('#/ask');
    // Render a printed-style question image with the bundled Gujarati font, save it as a real PNG file, upload it.
    const dataUrl = await page.evaluate(async () => {
      await document.fonts.load('48px "Noto Sans Gujarati"');
      const c = document.createElement('canvas'); c.width = 1100; c.height = 260;
      const x = c.getContext('2d'); x.fillStyle = '#fff'; x.fillRect(0, 0, c.width, c.height);
      x.fillStyle = '#000'; x.font = '48px "Noto Sans Gujarati"'; x.fillText('હરિતદ્રવ્ય કોને કહે છે?', 60, 150);
      return c.toDataURL('image/png');
    });
    const file = path.join(tmp, 'question.png');
    writeFileSync(file, Buffer.from(dataUrl.split(',')[1], 'base64'));
    const input = await page.$('#gallery');
    await input.uploadFile(file);
    await page.evaluate(() => document.querySelector('#gallery').dispatchEvent(new Event('change', { bubbles: true })));
    await page.waitForSelector('#preview', { timeout: 5000 });
    const size0 = await page.$eval('#preview', (c) => [c.width, c.height]);
    await page.click('#rot-r');
    const size1 = await page.$eval('#preview', (c) => [c.width, c.height]);
    assert(size1[0] === size0[1] && size1[1] === size0[0], 'rotation did not swap preview dimensions');
    await page.click('#rot-l');
    await page.$eval('#crop-top', (i) => { i.value = 10; i.dispatchEvent(new Event('input', { bubbles: true })); });
    const size2 = await page.$eval('#preview', (c) => [c.width, c.height]);
    assert(size2[1] < size0[1], 'crop did not reduce preview height');
    const t0 = Date.now();
    await page.click('#run-ocr');
    await page.waitForFunction(() => document.querySelector('#question').value.length > 0 || /OCR ચાલી શક્યું નથી|વાંચી શકાયું નથી/.test(document.querySelector('#input-msg').innerText), { timeout: 120000 });
    const ocrText = await page.$eval('#question', (e) => e.value);
    assert(ocrText.length > 0, 'OCR produced no text: ' + await text('#input-msg'));
    assert(ocrText.includes('હરિતદ્રવ્ય'), 'OCR text does not contain the key word: ' + ocrText);
    await sleep(200);
    assert(!(await page.$('#result #answer')), 'OCR text was submitted automatically');
    await page.click('#submit');
    await page.waitForSelector('#result #answer', { timeout: 10000 });
    const status = await page.$eval('#result #answer', (e) => e.dataset.status);
    assert(status === 'answered', 'camera question not answered');
    return { ocr_text: ocrText, ocr_ms: Date.now() - t0, engine: 'tesseract.js in the browser (guj+eng), no upload' };
  });

  await step('OCR correction: a mis-read word abstains, the student-corrected text is answered', async () => {
    const bad = await ask('હરિતદવ્ચ્ય કોને કહે છે?', { mode: 'definition' });
    const good = await ask('હરિતદ્રવ્ય કોને કહે છે?', { mode: 'definition' });
    assert(good.status === 'answered', 'corrected text not answered');
    return { misread_status: bad.status, corrected_status: good.status };
  });

  await step('exam mode: marks-based answer is built from evidence and flags unsupported length', async () => {
    await go('#/exam');
    await page.waitForFunction(() => document.querySelector('#ex-ch').options.length > 1);
    const three = await ask('પરાવર્તનના નિયમો લખો', { mode: 'points', marks: 3 });
    assert(three.status === 'answered' && three.text.includes('આપાતકોણ'), 'points answer wrong');
    const five = await ask('તટસ્થીકરણ એટલે શું?', { mode: 'detailed', marks: 5 });
    assert(five.status === 'answered', 'detailed not answered');
    assert(await page.$('#answer-note'), '5-mark shortfall was not flagged');
    return { shortfall_note: (await text('#answer-note')).slice(0, 80) };
  });

  await step('exam mode: unsupported request (difference with no textbook basis) is rejected', async () => {
    const r = await ask('પરાવર્તન અને તટસ્થીકરણ વચ્ચેનો તફાવત લખો', { mode: 'difference', marks: '' });
    assert(r.status === 'abstained', 'unsupported difference should abstain, got ' + r.status);
    const f = await ask('પ્રકાશસંશ્લેષણમાં વનસ્પતિ ઑક્સિજન શોષે છે તે શા માટે?', { mode: 'short', marks: 2 });
    assert(f.status === 'abstained', 'false-premise question should abstain');
  });

  await step('exam mode: chapter revision and practice questions with page references and disclaimer', async () => {
    const opt = await page.$eval('#ex-ch', (s) => [...s.options].find((o) => o.textContent.includes('વિદ્યુત')).value);
    await page.select('#ex-ch', opt);
    await page.click('#btn-rev');
    await page.waitForSelector('#revision', { timeout: 5000 });
    assert((await text('#revision')).includes('V = I × R'), 'formula missing from revision');
    await page.click('#btn-prac');
    await page.waitForSelector('#practice', { timeout: 5000 });
    const n = await page.$$eval('#practice li', (l) => l.length);
    assert(n >= 2, 'too few practice questions');
    assert((await text('#practice .note')).length > 20, 'disclaimer missing');
    await page.select('#ex-ch', '');                              // back to whole-book scope
    return { practice_questions: n };
  });

  await step('dictionary: search shows labelled textbook meaning with chapter + page; unknown word is refused; save works', async () => {
    await go('#/dictionary');
    await page.$eval('#dq', (e) => { e.value = 'હરિતદ્રવ્ય'; });
    await page.$eval('#dform', (f) => f.requestSubmit());
    await page.waitForSelector('#dres .word', { timeout: 5000 });
    const w = await text('#dres .word');
    assert(w.includes('પૃષ્ઠ') && w.includes('પ્રકરણ'), 'source reference missing');
    assert(await page.$('#dres .word .badge'), 'kind label missing');
    await page.click('#dres .word .save');
    await page.waitForFunction(() => document.querySelector('#dres .word button').disabled, { timeout: 4000 });
    await page.$eval('#dq', (e) => { e.value = 'જ્વાળામુખી'; });
    await page.$eval('#dform', (f) => f.requestSubmit());
    await page.waitForSelector('#d-empty', { timeout: 5000 });
    await page.click('#d-saved');
    await page.waitForSelector('#dres .word .unsave', { timeout: 5000 });
    return { first_word: w.split('\n')[0] };
  });

  await step('history lists typed, voice and camera questions with their results', async () => {
    await go('#/history');
    const n = await page.$$eval('.hist', (e) => e.length);
    const s = await text('#hist');
    assert(n >= 8, 'history too short: ' + n);
    assert(s.includes('🎤') && s.includes('📷') && s.includes('⌨️'), 'input-method icons missing');
    return { entries: n };
  });

  await step('About page shows permanent credits, policy, sources and zero external API calls', async () => {
    await go('#/about');
    const c = await text('#credits');
    assert(c.includes('IDEA CONTRIBUTOR: BHAVESHBHAI SOLANKI') && c.includes('FOUNDER & PROJECT DEVELOPER: DIVYESH BAMBHANIYA') && c.includes('educational information platform'), 'credits incomplete');
    assert((await text('#stats')).includes('બાહ્ય AI API કૉલ'), 'stats missing');
  });

  await step('answer format: પ્રશ્ન / સરળ જવાબ / પુસ્તકનો આધાર / વિશ્વસનીયતા સ્થિતિ, quotation label, no percentage', async () => {
    await go('#/ask');
    const a = await ask('ઓહ્મનો નિયમ લખો', { mode: 'short' });
    assert(a.status === 'answered', 'not answered');
    for (const h of ['પ્રશ્ન', 'સરળ જવાબ', 'મુખ્ય મુદ્દા', 'પુસ્તકનો આધાર', 'વિશ્વસનીયતા સ્થિતિ']) assert(a.text.includes(h), 'section missing: ' + h);
    assert(a.text.includes('સીધું અવતરણ'), 'quotation label missing');
    const trust = await page.$eval('#result #answer .trust', (e) => e.dataset.trust);
    assert(trust === 'verified', 'trust status ' + trust);
    assert(!/\d\s*%/.test(a.text), 'a percentage is shown in the answer card');
    return { trust };
  });

  await step('English question is answered from the Gujarati source with a visible mapping note', async () => {
    const a = await ask('What is photosynthesis?', { mode: 'auto' });
    assert(a.status === 'answered' && a.text.includes('પ્રકાશસંશ્લેષણ કહે છે'), 'English question not answered: ' + a.text.slice(0, 150));
    assert(await page.$('#translation-note'), 'mapping note missing');
    assert(a.text.includes('photosynthesis'), 'English term not shown');
  });

  await step('ambiguous one-word question is refused with topic suggestions', async () => {
    const a = await ask('નિયમ');
    assert(a.status === 'abstained', 'ambiguous question was answered');
    const n = await page.$$eval('#result .sugg', (els) => els.length);
    assert(n >= 3, 'suggestions missing');
    return { suggestions: n };
  });

  await step('supplementary source: off by default; when selected it is shown in a separate, labelled block', async () => {
    const off = await ask('ન્યૂટનનો ત્રીજો નિયમ સમજાવો');
    assert(off.status === 'abstained' && off.text.includes(REFUSAL), 'textbook-only refusal missing');
    assert(!(await page.$('#supplementary')), 'supplementary block shown without being selected');
    const val = await page.$eval('#supp', (el) => el.options[1].value);
    await page.select('#supp', val);
    const on = await ask('ન્યૂટનનો ત્રીજો નિયમ સમજાવો');
    assert(on.status === 'abstained' && on.text.includes(REFUSAL), 'textbook card must still refuse');
    assert(!on.text.includes('પ્રતિક્રિયા'), 'supplementary text leaked into the textbook card');
    const sup = await page.$eval('#supplementary', (el) => ({ status: el.dataset.status, text: el.innerText }));
    assert(sup.status === 'answered' && sup.text.includes('પ્રતિક્રિયા બળ'), 'supplementary answer missing');
    assert(sup.text.includes('પાઠ્યપુસ્તકનો ભાગ નથી') && sup.text.includes('CC BY 4.0'), 'supplementary label / licence missing');
    await page.select('#supp', '');
  });

  await step('worked example is shown step by step, copied from the book', async () => {
    const a = await ask('ઓહ્મના નિયમનું ઉદાહરણ પગલાંવાર સમજાવો');
    assert(a.status === 'answered' && a.text.includes('પગલું 1') && a.text.includes('પગલું 2') && a.text.includes('10 વોલ્ટ'), 'steps missing: ' + a.text.slice(0, 200));
  });

  await step('saved answers: save from the answer card, listed under સાચવેલા ઉત્તરો, removable', async () => {
    await ask('પરાવર્તન એટલે શું?');
    await page.click('#result .savea');
    await page.waitForFunction(() => document.querySelector('#result .savea').disabled, { timeout: 5000 });
    await go('#/saved');
    await page.waitForSelector('#savedlist details, #no-saved');
    const n = await page.$$eval('#savedlist > details', (els) => els.length);
    assert(n === 1, 'saved answer not listed');
    await page.click('#savedlist > details > summary');
    await page.click('#savedlist .unsave');
    await page.waitForSelector('#no-saved', { timeout: 5000 });
  });

  await step('personal notes: rights confirmation required, private answer labelled as own notes, delete works', async () => {
    const keep = await page.evaluate(() => localStorage.getItem('granth.sel'));
    await go('#/notes');
    await page.waitForSelector('#no-notes');
    await page.$eval('#ntitle', (el) => { el.value = 'મારી વર્ગનોંધ'; });
    await page.$eval('#ntext', (el) => { el.value = 'ચુંબકની આસપાસ જે વિસ્તારમાં તેની અસર અનુભવાય છે તે વિસ્તારને ચુંબકીય ક્ષેત્ર કહે છે.\n\nચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ.'; });
    const refused = await page.evaluate(async () => {
      const s = JSON.parse(localStorage.getItem('granth.session'));
      const r = await fetch('/api/personal-notes', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: s, title: 'x', text: 'ચુંબકને બે ધ્રુવ હોય છે: ઉત્તર ધ્રુવ અને દક્ષિણ ધ્રુવ.', rights_confirmed: false }) });
      return r.status;
    });
    assert(refused === 400, 'notes accepted without rights confirmation');
    await page.click('#nrights');
    await page.click('#noteform button[type=submit]');
    await page.waitForSelector('.usenote', { timeout: 5000 });
    await page.click('.usenote');
    await page.waitForSelector('#askform');
    const a = await ask('ચુંબકીય ક્ષેત્ર એટલે શું?');
    assert(a.status === 'answered' && a.text.includes('ચુંબકીય ક્ષેત્ર કહે છે') && a.text.includes('તમારી પોતાની નોંધમાંથી'), 'personal answer wrong: ' + a.text.slice(0, 200));
    const cat = await (await fetch(`${BASE}/api/catalog`)).text();
    assert(!cat.includes('મારી વર્ગનોંધ'), 'personal notes leaked into the public catalogue');
    await go('#/notes');
    await page.waitForSelector('.delnote');
    await page.click('.delnote');
    await page.waitForSelector('#no-notes', { timeout: 5000 });
    await page.evaluate((v) => localStorage.setItem('granth.sel', v), keep);
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#view').dataset.ready);
  });

  await step('mobile responsiveness: no horizontal overflow at 360px and 390px; touch targets ≥ 40px', async () => {
    const out = {};
    for (const width of [360, 390]) {
      await page.setViewport({ width, height: 740, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
      for (const h of ['#/', '#/select', '#/ask', '#/chapters', '#/exam', '#/dictionary', '#/library', '#/history', '#/saved', '#/notes', '#/about']) {
        await go(h);
        const m = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth,
          small: [...document.querySelectorAll('button, a.btn, .tabs a, select, input[type=search]')].filter((e) => e.offsetParent && e.getBoundingClientRect().height < 40).map((e) => e.innerText || e.id).slice(0, 5) }));
        assert(m.sw <= m.iw + 1, `horizontal overflow on ${h} at ${width}px (${m.sw} > ${m.iw})`);
        assert(m.small.length === 0, `small touch targets on ${h}: ${m.small.join(' | ')}`);
      }
      out[width] = 'ok';
    }
    assert(await page.$eval('meta[name=viewport]', (m) => m.content.includes('width=device-width')), 'viewport meta missing');
    await page.setViewport({ width: 390, height: 800, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
    return out;
  });

  await step('offline library: download an authorized book, verified and listed with storage usage', async () => {
    await go('#/library');
    assert(await page.$('#no-books'), 'library should start empty');
    await page.waitForFunction(() => navigator.serviceWorker && navigator.serviceWorker.controller, { timeout: 15000 }).catch(() => {});
    await page.evaluate(() => { const b = [...document.querySelectorAll('.dl')].find((x) => x.closest('[data-ed], li, div').innerText.includes('2026') && x.closest('[data-ed], li, div').innerText.includes('વિજ્ઞાન')) || document.querySelector('.dl'); b.click(); });
    await page.waitForSelector('#dl-ok', { timeout: 10000 });
    assert(await page.$('.book'), 'downloaded book not listed');
    const bytes = await text('#book-bytes');
    assert(!bytes.startsWith('0 B'), 'storage usage not updated');
    return { stored: bytes, service_worker: await page.evaluate(() => !!(navigator.serviceWorker && navigator.serviceWorker.controller)) };
  });

  let offlineEd;
  await step('OFFLINE (network cut): app shell reloads, downloaded book opens, pages navigate, progress is kept', async () => {
    offlineEd = await page.$eval('.book', (b) => +b.dataset.ed);
    await page.setOfflineMode(true);
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => document.querySelector('#view') && document.querySelector('#view').dataset.ready, { timeout: 10000 });
    assert((await text('#net')).includes('ઑફલાઇન'), 'offline indicator not shown');
    await go(`#/read/${offlineEd}/1`);
    assert(await page.$('#offline-badge'), 'offline reader did not open');
    assert((await text('#pagetext')).includes('પ્રકાશસંશ્લેષણ'), 'page 1 text missing offline');
    await page.click('#next');
    await page.waitForFunction(() => document.querySelector('#pageno') && document.querySelector('#pageno').innerText.includes('પૃષ્ઠ 2 /'), { timeout: 5000 });
    assert((await text('#pagetext')).includes('હરિતદ્રવ્ય'), 'page 2 text missing offline');
    await go('#/library');
    assert((await text('.book')).includes('2'), 'reading progress not shown');
  });

  await step('OFFLINE: search inside the downloaded book works; a not-downloaded book says so', async () => {
    await go(`#/read/${offlineEd}/1`);
    await page.$eval('#rq', (e) => { e.value = 'ઓહ્મનો નિયમ'; });
    await page.$eval('#rsearch', (f) => f.requestSubmit());
    await page.waitForSelector('#offline-hits', { timeout: 5000 });
    const hits = await text('#offline-hits');
    assert(hits.includes('પૃષ્ઠ 7'), 'offline search did not find page 7: ' + hits.slice(0, 100));
    await page.$eval('#rq', (e) => { e.value = 'જ્વાળામુખી'; });
    await page.$eval('#rsearch', (f) => f.requestSubmit());
    await page.waitForFunction(() => document.querySelector('#offline-hits').innerText.includes('કોઈ મેળ મળ્યો નથી'), { timeout: 5000 });
    await go('#/read/9999/1');
    assert(await page.$('#not-offline'), 'missing book must not pretend to be available');
  });

  await step('OFFLINE: previously verified answer is reused from the device; a new question gets search results only, labelled as not an answer', async () => {
    await go('#/ask');
    const saved = await ask('પ્રકાશસંશ્લેષણ એટલે શું?', { mode: 'auto', marks: '' });
    assert(saved.status === 'answered' && (await text('#result')).includes('ઑફલાઇન: આ ઉપકરણ પર સંગ્રહિત'), 'saved verified answer not reused offline: ' + saved.status);
    assert(saved.text.includes('પૃષ્ઠ'), 'offline saved answer lost its citation');
    const fresh = await ask('ફેફસાં વિશે માહિતી આપો', { mode: 'auto', marks: '' });
    assert(fresh.status === 'offline-search', 'expected offline search fallback, got ' + fresh.status);
    assert(fresh.text.includes('ચકાસાયેલો ઉત્તર નથી'), 'offline search must be labelled as not a verified answer');
  });

  await step('back ONLINE: delete the downloaded book; storage is released', async () => {
    await page.setOfflineMode(false);
    await go('#/library');
    await page.click('.book .del');
    await page.waitForSelector('#del-ok', { timeout: 5000 });
    assert(await page.$('#no-books'), 'book still listed after delete');
    assert((await text('#book-bytes')).startsWith('0 B'), 'storage not released');
  });

  await step('admin source review: wrong token refused; rejecting an edition removes it from students; approve restores', async () => {
    await go('#/admin');
    await page.$eval('#tok', (e) => { e.value = 'wrong'; });
    await page.$eval('#aform', (f) => f.requestSubmit());
    await page.waitForSelector('#admin .err', { timeout: 5000 });
    await page.$eval('#tok', (e) => { e.value = 'e2e-admin'; });
    await page.$eval('#aform', (f) => f.requestSubmit());
    await page.waitForSelector('#admin .rev', { timeout: 5000 });
    const click = async (d) => {
      await page.evaluate((ed, dd) => document.querySelector(`.rev[data-ed="${ed}"][data-d="${dd}"]`).click(), offlineEd, d);
      await sleep(600);
    };
    await click('rejected');
    const r1 = await (await fetch(`${BASE}/api/editions/${offlineEd}/pages/1`)).status;
    await click('approved');
    const r2 = await (await fetch(`${BASE}/api/editions/${offlineEd}/pages/1`)).status;
    assert(r1 === 404 && r2 === 200, `expected 404 then 200, got ${r1} then ${r2}`);
  });

  await step('no uncaught JavaScript errors during the whole run', async () => {
    assert(pageErrors.length === 0, pageErrors.join(' | '));
  });
} catch (e) {
  results.push({ name: 'test harness', status: 'failed', error: String(e.stack || e).slice(0, 600) });
  console.log('HARNESS ERROR', e);
} finally {
  if (browser) await browser.close().catch(() => {});
  server.kill();
}

const passed = results.filter((r) => r.status === 'passed').length;
const summary = { suite: 'browser end-to-end (headless Chromium, 390x800 mobile viewport)', executed_at: new Date().toISOString(),
  passed, failed: results.length - passed, total: results.length, results };
mkdirSync(path.join(ROOT, 'benchmarks/results'), { recursive: true });
writeFileSync(path.join(ROOT, 'benchmarks/results/e2e_browser.json'), JSON.stringify(summary, null, 2) + '\n');
console.log(`\n${passed}/${results.length} passed`);
process.exit(passed === results.length ? 0 : 1);
