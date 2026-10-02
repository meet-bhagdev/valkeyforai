#!/usr/bin/env node
/**
 * dev.js - Development server with live reload
 *
 * Watches content/*.md and meta.json for changes, rebuilds the affected track,
 * and triggers a browser refresh via browser-sync.
 *
 * Usage: node dev.js
 */

const { execFileSync } = require('child_process');
const path = require('path');
const chokidar = require('chokidar');
const browserSync = require('browser-sync').create();

function runBuild(script, track) {
  const args = track ? [script, track] : [script];
  execFileSync(process.execPath, args, { stdio: 'inherit' });
}

// Initial full build
console.log('🔨 Running initial build...\n');
runBuild('build.js');
runBuild('build-notebooks.js');

// Start browser-sync
browserSync.init({
  server: '.',
  files: [
    'cookbooks/**/*.html',
    'cookbooks/cookbook.css',
    'index.html',
    'styles.css',
  ],
  open: false,
  notify: false,
  ui: false,
});

console.log('\n👀 Watching content/ for changes...\n');

// Watch markdown + meta.json, rebuild the affected track on change
chokidar
  .watch('content/**/*.{md,json}', { ignoreInitial: true })
  .on('all', (event, filePath) => {
    if (!['add', 'change', 'unlink'].includes(event)) return;
    const track = filePath.split(path.sep)[1]; // content/<track>/file.md
    console.log(`\n📝 Changed: ${filePath}`);
    console.log(`🔨 Rebuilding: ${track}`);
    try {
      runBuild('build.js', track);
      runBuild('build-notebooks.js', track);
    } catch (e) {
      console.error(`❌ Build failed for ${track}`);
    }
  });
