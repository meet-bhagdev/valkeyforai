#!/usr/bin/env node
/**
 * dev.js - Development server with live reload
 *
 * Watches content/*.md and meta.json for changes, rebuilds the affected track,
 * and triggers a browser refresh via browser-sync.
 *
 * Usage: node dev.js
 */

const { execSync } = require('child_process');
const path = require('path');
const chokidar = require('chokidar');
const browserSync = require('browser-sync').create();

// Initial full build
console.log('🔨 Running initial build...\n');
execSync('node build.js', { stdio: 'inherit' });

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
  .on('change', (filePath) => {
    const track = filePath.split(path.sep)[1]; // content/<track>/file.md
    console.log(`\n📝 Changed: ${filePath}`);
    console.log(`🔨 Rebuilding: ${track}`);
    try {
      execSync(`node build.js ${track}`, { stdio: 'inherit' });
    } catch (e) {
      console.error(`❌ Build failed for ${track}`);
    }
  });
