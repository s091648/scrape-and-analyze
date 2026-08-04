#!/usr/bin/env node
// Recursively searches parsed JSON for a `status` string field. Used by
// check-staging-deployments.sh's find_status() to parse `railway deployment
// list --json` / `railway status --json` output, whose exact shape isn't
// officially documented — this is resilient to minor schema differences:
// `railway deployment list --service X` is already scoped to one service,
// so a deployment's own `id` field is a *deployment* ID, not the service
// ID — there's nothing to match against. Just returns the first (most
// recent) `status` string found anywhere in the tree, or "UNKNOWN".
//
// Usage: node find-status.js '<json-string>'
'use strict';

let data;
try {
  data = JSON.parse(process.argv[2]);
} catch {
  console.log('UNKNOWN');
  process.exit(0);
}

function find(obj) {
  if (!obj || typeof obj !== 'object') return null;
  if (Array.isArray(obj)) {
    for (const item of obj) {
      const r = find(item);
      if (r) return r;
    }
    return null;
  }
  if (typeof obj.status === 'string') return obj.status;
  for (const key of Object.keys(obj)) {
    const r = find(obj[key]);
    if (r) return r;
  }
  return null;
}

console.log(find(data) || 'UNKNOWN');
