// Draws the PNG images the site's emails show (email clients don't show SVG):
//   node web/tools/mail-images.cjs
// Writes web/tickrweb/static/web/mail/: the wordmark and each email's symbol, one light and one
// dark copy each, at 2x for sharp screens. Needs Node with Playwright and its Chromium. Run it
// again after brand.svg, a symbol or a mail colour below changes, and commit the PNGs.
// Colours: the approved mail design (mockup board SiteEmails); light first, then dark.
const { chromium } = require("playwright");
const { readFileSync, mkdirSync } = require("node:fs");
const { join } = require("node:path");

const web = join(__dirname, "..");
const out = join(web, "tickrweb/static/web/mail");
const scale = 2; // device pixels per CSS pixel
const wordmarkHeight = 30; // CSS px, as mail/base.html shows it
const symbolSize = 22; // CSS px, as mail/base.html shows it

const themes = {
  light: { text: "#0B1020", dot: "#6B7493", prim: "#0B766F" },
  dark: { text: "#EEF1FA", dot: "#7C86A8", prim: "#2DD4BF" },
};
const teal = "#2DD4BF"; // the glyph's level bar, the same in both themes

// The symbols of the approved board, 24 x 24, drawn in the theme's primary colour.
const stroke = 'fill="none" stroke="currentColor" stroke-width="2"';
const symbols = {
  key: `<path d="M15 7a4 4 0 1 0-3.9 5H12v2h2v2h2v2h3v-3l-4.1-4.1A4 4 0 0 0 15 7z" ${stroke} stroke-linejoin="round"/><circle cx="15" cy="7" r="1.2" fill="currentColor"/>`,
  lock: `<rect x="5" y="11" width="14" height="9" rx="2" ${stroke}/><path d="M8 11V8a4 4 0 0 1 8 0v3" ${stroke}/>`,
  star: `<path d="M12 3l2.6 5.6 6 .6-4.5 4 1.3 6-5.4-3.1-5.4 3.1 1.3-6-4.5-4 6-.6z" ${stroke} stroke-linejoin="round"/>`,
  mail: `<rect x="3" y="5" width="18" height="14" rx="2" ${stroke}/><path d="m4 7 8 6 8-6" ${stroke}/>`,
  phone: `<rect x="7" y="3" width="10" height="18" rx="2.5" ${stroke}/><path d="M11 18h2" ${stroke} stroke-linecap="round"/>`,
  shield: `<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z" ${stroke} stroke-linejoin="round"/><path d="m9 12 2 2 4-4" ${stroke} stroke-linecap="round" stroke-linejoin="round"/>`,
};

// brand.svg without its template comment.
const wordmark = readFileSync(join(web, "tickrweb/templates/brand.svg"), "utf8").replace(/\{#[\s\S]*?#\}\s*/, "");

async function main() {
mkdirSync(out, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ deviceScaleFactor: scale });
const shoot = async function shoot(name, html, css) {
  await page.setContent(`<style>html,body{margin:0;background:transparent}svg{display:block}${css}</style>${html}`);
  await page.locator("svg").first().screenshot({ path: join(out, name), omitBackground: true });
};
for (const [theme, c] of Object.entries(themes)) {
  await shoot(`wordmark-${theme}.png`, wordmark,
    `svg{height:${wordmarkHeight}px;width:auto}.wl{fill:${c.text}}.wv{fill:${teal}}.wd{fill:${c.dot}}`);
  for (const [name, body] of Object.entries(symbols)) {
    await shoot(`${name}-${theme}.png`, `<svg viewBox="0 0 24 24">${body}</svg>`,
      `svg{width:${symbolSize}px;height:${symbolSize}px;color:${c.prim}}`);
  }
}
await browser.close();
}
main();
