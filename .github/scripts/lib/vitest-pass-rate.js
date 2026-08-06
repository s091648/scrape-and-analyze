#!/usr/bin/env node
// Reads vitest's --reporter=json output (test-results.json, resolved
// relative to cwd) and prints "<passed> <total>" space-separated. Used by
// compute-vitest-pass-rate.sh. On any read/parse failure, prints "0 0" —
// same fallback behavior as the inline `|| echo 0` script this replaced.
//
// Usage: node vitest-pass-rate.js   (run with cwd=frontend/)
'use strict';
const path = require('node:path');

let passed = 0;
let total = 0;
try {
  const r = require(path.resolve(process.cwd(), 'test-results.json'));
  passed = r.numPassedTests ?? 0;
  total = passed + (r.numFailedTests ?? 0);
} catch {
  // leave at 0/0
}

console.log(`${passed} ${total}`);
