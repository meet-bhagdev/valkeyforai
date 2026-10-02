#!/usr/bin/env node
/**
 * build-notebooks.js - Converts Markdown cookbooks to Jupyter notebooks (.ipynb)
 *
 * Usage:
 *   node build-notebooks.js                    # builds all tracks
 *   node build-notebooks.js semantic-caching   # builds one track
 *   node build-notebooks.js --check             # verifies tracked notebooks
 *
 * Output goes to notebooks/<track>/<notebook>.ipynb
 */

const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const CONTENT_DIR = path.join(__dirname, 'content');
const OUTPUT_DIR = path.join(__dirname, 'notebooks');

/**
 * Split markdown into alternating prose / code blocks.
 * Returns an array of { type: 'markdown' | 'code', lang?: string, content: string }
 */
function splitMarkdown(md, sourceLabel) {
  const blocks = [];
  const fenceRe = /^```([^`]*)\s*$/;
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
      const lang = (fenceMatch[1] || '').trim().split(/\s+/, 1)[0];
      i++; // skip opening fence
      const codeBuf = [];
      while (i < lines.length && !lines[i].match(/^```\s*$/)) {
        codeBuf.push(lines[i]);
        i++;
      }
      if (i >= lines.length) {
        throw new Error(`Unclosed code fence in ${sourceLabel}`);
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
 * - bash code → %%bash cells, except environment-file snippets
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
      } else if (lang === 'bash' || lang === 'sh' || lang === 'shell') {
        if (isEnvironmentSnippet(block.content)) {
          cells.push(markdownCell(fencedBlock(block)));
        } else {
          cells.push(codeCell(`%%bash\n${block.content}`));
        }
      } else {
        // Preserve diagrams and non-Python examples as fenced Markdown.
        cells.push(markdownCell(fencedBlock(block)));
      }
    }
  }
  return cells;
}

function isEnvironmentSnippet(source) {
  const meaningfulLines = source
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && !line.startsWith('#'));

  return meaningfulLines.length > 0 && meaningfulLines.every(line =>
    /^(?:export\s+)?[A-Za-z_][A-Za-z0-9_]*=/.test(line)
  );
}

function fencedBlock(block) {
  return `\`\`\`${block.lang}\n${block.content}\n\`\`\``;
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

function addCellIds(cells) {
  return cells.map((cell, index) => ({
    ...cell,
    id: crypto
      .createHash('sha256')
      .update(`${index}\0${cell.cell_type}\0${cell.source.join('')}`)
      .digest('hex')
      .slice(0, 12),
  }));
}

/** Jupyter expects source as an array of lines, each ending with \n except the last */
function sourceLines(text) {
  const lines = text.split('\n');
  return lines.map((line, i) => (i < lines.length - 1 ? line + '\n' : line));
}

function buildNotebook(cells, title, trackName, source) {
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
        version: '3.12',
      },
      title,
      valkey_for_ai: {
        generated_by: 'build-notebooks.js',
        source: path.posix.join('content', trackName, source),
      },
    },
    cells: addCellIds(cells),
  };
}

function loadMeta(trackDir, issues) {
  const metaPath = path.join(trackDir, 'meta.json');
  if (!fs.existsSync(metaPath)) {
    issues.push(`Missing metadata: ${path.relative(__dirname, metaPath)}`);
    return null;
  }

  try {
    const meta = JSON.parse(fs.readFileSync(metaPath, 'utf8'));
    if (typeof meta.trackName !== 'string' || !meta.trackName.trim()) {
      issues.push(`Invalid metadata: ${path.relative(__dirname, metaPath)} must contain a trackName`);
    }
    if (!Array.isArray(meta.cookbooks)) {
      issues.push(`Invalid metadata: ${path.relative(__dirname, metaPath)} must contain a cookbooks array`);
      return null;
    }
    return meta;
  } catch (error) {
    issues.push(`Invalid JSON: ${path.relative(__dirname, metaPath)} (${error.message})`);
    return null;
  }
}

function createBuildPlan(trackNames) {
  const issues = [];
  const plan = [];

  for (const trackName of trackNames) {
    const trackDir = path.join(CONTENT_DIR, trackName);
    const meta = loadMeta(trackDir, issues);
    if (!meta) continue;

    const listedSources = new Set();

    for (const cookbook of meta.cookbooks) {
      if (!cookbook || typeof cookbook !== 'object') {
        issues.push(`Invalid cookbook entry in content/${trackName}/meta.json`);
        continue;
      }

      if (typeof cookbook.source !== 'string' ||
          path.basename(cookbook.source) !== cookbook.source ||
          !cookbook.source.endsWith('.md')) {
        issues.push(`Invalid cookbook source in content/${trackName}/meta.json: ${cookbook.source}`);
        continue;
      }

      for (const field of ['title', 'difficulty', 'time']) {
        if (typeof cookbook[field] !== 'string' || !cookbook[field].trim()) {
          issues.push(`Missing ${field} for content/${trackName}/${cookbook.source}`);
        }
      }

      if (listedSources.has(cookbook.source)) {
        issues.push(`Duplicate cookbook source in content/${trackName}/meta.json: ${cookbook.source}`);
        continue;
      }
      listedSources.add(cookbook.source);

      const mdPath = path.join(trackDir, cookbook.source);
      if (!fs.existsSync(mdPath)) {
        issues.push(`Missing cookbook source: ${path.relative(__dirname, mdPath)}`);
        continue;
      }

      const outName = cookbook.source.replace(/\.md$/, '.ipynb');
      plan.push({
        cookbook,
        meta,
        mdPath,
        outPath: path.join(OUTPUT_DIR, trackName, outName),
        trackName,
      });
    }

    const unlistedMarkdown = fs.readdirSync(trackDir)
      .filter(file => file.endsWith('.md') && !listedSources.has(file))
      .sort();
    for (const file of unlistedMarkdown) {
      issues.push(`Cookbook is not listed in content/${trackName}/meta.json: ${file}`);
    }
  }

  if (issues.length > 0) {
    throw new Error(issues.join('\n'));
  }

  return plan;
}

function renderNotebook(item) {
  const md = fs.readFileSync(item.mdPath, 'utf8');
  const titleMd = `# ${item.cookbook.title}\n\n**${item.cookbook.difficulty}** · ~${item.cookbook.time} · ${item.meta.trackName}`;
  const blocks = splitMarkdown(md, path.relative(__dirname, item.mdPath));
  const cells = [markdownCell(titleMd), ...blocksToNotebookCells(blocks)];
  const notebook = buildNotebook(
    cells,
    item.cookbook.title,
    item.trackName,
    item.cookbook.source
  );

  return `${JSON.stringify(notebook, null, 1)}\n`;
}

function findNotebookFiles(rootDir) {
  if (!fs.existsSync(rootDir)) return [];

  const files = [];
  for (const entry of fs.readdirSync(rootDir, { withFileTypes: true })) {
    const entryPath = path.join(rootDir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === '.ipynb_checkpoints') continue;
      files.push(...findNotebookFiles(entryPath));
    } else if (entry.isFile() && entry.name.endsWith('.ipynb')) {
      files.push(entryPath);
    }
  }
  return files;
}

function syncNotebooks(plan, scopeDir, checkOnly) {
  const issues = [];
  const expectedPaths = new Set(plan.map(item => item.outPath));
  const renderedPlan = plan.map(item => ({
    ...item,
    expected: renderNotebook(item),
  }));
  let written = 0;

  for (const item of renderedPlan) {
    const relativeOutPath = path.relative(__dirname, item.outPath);

    if (checkOnly) {
      if (!fs.existsSync(item.outPath)) {
        issues.push(`Missing notebook: ${relativeOutPath}`);
      } else if (fs.readFileSync(item.outPath, 'utf8') !== item.expected) {
        issues.push(`Stale notebook: ${relativeOutPath}`);
      }
      continue;
    }

    fs.mkdirSync(path.dirname(item.outPath), { recursive: true });
    if (!fs.existsSync(item.outPath) || fs.readFileSync(item.outPath, 'utf8') !== item.expected) {
      fs.writeFileSync(item.outPath, item.expected);
      written++;
    }
  }

  const orphaned = findNotebookFiles(scopeDir)
    .filter(file => !expectedPaths.has(file))
    .sort();

  for (const file of orphaned) {
    const relativePath = path.relative(__dirname, file);
    if (checkOnly) {
      issues.push(`Orphan notebook: ${relativePath}`);
    } else {
      fs.unlinkSync(file);
      console.log(`  🗑️  Removed ${relativePath}`);
    }
  }

  if (issues.length > 0) {
    throw new Error(issues.join('\n'));
  }

  return { removed: orphaned.length, written };
}

function getTrackNames(targetTrack) {
  if (targetTrack) {
    if (path.basename(targetTrack) !== targetTrack) {
      throw new Error(`Invalid track name: ${targetTrack}`);
    }

    const trackDir = path.join(CONTENT_DIR, targetTrack);
    if (!fs.existsSync(trackDir) || !fs.statSync(trackDir).isDirectory()) {
      throw new Error(`Track not found: content/${targetTrack}`);
    }
    return [targetTrack];
  }

  return fs.readdirSync(CONTENT_DIR)
    .filter(entry => fs.statSync(path.join(CONTENT_DIR, entry)).isDirectory())
    .sort();
}

function parseArgs(args) {
  const supportedFlags = new Set(['--check']);
  const unknownFlags = args.filter(arg => arg.startsWith('--') && !supportedFlags.has(arg));
  const positional = args.filter(arg => !arg.startsWith('--'));

  if (unknownFlags.length > 0 || positional.length > 1) {
    throw new Error('Usage: node build-notebooks.js [--check] [track-name]');
  }

  return {
    checkOnly: args.includes('--check'),
    targetTrack: positional[0],
  };
}

function main() {
  const { checkOnly, targetTrack } = parseArgs(process.argv.slice(2));
  const trackNames = getTrackNames(targetTrack);
  const plan = createBuildPlan(trackNames);
  const scopeDir = targetTrack ? path.join(OUTPUT_DIR, targetTrack) : OUTPUT_DIR;

  if (checkOnly) {
    console.log(`🔎 Checking ${plan.length} notebook(s) across ${trackNames.length} track(s)...`);
  } else {
    console.log(`🔨 Building ${plan.length} notebook(s) across ${trackNames.length} track(s)...`);
  }

  const result = syncNotebooks(plan, scopeDir, checkOnly);

  if (checkOnly) {
    console.log('✅ Every cookbook has a current Jupyter notebook.');
  } else {
    console.log(`✨ Done. Updated ${result.written}, removed ${result.removed}.`);
  }
}

try {
  main();
} catch (error) {
  console.error('❌ Notebook build failed:');
  for (const line of error.message.split('\n')) {
    console.error(`  ${line}`);
  }
  process.exitCode = 1;
}
