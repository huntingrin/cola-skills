#!/usr/bin/env node
// Find the saved 红包配置.json for the coupon project.
//
// The fixed project has been created under several near-identical names:
//   淘宝闪购 · 滴滴红包二维码
//   淘宝闪购滴滴红包码
//   淘宝闪购·滴滴红包码
// A literal name lookup misses the last one, so match on normalized names
// instead. Only inspect the current project, the Cola project registry, and
// `outputs/*` folders whose names look like a coupon project. Never walk the
// whole home directory.
//
// Usage:
//   node resolve_config.mjs [--current <dir>] [--cola-home <dir>] [--root <dir>]...
//
// Prints JSON:
//   { usable, missing, platforms, best, candidates, conflicts }
//
// Exit code 0 even when nothing is found; 2 only for bad arguments.

import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

const args = process.argv.slice(2)
let current = process.cwd()
let noGlobal = false
const homes = []
const extraRoots = []

function usage(message) {
  if (message) console.error(`resolve_config: ${message}`)
  console.error('usage: node resolve_config.mjs [--current <dir>] [--cola-home <dir>] [--root <dir>]... [--no-global]')
  process.exit(2)
}

for (let i = 0; i < args.length; i += 1) {
  const arg = args[i]
  if (arg === '--current') {
    const value = args[++i]
    if (!value) usage('--current needs a directory')
    current = path.resolve(value)
  } else if (arg === '--cola-home') {
    const value = args[++i]
    if (!value) usage('--cola-home needs a directory')
    homes.push(path.resolve(value))
  } else if (arg === '--root') {
    const value = args[++i]
    if (!value) usage('--root needs a directory')
    extraRoots.push(path.resolve(value))
  } else if (arg === '--no-global') {
    noGlobal = true
  } else if (arg === '--help' || arg === '-h') {
    usage()
  } else {
    usage(`unknown argument: ${arg}`)
  }
}

const home = os.homedir()
const defaultHomes = [
  path.join(home, '.cola'),
  path.join(home, '.cola-prod-dev'),
  path.join(home, '.cola-dev')
]
const allHomes = homes.length ? homes : defaultHomes
const outputsRoots = [
  current,
  ...extraRoots,
  ...(noGlobal ? [] : [
    path.join(home, 'cola', 'outputs'),
    path.join(home, 'cola-prod-dev', 'outputs')
  ]),
  ...allHomes.map((item) => path.join(item, 'outputs'))
]

function normalize(value) {
  return String(value || '')
    .normalize('NFC')
    .replace(/[\s·•・\-—_/\\()（）[\]【】,，.。:：'"“”]/g, '')
    .toLowerCase()
}

const TAOBAO = /淘宝闪购|饿了么|eleme/
const DIDI = /滴滴|didi/
const COUPON = /红包|优惠券|领券|券包|二维码/

function looksLikeCouponProject(name) {
  const key = normalize(name)
  if (!COUPON.test(key)) return false
  return TAOBAO.test(key) || DIDI.test(key)
}

function canonicalPlatform(key) {
  const normalized = normalize(key)
  if (TAOBAO.test(normalized)) return '淘宝闪购'
  if (DIDI.test(normalized)) return '滴滴出行'
  return null
}

function isHttpUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value) && !/[\r\n\t]/.test(value)
}

function statSafe(file) {
  try {
    return fs.statSync(file)
  } catch {
    return null
  }
}

function addUnique(list, value) {
  if (!value) return
  let key
  try {
    key = fs.realpathSync.native(value)
  } catch {
    key = path.resolve(value)
  }
  if (!list.some((item) => item.key === key)) list.push({ key, value })
}

const dirs = []
const registryNames = new Map()

function addDir(dir, name, source) {
  const before = dirs.length
  addUnique(dirs, dir)
  if (dirs.length > before && name) registryNames.set(path.resolve(dir), name)
  void source
}

// 1. The current project always wins, even if its folder name is opaque.
addDir(current, path.basename(current), 'current')

// 2. Cola project registry: only entries that look like this coupon project.
for (const colaHome of allHomes) {
  for (const file of [
    path.join(colaHome, 'projects', 'project.json'),
    path.join(colaHome, 'projects', 'projects.json')
  ]) {
    let parsed
    try {
      parsed = JSON.parse(fs.readFileSync(file, 'utf8'))
    } catch {
      continue
    }
    const entries = Array.isArray(parsed) ? parsed : parsed.projects
    if (!Array.isArray(entries)) continue
    for (const entry of entries) {
      if (!entry || typeof entry !== 'object') continue
      const name = entry.name || ''
      const workspace = entry.workspaceDir || entry.workspace || ''
      if (!workspace || !path.isAbsolute(workspace)) continue
      if (!looksLikeCouponProject(name) && !looksLikeCouponProject(path.basename(workspace))) continue
      addDir(workspace, name || path.basename(workspace), 'registry')
    }
  }
}

// 3. outputs folders with a coupon-like name, one level deep only.
for (const root of outputsRoots) {
  let entries
  try {
    entries = fs.readdirSync(root, { withFileTypes: true })
  } catch {
    continue
  }
  for (const entry of entries) {
    if (!entry.isDirectory()) continue
    if (!looksLikeCouponProject(entry.name)) continue
    addDir(path.join(root, entry.name), entry.name, 'outputs')
  }
}

const candidates = []
const seenConfigs = new Set()

for (const dir of dirs) {
  const configPath = path.join(dir.value, '红包配置.json')
  let realConfig
  try {
    realConfig = fs.realpathSync.native(configPath)
  } catch {
    continue
  }
  if (seenConfigs.has(realConfig)) continue
  seenConfigs.add(realConfig)

  const candidate = {
    dir: dir.value,
    name: registryNames.get(path.resolve(dir.value)) || path.basename(dir.value),
    configPath,
    platforms: {},
    invalid: [],
    error: null,
    mtime: 0
  }

  let parsed
  try {
    const stat = fs.statSync(configPath)
    candidate.mtime = stat.mtimeMs
    parsed = JSON.parse(fs.readFileSync(configPath, 'utf8'))
  } catch (error) {
    candidate.error = error instanceof Error ? error.message : String(error)
    candidates.push(candidate)
    continue
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    candidate.error = 'config must be a JSON object'
    candidates.push(candidate)
    continue
  }

  for (const [key, value] of Object.entries(parsed)) {
    const platform = canonicalPlatform(key)
    if (!platform) continue
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      candidate.invalid.push(`${key}: entry must be an object`)
      continue
    }
    if (!isHttpUrl(value.url)) {
      candidate.invalid.push(`${key}: url must be an http(s) URL`)
      continue
    }
    if (candidate.platforms[platform]) continue

    const qrcode = typeof value.qrcode === 'string' && value.qrcode
      ? path.resolve(candidate.dir, value.qrcode)
      : null
    const qrcodeStat = qrcode ? statSafe(qrcode) : null

    candidate.platforms[platform] = {
      url: value.url,
      qrcode: qrcodeStat && qrcodeStat.isFile() && qrcodeStat.size > 0 ? qrcode : null,
      qrcode_url: typeof value.qrcode_url === 'string' ? value.qrcode_url : null,
      qrcodeExists: Boolean(qrcodeStat && qrcodeStat.isFile() && qrcodeStat.size > 0)
    }
  }

  candidates.push(candidate)
}

function dirPriority(dir) {
  const resolved = path.resolve(dir)
  if (resolved === path.resolve(current)) return 100
  if (resolved.startsWith(path.join(home, 'cola', 'outputs'))) return 50
  if (resolved.startsWith(path.join(home, '.cola', 'outputs'))) return 40
  if (resolved.startsWith(path.join(home, 'cola-prod-dev', 'outputs'))) return 10
  if (resolved.startsWith(path.join(home, '.cola-prod-dev', 'outputs'))) return 5
  return 0
}

function score(candidate) {
  const platforms = Object.values(candidate.platforms)
  let value = platforms.length * 30
  if (candidate.platforms['淘宝闪购'] && candidate.platforms['滴滴出行']) value += 100
  value += platforms.filter((item) => item.qrcodeExists).length * 5
  value += dirPriority(candidate.dir)
  const ageDays = candidate.mtime ? (Date.now() - candidate.mtime) / 86400000 : 999
  value += Math.max(0, 1 - ageDays / 365)
  return value
}

for (const candidate of candidates) candidate.score = score(candidate)
candidates.sort((a, b) => b.score - a.score)

// Merge per platform: current project first, then the highest-scoring config.
const platforms = {}
const sources = {}
for (const name of ['淘宝闪购', '滴滴出行']) {
  const options = candidates
    .filter((candidate) => candidate.platforms[name])
    .map((candidate) => ({
      dir: candidate.dir,
      name: candidate.name,
      configPath: candidate.configPath,
      score: candidate.score,
      isCurrent: path.resolve(candidate.dir) === path.resolve(current),
      ...candidate.platforms[name]
    }))
    .sort((a, b) => Number(b.isCurrent) - Number(a.isCurrent) || b.score - a.score)

  if (!options.length) continue
  const chosen = options[0]
  platforms[name] = {
    url: chosen.url,
    qrcode: chosen.qrcode,
    qrcode_url: chosen.qrcode_url,
    qrcodeExists: chosen.qrcodeExists,
    sourceDir: chosen.dir,
    sourceName: chosen.name,
    configPath: chosen.configPath,
    alternatives: options.length - 1
  }
  sources[name] = { dir: chosen.dir, configPath: chosen.configPath, isCurrent: chosen.isCurrent }
}

const missing = ['淘宝闪购', '滴滴出行'].filter((name) => !platforms[name])
const conflicts = []
for (const name of Object.keys(platforms)) {
  const urls = [...new Set(
    candidates
      .map((candidate) => candidate.platforms[name]?.url)
      .filter(Boolean)
  )]
  if (urls.length > 1) conflicts.push({ platform: name, urls })
}

const best = candidates.find((candidate) => !candidate.error) || null

console.log(JSON.stringify({
  usable: missing.length === 0,
  missing,
  platforms,
  sources,
  best: best ? {
    dir: best.dir,
    name: best.name,
    configPath: best.configPath,
    score: best.score
  } : null,
  candidates: candidates.map((candidate) => ({
    dir: candidate.dir,
    name: candidate.name,
    configPath: candidate.configPath,
    score: candidate.score,
    error: candidate.error,
    invalid: candidate.invalid,
    platforms: Object.fromEntries(
      Object.entries(candidate.platforms).map(([name, value]) => [name, {
        url: value.url,
        qrcode: value.qrcode,
        qrcodeExists: value.qrcodeExists
      }])
    )
  })),
  conflicts
}, null, 2))
