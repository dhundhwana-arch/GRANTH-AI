// Feature 1 (voice) and Feature 2 (image preparation) logic tests with mocked browser objects.
// Real microphone transcription accuracy cannot be tested without a device and is NOT claimed.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createVoiceInput, voiceErrorMessage, speakGujarati, VOICE_ERRORS } from '../../web/js/voice.mjs';
import * as img from '../../web/js/imageprep.mjs';

class MockRecognition {
  static last = null;
  constructor() { MockRecognition.last = this; this.started = false; }
  start() { if (MockRecognition.throwOnStart) { const e = new Error('denied'); e.name = 'NotAllowedError'; throw e; } this.started = true; this.onstart && this.onstart(); }
  stop() { this.onend && this.onend(); }
  emit(results) { this.onresult({ results }); }
  fail(code) { this.onerror({ error: code }); this.onend(); }
}
const result = (t, isFinal) => Object.assign([{ transcript: t }], { isFinal });

test('transcript is delivered for review (interim then final) in Gujarati locale and nothing is auto-submitted', () => {
  const seen = []; const states = [];
  const v = createVoiceInput({ onTranscript: (t, f) => seen.push([t, f]), onState: (s) => states.push(s) }, MockRecognition);
  assert.equal(v.supported, true);
  assert.equal(v.start(), true);
  const rec = MockRecognition.last;
  assert.equal(rec.lang, 'gu-IN');
  assert.equal(rec.interimResults, true);
  rec.emit([result('પ્રકાશ', false)]);
  rec.emit([result('પ્રકાશસંશ્લેષણ શું છે', true)]);
  rec.stop();
  assert.deepEqual(seen, [['પ્રકાશ', false], ['પ્રકાશસંશ્લેષણ શું છે', true]]);
  assert.deepEqual(states, ['listening', 'idle']);
  assert.equal(Object.keys(v).includes('submit'), false);      // the module has no way to submit or answer
});

test('microphone permission denial gives a clear Gujarati message and returns to idle', () => {
  const errors = []; const states = [];
  const v = createVoiceInput({ onError: (c, m) => errors.push([c, m]), onState: (s) => states.push(s) }, MockRecognition);
  v.start();
  MockRecognition.last.fail('not-allowed');
  assert.equal(errors[0][0], 'not-allowed');
  assert.match(errors[0][1], /માઇક્રોફોનની પરવાનગી મળી નથી/);
  assert.equal(states.at(-1), 'idle');
  assert.equal(v.listening, false);
});

test('permission error thrown synchronously by start() is handled', () => {
  MockRecognition.throwOnStart = true;
  const errors = [];
  const v = createVoiceInput({ onError: (c, m) => errors.push([c, m]) }, MockRecognition);
  assert.equal(v.start(), false);
  assert.equal(errors[0][0], 'not-allowed');
  MockRecognition.throwOnStart = false;
});

test('unsupported browser, no-speech, network and unknown errors have messages', () => {
  const errors = [];
  const v = createVoiceInput({ onError: (c, m) => errors.push([c, m]) }, null);
  assert.equal(v.supported, false);
  assert.equal(v.start(), false);
  assert.equal(errors[0][0], 'unsupported');
  for (const code of ['no-speech', 'network', 'audio-capture', 'service-not-allowed']) assert.ok(VOICE_ERRORS[code].length > 10);
  assert.equal(voiceErrorMessage('something-new'), VOICE_ERRORS.unknown);
});

test('read-aloud uses a Gujarati voice, and reports honestly when none exists', () => {
  const spoken = [];
  class U { constructor(t) { this.text = t; } }
  const synth = (voices) => ({ getVoices: () => voices, cancel() {}, speak: (u) => spoken.push(u) });
  const ok = speakGujarati('ઉત્તર | કોષ્ટક', synth([{ lang: 'en-US' }, { lang: 'gu-IN', name: 'G' }]), U);
  assert.deepEqual([ok.spoken, spoken[0].lang, spoken[0].voice.name, spoken[0].text.includes('|')], [true, 'gu-IN', 'G', false]);
  assert.deepEqual(speakGujarati('x', synth([{ lang: 'en-US' }]), U), { spoken: false, reason: 'no-gujarati-voice' });
  assert.equal(speakGujarati('x', undefined, undefined).reason, 'unsupported');
});

test('image geometry: downscale, crop margins, rotation', () => {
  assert.deepEqual(img.fitWithin(4000, 3000, 1600), { width: 1600, height: 1200, scale: 0.4 });
  assert.equal(img.fitWithin(800, 600, 1600).scale, 1);
  assert.deepEqual(img.cropRect(1000, 500, { top: 10, bottom: 20, left: 5, right: 5 }), { x: 50, y: 50, width: 900, height: 350 });
  assert.deepEqual(img.cropRect(100, 100, { top: 90, left: -5 }), { x: 0, y: 45, width: 100, height: 55 });   // clamped
  assert.equal(img.normalizeRotation(-90), 270);
  assert.equal(img.normalizeRotation(450), 90);
  assert.deepEqual(img.rotatedSize(400, 300, 90), { width: 300, height: 400 });
  assert.deepEqual(img.rotatedSize(400, 300, 180), { width: 400, height: 300 });
});

test('image file validation and OCR text clean-up', () => {
  assert.equal(img.validateImageFile(null).ok, false);
  assert.equal(img.validateImageFile({ type: 'application/pdf', size: 10 }).ok, false);
  assert.equal(img.validateImageFile({ type: 'image/jpeg', size: 20 * 1024 * 1024 }).ok, false);
  assert.equal(img.validateImageFile({ type: 'image/png', size: 1000 }).ok, true);
  assert.equal(img.cleanOcrText('હરિતદ્રવ્ય કોને\n  કહે છે ?\n'), 'હરિતદ્રવ્ય કોને કહે છે?');
});
