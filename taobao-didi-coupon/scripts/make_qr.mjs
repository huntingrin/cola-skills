#!/usr/bin/env node
// Generate a QR code PNG from a URL with no network access and no external
// dependencies. The QR matrix comes from the vendored qrcode-generator (MIT);
// the PNG container is written here with Node's zlib.
//
// Usage:
//   node make_qr.mjs "<url>" "<output.png>"
//
// Prints:
//   QR: <absolute path>
//   MODULES: <n>
//   SIZE: <pixels>

import fs from 'node:fs'
import path from 'node:path'
import zlib from 'node:zlib'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const qrcode = require('./vendor/qrcode.js')

const [url, outArg] = process.argv.slice(2)

function fail(message) {
  console.error(`make_qr: ${message}`)
  process.exit(2)
}

if (!url || !outArg) {
  fail('usage: node make_qr.mjs "<url>" "<output.png>"')
}
if (!/^https?:\/\//i.test(url)) {
  fail('url must start with http:// or https://')
}
if (/[\r\n\t]/.test(url)) {
  fail('url must not contain whitespace or newlines')
}
if (url.length > 4096) {
  fail('url is too long (max 4096 characters)')
}

const out = path.resolve(outArg)
fs.mkdirSync(path.dirname(out), { recursive: true })

// Type 0 = auto-detect the smallest version that fits; M = ~15% recovery.
const qr = qrcode(0, 'M')
qr.addData(url, 'Byte')
qr.make()

const modules = qr.getModuleCount()
const cell = 8
const margin = 4
const size = (modules + margin * 2) * cell
const raw = Buffer.alloc((size + 1) * size, 255)

for (let y = 0; y < size; y += 1) {
  const row = y * (size + 1)
  raw[row] = 0 // PNG filter: none
  const my = Math.floor(y / cell) - margin
  for (let x = 0; x < size; x += 1) {
    const mx = Math.floor(x / cell) - margin
    const dark =
      mx >= 0 && my >= 0 && mx < modules && my < modules && qr.isDark(my, mx)
    raw[row + 1 + x] = dark ? 0 : 255
  }
}

const crcTable = (() => {
  const table = new Uint32Array(256)
  for (let n = 0; n < 256; n += 1) {
    let c = n
    for (let k = 0; k < 8; k += 1) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1
    }
    table[n] = c >>> 0
  }
  return table
})()

function crc32(buffer) {
  let c = 0xffffffff
  for (let i = 0; i < buffer.length; i += 1) {
    c = crcTable[(c ^ buffer[i]) & 0xff] ^ (c >>> 8)
  }
  return (c ^ 0xffffffff) >>> 0
}

function chunk(type, data) {
  const typeBuffer = Buffer.from(type, 'ascii')
  const length = Buffer.alloc(4)
  length.writeUInt32BE(data.length, 0)
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuffer, data])), 0)
  return Buffer.concat([length, typeBuffer, data, crc])
}

const signature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
const ihdr = Buffer.alloc(13)
ihdr.writeUInt32BE(size, 0)
ihdr.writeUInt32BE(size, 4)
ihdr[8] = 8 // bit depth
ihdr[9] = 0 // grayscale
ihdr[10] = 0 // compression
ihdr[11] = 0 // filter
ihdr[12] = 0 // interlace

const png = Buffer.concat([
  signature,
  chunk('IHDR', ihdr),
  chunk('IDAT', zlib.deflateSync(raw, { level: 9 })),
  chunk('IEND', Buffer.alloc(0))
])

fs.writeFileSync(out, png)

// Read the file back and compare the inflated scanlines with what we intended
// to write. This proves the PNG container and compression are intact; it does
// not prove a phone camera can decode the QR, so never describe it as a scan.
const written = fs.readFileSync(out)
if (written.subarray(0, 8).compare(signature) !== 0) {
  fail('verification failed: PNG signature')
}
let offset = 8
let width = 0
let height = 0
const idat = []
while (offset < written.length) {
  const length = written.readUInt32BE(offset)
  const type = written.toString('ascii', offset + 4, offset + 8)
  const data = written.subarray(offset + 8, offset + 8 + length)
  if (type === 'IHDR') {
    width = data.readUInt32BE(0)
    height = data.readUInt32BE(4)
  }
  if (type === 'IDAT') idat.push(data)
  offset += 12 + length
}
if (width !== size || height !== size) {
  fail('verification failed: PNG dimensions')
}
const inflated = zlib.inflateSync(Buffer.concat(idat))
if (inflated.length !== raw.length || Buffer.compare(inflated, raw) !== 0) {
  fail('verification failed: PNG pixels')
}

console.log(`QR: ${out}`)
console.log(`MODULES: ${modules}`)
console.log(`SIZE: ${size}`)
console.log(`BYTES: ${png.length}`)
console.log('VERIFY: png-ok')
