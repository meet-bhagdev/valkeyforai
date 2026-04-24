#!/usr/bin/env node
/**
 * build-notebooks.js - Converts Markdown cookbooks to Jupyter notebooks (.ipynb)
 *
 * Usage:
 *   node build-notebooks.js                    # builds all tracks
 *   node build-notebooks.js semantic-caching   # builds one track
 *
 * Output goes to notebooks/<track>/<notebook>.ipynb
 */

const fs = require('fs');
const path = require('path');

const CONTENT_DIR = path.join(__dirname, 'content');
const OUTPUT_DIR = path.join(__dirname, 'notebooks');

/**
 * Split markdown into alternating prose / code blocks.
 * Returns an array of { type: 'markdown' | 'code', lang?: string, content: string }
 */
function splitMarkdown(md) {
  const blocks = [];
  const fenceRe = /^```(\w*)\s*$/;
  const lines = md.split('\n');
  let i = 0;

  let mdBuf = [];

  function flushMd() {
    const text = mdBuf.join('\n').trim();
    if (text) blocks.push({ type: 'markdown', content: text });
    mdBuf = [];
  }

  while (i < lines.length) {
    const fenceMatch = lines[i].match(fenceRe);
    if (fenceMatch) {
      flushMd();
      const lang = fenceMatch[1] || '';
      i++; // skip opening fence
      const codeBuf = [];
      while (i < lines.length && !lines[i].match(/^```\s*$/)) {
        codeBuf.push(lines[i]);
        i++;
      }
      i++; // skip closing fence
      blocks.push({ type: 'code', lang, content: codeBuf.join('\n') });
    } else {
      mdBuf.push(lines[i]);
      i++;
    }
  }
  flushMd();
  return blocks;
}

/**
 * Convert a list of blocks into Jupyter notebook cells.
 * - python code → code cells
 * - bash code → code cells prefixed with ! (so they run in notebook)
 * - other fenced code (json, text, pseudo) → markdown cells wrapped in fences
 * - prose → markdown cells
 */
function blocksToNotebookCells(blocks) {
  const cells = [];

  for (const block of blocks) {
    if (block.type === 'markdown') {
      cells.push(markdownCell(block.content));
    } else if (block.type === 'code') {
      const lang = block.lang.toLowerCase();
      if (lang === 'python' || lang === 'py') {
        cells.push(codeCell(block.content));
      } else if (lang === 'mermaid') {
        // Skip mermaid diagrams — not supported in Jupyter
      } else if (lang === 'bash' || lang === 'sh' || lang === 'shell') {
        // Convert each line to a !-prefixed shell command for notebooks
        const shellLines = block.content
          .split('\n')
          .map(line => {
            const trimmed = line.trim();
            if (!trimmed || trimmed.startsWith('#')) return trimmed;
            return trimmed.startsWith('!') ? trimmed : `!${trimmed}`;
          })
          .join('\n');
        cells.push(codeCell(shellLines));
      } else {
        // Non-executable code (json, yaml, text, pseudo-code) → markdown fence
        cells.push(markdownCell(`\`\`\`${block.lang}\n${block.content}\n\`\`\``));
      }
    }
  }
  return cells;
}


function markdownCell(source) {
  return {
    cell_type: 'markdown',
    metadata: {},
    source: sourceLines(source),
  };
}

function codeCell(source) {
  return {
    cell_type: 'code',
    execution_count: null,
    metadata: {},
    outputs: [],
    source: sourceLines(source),
  };
}

/** Jupyter expects source as an array of lines, each ending with \n except the last */
function sourceLines(text) {
  const lines = text.split('\n');
  return lines.map((line, i) => (i < lines.length - 1 ? line + '\n' : line));
}

function buildNotebook(cells, title) {
  return {
    nbformat: 4,
    nbformat_minor: 5,
    metadata: {
      kernelspec: {
        display_name: 'Python 3',
        language: 'python',
        name: 'python3',
      },
      language_info: {
        name: 'python',
        version: '3.11.0',
      },
      title,
    },
    cells,
  };
}

function loadMeta(trackDir) {
  const metaPath = path.join(trackDir, 'meta.json');
  if (!fs.existsSync(metaPath)) {
    console.error(`  ⚠️  No meta.json in ${trackDir}`);
    return null;
  }
  return JSON.parse(fs.readFileSync(metaPath, 'utf8'));
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

  console.log(`📓 Building notebooks: ${meta.trackName} (${meta.cookbooks.length} cookbooks)`);

  for (const cookbook of meta.cookbooks) {
    const mdPath = path.join(trackDir, cookbook.source);
    if (!fs.existsSync(mdPath)) {
      console.error(`  ⚠️  Missing: ${mdPath}`);
      continue;
    }

    const md = fs.readFileSync(mdPath, 'utf8');

    // Add a title cell at the top
    const titleMd = `# ${cookbook.title}\n\n**${cookbook.difficulty}** · ~${cookbook.time} · ${meta.trackName}`;
    const blocks = splitMarkdown(md);
    const cells = [markdownCell(titleMd), ...blocksToNotebookCells(blocks)];

    const nb = buildNotebook(cells, cookbook.title);
    const outName = cookbook.source.replace(/\.md$/, '.ipynb');
    const outPath = path.join(outDir, outName);
    fs.writeFileSync(outPath, JSON.stringify(nb, null, 1));
    console.log(`  ✅ ${outName}`);
  }
}

// --- Main ---
const targetTrack = process.argv[2];

if (targetTrack) {
  buildTrack(targetTrack);
} else {
  const tracks = fs.readdirSync(CONTENT_DIR).filter(d =>
    fs.statSync(path.join(CONTENT_DIR, d)).isDirectory()
  );
  console.log(`🔨 Building notebooks for ${tracks.length} track(s)...\n`);
  for (const track of tracks) {
    buildTrack(track);
  }
}

console.log('\n✨ Done!');
