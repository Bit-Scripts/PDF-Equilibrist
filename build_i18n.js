#!/usr/bin/env node
/**
 * Build script — generates language-specific HTML files from templates.
 *
 * Usage:
 *   node build_i18n.js              # all languages, all templates
 *   node build_i18n.js fr           # French only, all templates
 *   node build_i18n.js en docs      # English only, docs template only
 *
 * Output:
 *   fr  + index → index.html
 *   fr  + docs  → docs/index.html
 *   en  + index → en/index.html
 *   en  + docs  → docs/en/index.html
 */

const fs   = require('fs');
const path = require('path');

const ROOT_DIR = __dirname;
const L18N_DIR = path.join(ROOT_DIR, 'l18n');

const TEMPLATES = [
  { tpl: 'multilingual/index.template.html', frOut: 'index.html',      otherOut: '{lang}/index.html' },
  { tpl: 'multilingual/docs.template.html',  frOut: 'docs/index.html', otherOut: 'docs/{lang}/index.html' },
];

const targetLang = process.argv[2] || null;
const targetTpl  = process.argv[3] || null;

const dictFiles = fs.readdirSync(L18N_DIR)
  .filter(f => f.endsWith('.json'))
  .filter(f => !targetLang || f === `${targetLang}.json`)
  .sort();

if (dictFiles.length === 0) {
  console.error(`No dictionary found${targetLang ? ` for lang "${targetLang}"` : ''}.`);
  process.exit(1);
}

let built = 0;
for (const file of dictFiles) {
  const lang = path.basename(file, '.json');
  const dict = JSON.parse(fs.readFileSync(path.join(L18N_DIR, file), 'utf8'));

  for (const { tpl, frOut, otherOut } of TEMPLATES) {
    if (targetTpl && !tpl.includes(targetTpl)) continue;

    const template = fs.readFileSync(path.join(ROOT_DIR, tpl), 'utf8');
    const missing = [];

    const html = template.replace(/\{\{([\w.]+)\}\}/g, (match, key) => {
      if (Object.prototype.hasOwnProperty.call(dict, key)) return dict[key];
      missing.push(key);
      return match;
    });

    if (missing.length > 0) {
      console.warn(`[${lang}/${path.basename(tpl)}] Missing keys: ${missing.join(', ')}`);
    }

    const outRel = lang === 'fr' ? frOut : otherOut.replace('{lang}', lang);
    const outPath = path.join(ROOT_DIR, outRel);
    const outDir = path.dirname(outPath);
    if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true });

    fs.writeFileSync(outPath, html, 'utf8');
    console.log(`[${lang}] → ${path.relative(ROOT_DIR, outPath)}`);
    built++;
  }
}

console.log(`Done. ${built} file(s) built.`);
