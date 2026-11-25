// Builds one self-contained HTML file from dist/: CSS, JS and all data files inline.
// The file opens with a double click (file://) and needs no web server.
// Usage: npm run build:single  ->  dist-single/defi-luecke.html
import { readFileSync, writeFileSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { join, relative, sep } from 'node:path';

const dist = 'dist';
const outDir = 'dist-single';
let html = readFileSync(join(dist, 'index.html'), 'utf8');

// Keep "</script" and "</style" from ending the inline blocks early.
const safe = (text, tag) => text.replaceAll(`</${tag}`, `<\\/${tag}`);

// 1. Stylesheets
html = html.replace(/<link rel="stylesheet"[^>]*href="\.\/([^"]+)"[^>]*>/g, (_, file) => {
  const css = readFileSync(join(dist, file), 'utf8');
  return `<style>\n${safe(css, 'style')}\n</style>`;
});

// 2. Data files below dist/data -> window.__DEFI_DATA__ (keys = path below data/)
const data = {};
const walk = (dir) => {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else if (/\.(geo)?json$/.test(name)) {
      data[relative(join(dist, 'data'), path).split(sep).join('/')] = JSON.parse(
        readFileSync(path, 'utf8'),
      );
    }
  }
};
walk(join(dist, 'data'));
if (!data['regions.json']) throw new Error('dist/data/regions.json fehlt – zuerst export-web ausführen.');
const dataScript = `<script>window.__DEFI_DATA__=${safe(JSON.stringify(data), 'script')};</script>`;

// 3. Module scripts inline (a module loaded via src= is blocked on file://)
html = html.replace(
  /<script type="module"[^>]*src="\.\/([^"]+)"[^>]*><\/script>/g,
  (_, file) => {
    const js = readFileSync(join(dist, file), 'utf8');
    return `${dataScript}\n<script type="module">\n${safe(js, 'script')}\n</script>`;
  },
);
if (html.includes('src="./assets/') || html.includes('href="./assets/')) {
  throw new Error('Nicht alle Assets wurden eingebettet.');
}

mkdirSync(outDir, { recursive: true });
const out = join(outDir, 'defi-luecke.html');
writeFileSync(out, html);
console.log(`Geschrieben: ${out} (${(Buffer.byteLength(html) / 1e6).toFixed(1)} MB, ${Object.keys(data).length} Datendateien)`);
