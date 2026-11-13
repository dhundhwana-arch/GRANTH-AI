// Camera / gallery image preparation for on-device OCR. Geometry is pure (unit-tested); drawing needs a canvas.
export function fitWithin(w, h, maxSide) {
  const s = Math.min(1, maxSide / Math.max(w, h));
  return { width: Math.max(1, Math.round(w * s)), height: Math.max(1, Math.round(h * s)), scale: s };
}

/** margins = {top, right, bottom, left} in percent (0-45). Returns the crop rectangle in source pixels. */
export function cropRect(w, h, margins = {}) {
  const pct = (v) => Math.min(45, Math.max(0, Number(v) || 0)) / 100;
  const l = Math.round(w * pct(margins.left));
  const r = Math.round(w * pct(margins.right));
  const t = Math.round(h * pct(margins.top));
  const b = Math.round(h * pct(margins.bottom));
  return { x: l, y: t, width: Math.max(1, w - l - r), height: Math.max(1, h - t - b) };
}

export function normalizeRotation(deg) {
  return (((Math.round(deg / 90) * 90) % 360) + 360) % 360;
}

export function rotatedSize(w, h, deg) {
  const d = normalizeRotation(deg);
  return d === 90 || d === 270 ? { width: h, height: w } : { width: w, height: h };
}

export const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export const MAX_IMAGE_BYTES = 12 * 1024 * 1024;

export function validateImageFile(file) {
  if (!file) return { ok: false, message: 'કોઈ ચિત્ર પસંદ થયું નથી.' };
  if (!ACCEPTED_TYPES.includes(file.type)) return { ok: false, message: 'માત્ર JPG, PNG કે WebP ચિત્ર ચાલશે.' };
  if (file.size > MAX_IMAGE_BYTES) return { ok: false, message: 'ચિત્ર બહુ મોટું છે (12 MB થી વધુ).' };
  return { ok: true };
}

/** Clean typical OCR artefacts from a question line; the student still reviews and edits the text. */
export function cleanOcrText(text) {
  return (text || '').normalize('NFC').replace(/[\u200b\u200c\u200d]/g, '').replace(/[ \t]+/g, ' ')
    .replace(/\s*\n\s*/g, ' ').replace(/\s+([?,.!])/g, '$1').trim();
}

/** Draw source (ImageBitmap / HTMLImageElement) rotated + cropped + downscaled. Returns a canvas. */
export function renderToCanvas(source, { rotation = 0, margins = {}, maxSide = 1600 } = {}, doc = globalThis.document) {
  const sw = source.width || source.naturalWidth;
  const sh = source.height || source.naturalHeight;
  const rot = normalizeRotation(rotation);
  const rs = rotatedSize(sw, sh, rot);
  const full = doc.createElement('canvas');
  full.width = rs.width;
  full.height = rs.height;
  const ctx = full.getContext('2d');
  ctx.translate(rs.width / 2, rs.height / 2);
  ctx.rotate((rot * Math.PI) / 180);
  ctx.drawImage(source, -sw / 2, -sh / 2);
  const c = cropRect(rs.width, rs.height, margins);
  const fit = fitWithin(c.width, c.height, maxSide);
  const out = doc.createElement('canvas');
  out.width = fit.width;
  out.height = fit.height;
  const octx = out.getContext('2d');
  octx.fillStyle = '#fff';
  octx.fillRect(0, 0, out.width, out.height);
  octx.drawImage(full, c.x, c.y, c.width, c.height, 0, 0, fit.width, fit.height);
  return out;
}
