#!/usr/bin/env node
/**
 * Build script — generates language-specific index.html files from a template.
 *
 * Usage:
 *   node build_i18n.js              # build all languages
 *   node build_i18n.js fr           # build only French
 *
 * Output:
 *   fr  → index.html        (canonical FR root)
 *   en  → en/index.html
 *   ... → {lang}/index.html
 */

const fs   = require('fs');
const path = require('path');

const TEMPLATE = path.join(__dirname, 'multilingual', 'index.template.html');
const L18N_DIR = path.join(__dirname, 'l18n');
const ROOT_DIR = __dirname;

const targetLang = process.argv[2] || null;

const template = fs.readFileSync(TEMPLATE, 'utf8');

const dictFiles = fs.readdirSync(L18N_DIR)
  .filter(f => f.endsWith('.json'))
  .filter(f => !targetLang || f === `${targetLang}.json`);

if (dictFiles.length === 0) {
  console.error(`No dictionary found${targetLang ? ` for lang "${targetLang}"` : ''}.`);
  process.exit(1);
}

let built = 0;
for (const file of dictFiles) {
  const lang = path.basename(file, '.json');
  const dict = JSON.parse(fs.readFileSync(path.join(L18N_DIR, file), 'utf8'));

  let html = template;
  let missing = [];

  html = html.replace(/\{\{([\w.]+)\}\}/g, (match, key) => {
    if (Object.prototype.hasOwnProperty.call(dict, key)) {
      return dict[key];
    }
    missing.push(key);
    return match;
  });

  if (missing.length > 0) {
    console.warn(`[${lang}] Missing keys: ${missing.join(', ')}`);
  }

  let outPath;
  if (lang === 'fr') {
    outPath = path.join(ROOT_DIR, 'index.html');
  } else {
    const outDir = path.join(ROOT_DIR, lang);
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });
    outPath = path.join(outDir, 'index.html');
  }

  fs.writeFileSync(outPath, html, 'utf8');
  console.log(`[${lang}] → ${path.relative(ROOT_DIR, outPath)}`);
  built++;
}

console.log(`Done. ${built} file(s) built.`);
