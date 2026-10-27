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

  // resolve_config: the saved project is named with a middle dot and no
  // "二维码", which a literal name lookup used to miss.
  const home = path.join(tmp, 'home')
  const project = path.join(home, 'outputs', '淘宝闪购·滴滴红包码')
  const current = path.join(tmp, 'current')
  fs.mkdirSync(path.join(project, '交付物'), { recursive: true })
  fs.mkdirSync(current, { recursive: true })
  fs.mkdirSync(path.join(home, 'projects'), { recursive: true })
  fs.writeFileSync(path.join(project, '交付物', '淘宝闪购-红包二维码.png'), 'png')
  fs.writeFileSync(path.join(project, '交付物', '滴滴-红包二维码.png'), 'png')
  fs.writeFileSync(path.join(project, '红包配置.json'), JSON.stringify({
    淘宝闪购: {
      url: 'https://example.com/taobao?scene=abc',
      qrcode: '交付物/淘宝闪购-红包二维码.png',
      qrcode_url: 'https://example.com/taobao?scene=abc'
    },
    滴滴出行: {
      url: 'https://example.com/didi?source_id=abc',
      qrcode: '交付物/滴滴-红包二维码.png',
      qrcode_url: 'https://example.com/didi?source_id=abc'
    }
  }, null, 2))
  fs.writeFileSync(path.join(home, 'projects', 'project.json'), JSON.stringify({
    projects: [{
      id: 'smoke',
      name: '淘宝闪购·滴滴红包码',
      workspaceDir: project
    }]
  }))

  const resolved = run([
    path.join(root, 'scripts/resolve_config.mjs'),
    '--current', current,
    '--cola-home', home,
    '--root', path.join(home, 'outputs'),
    '--no-global'
  ])
  ok(resolved.status === 0, `resolve_config exit ${resolved.status}: ${resolved.stderr}`)
  const saved = JSON.parse(resolved.stdout)
  ok(saved.usable === true, 'resolve_config should find both platforms')
  ok(saved.missing.length === 0, 'resolve_config should report no missing platform')
  ok(saved.platforms['淘宝闪购'].url.includes('scene=abc'), 'taobao URL missing')
  ok(saved.platforms['滴滴出行'].url.includes('source_id=abc'), 'didi URL missing')
  ok(saved.platforms['淘宝闪购'].qrcodeExists === true, 'taobao QR should exist')
  ok(saved.best.name === '淘宝闪购·滴滴红包码', 'resolve_config should find the middle-dot name')

  const home2 = path.join(tmp, 'home2')
  const onlyTaobao = path.join(home2, 'outputs', '淘宝闪购-红包二维码')
  fs.mkdirSync(onlyTaobao, { recursive: true })
  fs.writeFileSync(path.join(onlyTaobao, '红包配置.json'), JSON.stringify({
    淘宝闪购: { url: 'https://example.com/only-taobao' }
  }))
  const partial = JSON.parse(run([
    path.join(root, 'scripts/resolve_config.mjs'),
    '--current', current,
    '--cola-home', home2,
    '--root', path.join(home2, 'outputs'),
    '--no-global'
  ]).stdout)
  ok(partial.usable === false, 'partial config should not be usable')
  ok(partial.missing.includes('滴滴出行'), 'partial config should report missing didi')

  const broken = path.join(home2, 'outputs', '滴滴红包码-坏配置')
  fs.mkdirSync(broken, { recursive: true })
  fs.writeFileSync(path.join(broken, '红包配置.json'), '{not json')
  const brokenRun = run([
    path.join(root, 'scripts/resolve_config.mjs'),
    '--current', current,
    '--cola-home', home2,
    '--root', path.join(home2, 'outputs'),
    '--no-global'
  ])
  ok(brokenRun.status === 0, 'malformed config should not crash resolve_config')
  ok(JSON.parse(brokenRun.stdout).candidates.some((item) => item.error), 'malformed config should be reported')

  console.log('SMOKE: ok')
} finally {
  fs.rmSync(tmp, { recursive: true, force: true })
}
