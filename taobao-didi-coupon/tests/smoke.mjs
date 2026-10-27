#!/usr/bin/env node
// Minimal smoke test for the two bundled scripts. No network required.
// Run from the skill root: node tests/smoke.mjs

import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'taobao-didi-coupon-'))

function run(args) {
  return spawnSync(process.execPath, args, { cwd: root, encoding: 'utf8' })
}

function ok(condition, message) {
  if (!condition) {
    console.error(`SMOKE FAIL: ${message}`)
    process.exit(1)
  }
}

try {
  const qrPath = path.join(tmp, 'qr.png')
  const qr = run([
    path.join(root, 'scripts/make_qr.mjs'),
    'https://example.com/smoke?x=1',
    qrPath
  ])
  ok(qr.status === 0, `make_qr exit ${qr.status}: ${qr.stderr}`)
  ok(qr.stdout.includes('VERIFY: png-ok'), 'make_qr did not print VERIFY: png-ok')
  ok(fs.existsSync(qrPath), 'QR file missing')
  const png = fs.readFileSync(qrPath)
  ok(png.length > 100, 'QR file too small')
  ok(png.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'not a PNG')

  const bad = run([path.join(root, 'scripts/check_link.mjs'), 'ftp://example.com'])
  ok(bad.status === 2, 'check_link should reject non-http(s) URLs')
  ok(bad.stderr.includes('url must start'), 'check_link rejection message missing')

  const check = run([path.join(root, 'scripts/check_link.mjs'), 'http://127.0.0.1:1/'])
  ok(check.status === 0, 'check_link should return a JSON diagnosis')
  const parsed = JSON.parse(check.stdout)
  ok(parsed.ok === false, 'unreachable URL should be ok:false')
  ok(Array.isArray(parsed.warnings), 'check_link warnings missing')

  console.log('SMOKE: ok')
} finally {
  fs.rmSync(tmp, { recursive: true, force: true })
}
