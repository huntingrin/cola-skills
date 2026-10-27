#!/usr/bin/env node
// Check whether a promotion link is reachable and which attribution parameters
// it carries. This does not log in, does not use cookies, and does not prove the
// coupon is still available.
//
// Usage:
//   node check_link.mjs "<url>"
//
// Prints JSON:
//   { ok, status, finalHost, finalPath, loginWrapper, metaRedirect, params, warnings }

const url = process.argv[2]

function fail(message) {
  console.error(`check_link: ${message}`)
  process.exit(2)
}

if (!url) fail('usage: node check_link.mjs "<url>"')
if (!/^https?:\/\//i.test(url)) fail('url must start with http:// or https://')
if (/[\r\n\t]/.test(url)) fail('url must not contain whitespace or newlines')

const MOBILE_UA =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'

function collectParams(input, keys) {
  let inner = null
  try {
    const parsed = new URL(input)
    for (const key of parsed.searchParams.keys()) keys.add(key)
    const redirect = parsed.searchParams.get('redirect')
    if (redirect) {
      try {
        inner = new URL(redirect)
        for (const key of inner.searchParams.keys()) keys.add(key)
      } catch {
        // The redirect value is not a URL; keep the outer params only.
      }
    }
    return { outer: parsed, inner }
  } catch {
    return { outer: null, inner: null }
  }
}

const keys = new Set()
const parsed = collectParams(url, keys)
if (!parsed.outer) fail('url could not be parsed')

function findMetaRefresh(html, baseUrl) {
  const tags = html.match(/<meta\b[^>]*>/gi) || []
  for (const tag of tags) {
    if (!/http-equiv\s*=\s*["']?refresh["']?/i.test(tag)) continue
    const content =
      tag.match(/content\s*=\s*["']([^"']*)["']/i)?.[1] ??
      tag.match(/content\s*=\s*([^\s>]+)/i)?.[1]
    if (!content) continue
    const target = content.match(/url\s*=\s*['"]?([^'";>]+)/i)?.[1]
    if (!target) continue
    try {
      return new URL(target.trim(), baseUrl)
    } catch {
      return null
    }
  }
  return null
}

async function readCapped(response, maxBytes = 64 * 1024) {
  if (!response.body) return ''
  const reader = response.body.getReader()
  const chunks = []
  let total = 0
  try {
    while (total < maxBytes) {
      const { done, value } = await reader.read()
      if (done) break
      chunks.push(Buffer.from(value))
      total += value.length
    }
  } finally {
    await reader.cancel().catch(() => {})
  }
  return Buffer.concat(chunks).subarray(0, maxBytes).toString('utf8')
}

const controller = new AbortController()
const timer = setTimeout(() => controller.abort(), 15000)

try {
  const response = await fetch(url, {
    method: 'GET',
    redirect: 'follow',
    signal: controller.signal,
    headers: {
      'user-agent': MOBILE_UA,
      accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
  })
  let finalUrl = response.url || url
  let status = response.status
  const contentType = response.headers.get('content-type') || ''
  let metaRedirect = null

  if (response.status < 400 && /text\/html|text\/plain/i.test(contentType)) {
    const html = await readCapped(response)
    metaRedirect = findMetaRefresh(html, finalUrl)
  } else {
    await response.body?.cancel()
  }

  if (metaRedirect && /^https?:$/i.test(metaRedirect.protocol) && metaRedirect.href !== finalUrl) {
    const metaResponse = await fetch(metaRedirect.href, {
      method: 'GET',
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'user-agent': MOBILE_UA,
        accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
      }
    })
    status = metaResponse.status
    finalUrl = metaResponse.url || metaRedirect.href
    await metaResponse.body?.cancel()
  }

  const final = new URL(finalUrl)
  collectParams(finalUrl, keys)
  if (metaRedirect) collectParams(metaRedirect.href, keys)

  const warnings = []
  let sid = parsed.outer.searchParams.get('sid')
  if (!sid && parsed.inner) sid = parsed.inner.searchParams.get('sid')
  if (!sid) sid = new URL(finalUrl).searchParams.get('sid')
  if (sid === '123456') warnings.push('sid_placeholder')

  const hasAttribution =
    keys.has('sid') ||
    keys.has('scene') ||
    keys.has('spm') ||
    keys.has('o2i_shortlink') ||
    keys.has('source_id') ||
    keys.has('channel_id') ||
    keys.has('entrance_channel') ||
    keys.has('dchn') ||
    [...keys].some((key) => key.startsWith('utm_'))
  if (!hasAttribution) warnings.push('no_attribution_params')
  if (status >= 400) warnings.push('http_error')
  if (parsed.outer.pathname.includes('/login') || parsed.outer.searchParams.has('redirect')) {
    warnings.push('login_page')
  } else if (final.pathname.includes('/login')) {
    warnings.push('login_page')
  }

  console.log(
    JSON.stringify(
      {
        ok: status >= 200 && status < 400,
        status,
        finalHost: final.hostname,
        finalPath: final.pathname,
        loginWrapper:
          parsed.outer.pathname.includes('/login') ||
          parsed.outer.searchParams.has('redirect'),
        metaRedirect: Boolean(metaRedirect),
        params: [...keys].sort(),
        warnings
      },
      null,
      2
    )
  )
} catch (error) {
  console.log(
    JSON.stringify(
      {
        ok: false,
        status: null,
        finalHost: parsed.outer.hostname,
        finalPath: parsed.outer.pathname,
        loginWrapper:
          parsed.outer.pathname.includes('/login') ||
          parsed.outer.searchParams.has('redirect'),
        metaRedirect: false,
        params: [...keys].sort(),
        warnings: ['network_error'],
        error: error?.name === 'AbortError' ? 'timeout' : String(error?.message ?? error)
      },
      null,
      2
    )
  )
} finally {
  clearTimeout(timer)
}
