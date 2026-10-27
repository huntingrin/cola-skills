#!/usr/bin/env node
// Check whether a promotion link is reachable and which attribution parameters
// it carries. This does not log in, does not use cookies, and does not prove the
// coupon is still available.
//
// Usage:
//   node check_link.mjs "<url>"
//
// Prints JSON:
//   { ok, status, finalHost, finalPath, loginWrapper, params, warnings }

const url = process.argv[2]

function fail(message) {
  console.error(`check_link: ${message}`)
  process.exit(2)
}

if (!url) fail('usage: node check_link.mjs "<url>"')
if (!/^https?:\/\//i.test(url)) fail('url must start with http:// or https://')
if (/[\r\n\t]/.test(url)) fail('url must not contain whitespace or newlines')

function collectParams(input) {
  const keys = new Set()
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
    return { outer: parsed, inner, keys }
  } catch {
    return { outer: null, inner: null, keys }
  }
}

const parsed = collectParams(url)
if (!parsed.outer) fail('url could not be parsed')

const warnings = []
const outerSid = parsed.outer.searchParams.get('sid')
const innerSid = parsed.inner?.searchParams.get('sid') ?? null
if (outerSid === '123456' || innerSid === '123456') {
  warnings.push('sid_placeholder')
}
const hasAttribution =
  parsed.keys.has('sid') ||
  parsed.keys.has('scene') ||
  parsed.keys.has('spm') ||
  parsed.keys.has('o2i_shortlink') ||
  [...parsed.keys].some((key) => key.startsWith('utm_'))
if (!hasAttribution) warnings.push('no_attribution_params')

const loginWrapper =
  parsed.outer.pathname.includes('/login') ||
  parsed.outer.searchParams.has('redirect')

const controller = new AbortController()
const timer = setTimeout(() => controller.abort(), 15000)

try {
  const response = await fetch(url, {
    method: 'GET',
    redirect: 'follow',
    signal: controller.signal,
    headers: {
      'user-agent':
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
      accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }
  })
  const finalUrl = response.url || url
  const final = new URL(finalUrl)
  if (response.status >= 400) warnings.push('http_error')
  if (final.pathname.includes('/login')) warnings.push('login_page')

  // The body is irrelevant; release it so the process can exit promptly.
  await response.body?.cancel()

  console.log(
    JSON.stringify(
      {
        ok: response.status >= 200 && response.status < 400,
        status: response.status,
        finalHost: final.hostname,
        finalPath: final.pathname,
        loginWrapper,
        params: [...parsed.keys].sort(),
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
        loginWrapper,
        params: [...parsed.keys].sort(),
        warnings: [...warnings, 'network_error'],
        error: error?.name === 'AbortError' ? 'timeout' : String(error?.message ?? error)
      },
      null,
      2
    )
  )
} finally {
  clearTimeout(timer)
}
