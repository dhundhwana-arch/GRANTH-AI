#!/usr/bin/env node
// GRANTH-AI OCR command-line adapter (tesseract.js, fully local, no network).
// Usage: node scripts/ocr_cli.mjs [--langs guj+eng] [--langpath DIR] image1.png [image2.png ...]
// Prints one JSON document: {"engine":..., "langs":..., "results":[{"path","text","confidence","ms"}]}
import { createWorker } from 'tesseract.js';
import path from 'node:path';
import os from 'node:os';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
let langs = 'guj+eng';
let langPath = path.join(here, '..', 'web', 'vendor', 'tessdata');
const files = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--langs') langs = args[++i];
  else if (args[i] === '--langpath') langPath = args[++i];
  else files.push(args[i]);
}
if (!files.length) {
  console.error('usage: ocr_cli.mjs [--langs guj+eng] [--langpath DIR] image...');
  process.exit(2);
}
for (const l of langs.split('+')) {
  if (!fs.existsSync(path.join(langPath, `${l}.traineddata.gz`))) {
    console.error(`missing language data ${l}.traineddata.gz in ${langPath}; run: python scripts/setup_vendor.py`);
    process.exit(3);
  }
}
const cachePath = fs.mkdtempSync(path.join(os.tmpdir(), 'granth-ocr-'));
const worker = await createWorker(langs.split('+'), 1, { langPath, gzip: true, cachePath, cacheMethod: 'none' });
const results = [];
for (const f of files) {
  const t0 = Date.now();
  const { data } = await worker.recognize(f);
  results.push({ path: f, text: data.text, confidence: data.confidence, ms: Date.now() - t0 });
}
await worker.terminate();
fs.rmSync(cachePath, { recursive: true, force: true });
process.stdout.write(JSON.stringify({ engine: 'tesseract.js', langs, results }));
