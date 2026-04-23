#!/usr/bin/env node
/**
 * build.js - Converts Markdown cookbooks to styled HTML pages
 * 
 * Usage: node build.js [track-name]
 *   node build.js                    # builds all tracks
 *   node build.js semantic-caching   # builds one track
 */

const fs = require('fs');
const path = require('path');
const { marked } = require('marked');

const CONTENT_DIR = path.join(__dirname, 'content');
const OUTPUT_DIR = path.join(__dirname, 'cookbooks');

// Configure marked for GitHub-flavored markdown
marked.setOptions({
  gfm: true,
  breaks: false,
});

function loadMeta(trackDir) {
  const metaPath = path.join(trackDir, 'meta.json');
  if (!fs.existsSync(metaPath)) {
    console.error(`  ⚠️  No meta.json in ${trackDir}`);
    return null;
  }
  return JSON.parse(fs.readFileSync(metaPath, 'utf8'));
}

function buildPage(mdContent, cookbook, track, meta) {
  const htmlContent = marked.parse(mdContent);
  
  const diffClass = { 'Beginner': 'diff-easy', 'Intermediate': 'diff-medium', 'Advanced': 'diff-hard' }[cookbook.difficulty] || 'diff-medium';
  
  const prevHtml = cookbook.prev
    ? `<a href="${cookbook.prev.file}" class="prev"><span class="label">← Previous</span><span class="title">${cookbook.prev.title}</span></a>`
    : '<div></div>';
  
  const nextHtml = cookbook.next
    ? `<a href="${cookbook.next.file}" class="next"><span class="label">Next →</span><span class="title">${cookbook.next.title}</span></a>`
    : '<div></div>';

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${cookbook.num} - ${cookbook.title} - Valkey for AI</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<link rel="icon" href="/valkey-logo.svg" type="image/svg+xml">
<link rel="stylesheet" href="../cookbook.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css">
<style>
body.light .nav{background:rgba(255,255,255,.9)!important}
body.light pre{background:rgba(0,0,0,.03)!important;border-color:rgba(0,0,0,.08)!important}
body.light code{color:#1d1d1f}
body.light .callout{background:rgba(0,0,0,.02);border-color:rgba(0,0,0,.08)}
body.light table{border-color:rgba(0,0,0,.08)}
body.light th{background:rgba(0,0,0,.04)}
body.light td{border-color:rgba(0,0,0,.06)}
body.light{--bg:#fff;--bg-elevated:#f5f5f7;--bg-card:rgba(0,0,0,.03);--bg-card-hover:rgba(0,0,0,.06);--brd:rgba(0,0,0,.08);--t1:#1d1d1f;--t2:rgba(29,29,31,.6);--t3:rgba(29,29,31,.4)}
.theme-toggle{background:rgba(128,128,128,.12);border:1px solid rgba(128,128,128,.2);border-radius:100px;width:36px;height:36px;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;position:fixed;top:18px;right:24px;z-index:1001}
pre{position:relative}
pre code.hljs{background:transparent!important;padding:0}
</style>
</head>
<body>
<nav class="nav"><div class="nav-inner"><a href="/" class="nav-logo"><img src="/valkey-logo.svg" alt="Valkey"><span class="accent">for ai</span></a><div class="nav-links"><a href="/#use-cases">Use Cases</a><a href="/#frameworks">Frameworks</a><a href="https://github.com/meet-bhagdev/valkeyforai/tree/main" target="_blank">GitHub</a></div></div></nav>
<article>
<div class="breadcrumb"><a href="/">Home</a> → <a href="/cookbooks/${track}/">${meta.trackName}</a> → ${cookbook.num} ${cookbook.breadcrumb || cookbook.title}</div>
<div class="meta"><span class="${diffClass}">${cookbook.difficulty}</span><span class="lang">${cookbook.language || 'Python'}</span><span class="lang">~${cookbook.time}</span></div>
<h1>${cookbook.h1 || cookbook.title}</h1>
${cookbook.lead ? `<p class="lead">${cookbook.lead}</p>` : ''}

${htmlContent}

<div class="nav-prev-next">
${prevHtml}
${nextHtml}
</div>
</article>
<button class="theme-toggle" onclick="toggleTheme()" aria-label="Toggle theme"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/></svg></button>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script>hljs.highlightAll();</script>
<script>function toggleTheme(){var b=document.body,l=b.classList.toggle("light");localStorage.setItem("theme",l?"light":"dark")}(function(){if(localStorage.getItem("theme")==="light")document.body.classList.add("light")})()</script>
</body>
</html>`;
}

function buildTrack(trackName) {
  const trackDir = path.join(CONTENT_DIR, trackName);
  const outDir = path.join(OUTPUT_DIR, trackName);
  
  if (!fs.existsSync(trackDir)) {
    console.error(`❌ Track not found: ${trackDir}`);
    return;
  }
  
  const meta = loadMeta(trackDir);
  if (!meta) return;
  
  fs.mkdirSync(outDir, { recursive: true });
  
  console.log(`📚 Building: ${meta.trackName} (${meta.cookbooks.length} cookbooks)`);
  
  for (const cookbook of meta.cookbooks) {
    const mdPath = path.join(trackDir, cookbook.source);
    if (!fs.existsSync(mdPath)) {
      console.error(`  ⚠️  Missing: ${mdPath}`);
      continue;
    }
    
    const mdContent = fs.readFileSync(mdPath, 'utf8');
    const html = buildPage(mdContent, cookbook, trackName, meta);
    const outPath = path.join(outDir, cookbook.output);
    fs.writeFileSync(outPath, html);
    console.log(`  ✅ ${cookbook.output}`);
  }
}

// Main
const targetTrack = process.argv[2];

if (targetTrack) {
  buildTrack(targetTrack);
} else {
  // Build all tracks that have content/ directories
  const tracks = fs.readdirSync(CONTENT_DIR).filter(d => 
    fs.statSync(path.join(CONTENT_DIR, d)).isDirectory()
  );
  console.log(`🔨 Building ${tracks.length} track(s)...\n`);
  for (const track of tracks) {
    buildTrack(track);
  }
}

console.log('\n✨ Done!');
