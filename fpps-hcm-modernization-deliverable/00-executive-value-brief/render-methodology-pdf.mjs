// Render methodology-overview.html to a customer-ready landscape PDF and
// write methodology-overview.pdf.source.sha256 (hash of the HTML it was
// rendered from) so tests/test_methodology_overview.py can detect a stale PDF.
//
// usage: node render-methodology-pdf.mjs [chrome executable]
// needs: a Chrome/Chromium binary, and `playwright` resolvable from the
// current working directory (run it from a directory where `npm i playwright` was done).
import { createHash } from 'crypto';
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const { chromium } = createRequire(path.join(process.cwd(), 'noop.js'))('playwright');
const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, 'methodology-overview.html');
const out = path.join(here, 'methodology-overview.pdf');
const executablePath = process.argv[2] || process.env.CHROME_BIN || undefined;

const PRINT_CSS = `
@page{size:11in 8.5in;margin:0.4in 0.35in 0.5in 0.35in}
html{background:#0a0a0f}
html,body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
html{scroll-behavior:auto}
header,.ctas,.marks,.stage::after,.stage .bar{display:none!important}
.hero .glow,.hero .gridlines{display:block!important}
.wrap{max-width:none;padding:0 18px}
section{padding:14px 0 12px 0;break-before:page;break-inside:auto;scroll-margin-top:0}
section+section{border-top:0}
section.hero{break-before:auto;padding:56px 0 12px 0;min-height:auto}
section.hero h1{font-size:2.3rem;margin-bottom:14px}
section.hero .lede{font-size:1.1rem;margin-bottom:18px}
.cobrand{margin-bottom:22px}
.stats{margin-top:16px}
.stat .n{font-size:1.6rem}
h2{font-size:1.65rem;margin-bottom:8px}
.lede{font-size:1.02rem;margin-bottom:16px;max-width:1060px}
.eyebrow{margin-bottom:8px}
.pipeline{margin-top:20px}
.diff{padding:20px 24px}
#differentiator figure{margin-top:10px!important}
#differentiator .grid.g2{margin-top:12px!important}
#differentiator .lede{margin-bottom:0;font-size:.95rem;margin-top:8px!important}
#differentiator .callout{line-height:1.45}
#differentiator pre{font-size:.7rem;line-height:1.28;padding:8px 12px}
#differentiator .card .small{font-size:.86rem}
#differentiator .diff{padding:16px 20px}
#differentiator .callout{margin-top:10px!important;padding:9px 14px;font-size:.88rem}
#differentiator figure svg{width:100%;max-width:900px;height:auto;display:block;margin:0 auto}
#differentiator figure .fig{padding:6px}
.diff .grid{margin-top:16px}
figure{margin-top:18px}
figure .fig{padding:14px}
.card{padding:16px 18px}
.cap{padding:12px 14px;gap:6px}
.cap .si{font-size:.8rem}
.cap .art{font-size:.72rem}
#how .grid.g3{margin-top:16px!important}
#how .card .small{font-size:.84rem}
#how figure{margin-top:12px}
.caps{grid-template-columns:repeat(4,1fr);gap:12px}
#disposition th,#disposition td{padding:6px 10px;font-size:.8rem}
#disposition td.mono{font-size:.72rem}
#disposition .grid.disp{margin-top:12px!important;grid-template-columns:1fr}
#disposition .grid.disp>div:last-child{display:block;max-width:920px;margin:0 auto;break-before:page}
#disposition .grid.disp>div:last-child figure{margin-top:0}
#disposition .grid.disp>div:last-child .card{margin-top:18px!important}
#disposition .grid.disp>div:last-child svg{width:100%;max-width:640px;height:auto;display:block;margin:0 auto}
#disposition .grid.g4{margin-top:16px!important}
.card,.cap,.stat,.stage,figure,pre,table,.kpi,.compare,.value>*,.steps>*,.recon>*,.info,blockquote,.tablewrap,.scrollx,.pillar,.callout
  {break-inside:avoid}
h2,h3,.eyebrow,figcaption{break-after:avoid}
pre{white-space:pre-wrap;word-break:break-word;overflow:visible}
.scrollx,.tablewrap,figure .fig{overflow:visible}
a{color:inherit;text-decoration:none}
footer{break-before:page;padding-top:12px}
`;

const browser = await chromium.launch({
  executablePath,
  headless: true,
  args: ['--headless=new'],
});
const page = await browser.newPage({ viewport: { width: 1354, height: 999 } });
await page.goto('file://' + src, { waitUntil: 'networkidle' });
await page.addStyleTag({ content: PRINT_CSS });
await page.emulateMedia({ media: 'print' });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(400);

const footer = `
<div style="width:100%;font-family:Inter,Arial,sans-serif;font-size:7.5pt;color:#52525b;
            display:flex;justify-content:space-between;align-items:center;padding:0 0.35in;box-sizing:border-box">
  <span>Cognition &nbsp;×&nbsp; SMX &nbsp;×&nbsp; U.S. Department of the Interior, Interior Business Center &nbsp;·&nbsp; Requirements-first modernization of a Natural / ADABAS payroll estate</span>
  <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
</div>`;

await page.pdf({
  path: out,
  width: '11in',
  height: '8.5in',
  printBackground: true,
  preferCSSPageSize: true,
  scale: 0.73,
  displayHeaderFooter: true,
  headerTemplate: '<div></div>',
  footerTemplate: footer,
});
await browser.close();
const digest = createHash('sha256').update(fs.readFileSync(src)).digest('hex');
fs.writeFileSync(out + '.source.sha256', digest + '\n');
console.log('wrote', out, fs.statSync(out).size, 'bytes; source sha256', digest);
