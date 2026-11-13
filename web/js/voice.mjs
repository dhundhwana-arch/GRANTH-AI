// Gujarati voice question input (Web Speech API) + optional read-aloud.
// Voice is ONLY a way to type: the transcript is put into the editable question box and is never
// answered or submitted automatically.
export const VOICE_ERRORS = {
  'unsupported': 'આ બ્રાઉઝરમાં અવાજથી લખવાની સુવિધા ઉપલબ્ધ નથી. કૃપા કરીને પ્રશ્ન ટાઇપ કરો.',
  'not-allowed': 'માઇક્રોફોનની પરવાનગી મળી નથી. બ્રાઉઝરના સેટિંગ્સમાં માઇક્રોફોનની પરવાનગી આપો અથવા પ્રશ્ન ટાઇપ કરો.',
  'service-not-allowed': 'માઇક્રોફોનની પરવાનગી મળી નથી. બ્રાઉઝરના સેટિંગ્સમાં માઇક્રોફોનની પરવાનગી આપો અથવા પ્રશ્ન ટાઇપ કરો.',
  'audio-capture': 'માઇક્રોફોન મળ્યો નથી. ઉપકરણનો માઇક્રોફોન તપાસો.',
  'no-speech': 'કોઈ અવાજ સંભળાયો નથી. ફરી પ્રયત્ન કરો.',
  'network': 'અવાજ ઓળખવા માટે ઇન્ટરનેટ જરૂરી છે. હાલ જોડાણ નથી – પ્રશ્ન ટાઇપ કરો.',
  'aborted': 'અવાજ ઓળખવાનું બંધ કર્યું.',
  'language-not-supported': 'આ ઉપકરણમાં ગુજરાતી અવાજ-ઓળખ ઉપલબ્ધ નથી. પ્રશ્ન ટાઇપ કરો.',
  'unknown': 'અવાજ ઓળખવામાં ભૂલ થઈ. ફરી પ્રયત્ન કરો અથવા પ્રશ્ન ટાઇપ કરો.',
};

export function voiceErrorMessage(code) {
  return VOICE_ERRORS[code] || VOICE_ERRORS.unknown;
}

export function getRecognitionCtor(win = globalThis) {
  return win.SpeechRecognition || win.webkitSpeechRecognition || null;
}

/**
 * handlers: onTranscript(text, isFinal), onError(code, message), onState('listening' | 'idle')
 * Returns {supported, start(), stop()}.
 */
export function createVoiceInput(handlers, Ctor = getRecognitionCtor(), lang = 'gu-IN') {
  const { onTranscript = () => {}, onError = () => {}, onState = () => {} } = handlers || {};
  if (!Ctor) {
    return { supported: false, start() { onError('unsupported', voiceErrorMessage('unsupported')); return false; }, stop() {} };
  }
  let rec = null;
  let listening = false;
  return {
    supported: true,
    get listening() { return listening; },
    start() {
      if (listening) return false;
      rec = new Ctor();
      rec.lang = lang;
      rec.interimResults = true;
      rec.continuous = false;
      rec.maxAlternatives = 1;
      rec.onstart = () => { listening = true; onState('listening'); };
      rec.onresult = (ev) => {
        let text = '';
        let final = false;
        for (let i = 0; i < ev.results.length; i++) {
          text += ev.results[i][0].transcript;
          if (ev.results[i].isFinal) final = true;
        }
        onTranscript(text.trim(), final);
      };
      rec.onerror = (ev) => {
        const code = (ev && ev.error) || 'unknown';
        onError(code, voiceErrorMessage(code));
      };
      rec.onend = () => { listening = false; onState('idle'); };
      try {
        rec.start();
      } catch (e) {
        listening = false;
        const code = e && e.name === 'NotAllowedError' ? 'not-allowed' : 'unknown';
        onError(code, voiceErrorMessage(code));
        onState('idle');
        return false;
      }
      return true;
    },
    stop() { if (rec && listening) rec.stop(); },
  };
}

/** Read text aloud in Gujarati if the device has a Gujarati voice. Returns {spoken, reason}. */
export function speakGujarati(text, synth = globalThis.speechSynthesis, Utterance = globalThis.SpeechSynthesisUtterance) {
  if (!synth || !Utterance) return { spoken: false, reason: 'unsupported' };
  const voices = synth.getVoices ? synth.getVoices() : [];
  const voice = voices.find((v) => /^gu(-|_|$)/i.test(v.lang));
  if (voices.length && !voice) return { spoken: false, reason: 'no-gujarati-voice' };
  synth.cancel();
  const u = new Utterance(text.replace(/\|/g, ' '));
  u.lang = 'gu-IN';
  if (voice) u.voice = voice;
  u.rate = 0.95;
  synth.speak(u);
  return { spoken: true, reason: voice ? 'gujarati-voice' : 'voice-list-empty-tried-default' };
}
