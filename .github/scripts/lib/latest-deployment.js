#!/usr/bin/env node
// Prints "<id> <status>" of the most recent deployment in `railway deployment list
// --json` output: the first object (depth-first, like find-status.js) carrying both a
// string `id` and a string `status`. Prints "UNKNOWN UNKNOWN" when the JSON doesn't
// parse or holds no such object. Used by wait-railway-deployment.sh to tell *this*
// job's deployment apart from the one that was already live before `railway up`.
//
// Usage: node latest-deployment.js '<json-string>'
'use strict';

let data;
try {
  data = JSON.parse(process.argv[2]);
} catch {
  console.log('UNKNOWN UNKNOWN');
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
  if (typeof obj.id === 'string' && typeof obj.status === 'string') return obj;
  for (const key of Object.keys(obj)) {
    const r = find(obj[key]);
    if (r) return r;
  }
  return null;
}

const d = find(data);
console.log(d ? `${d.id} ${d.status}` : 'UNKNOWN UNKNOWN');
