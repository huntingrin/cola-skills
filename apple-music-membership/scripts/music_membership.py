#!/usr/bin/env python3
"""Apple Music offer + native macOS UI helpers (stdlib only; no credential handling)."""
import argparse
import datetime as dt
import html.parser
import json
import platform
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15'
DEFAULT_OFFER = 'https://plus.migu.cn/c/0fxt2u'
MIGU_ENDPOINT = 'https://plus.migu.cn/whalecallback/delivery/pagevisit/buildAppleMusicAuthRedirectUrl'


class OfferParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.diversions = []

    def handle_starttag(self, tag, attrs):
        diversion = dict(attrs).get('data-diversion')
        if diversion:
            try:
                self.diversions.append(json.loads(diversion))
            except (ValueError, TypeError):
                pass


def apple_url(url):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'music.apple.com' or parsed.username or parsed.password:
        raise ValueError('Expected official HTTPS Apple Music redemption URL')
    if parsed.path.rstrip('/') not in ['/redeem', '/includes/commerce/redeem']:
        raise ValueError('Expected redemption path')
    params = urllib.parse.parse_qs(parsed.query)
    if len(params.get('code', [])) != 1 or not re.fullmatch(r'[A-Za-z0-9-]{4,128}', params['code'][0]):
        raise ValueError('Invalid or missing offer code')
    if params.get('ctx', ['Music']) != ['Music']:
        raise ValueError('Not a Music offer')
    return url


def native_redemption_url(url):
    apple_url(url)
    return 'musics://music.apple.com/redeem/?' + urllib.parse.urlsplit(url).query


def request_offer(url, issue=False):
    """GET inspects the reusable campaign; POST is an explicit request for a redemption link."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.hostname == 'music.apple.com':
        return {'kind': 'apple_redemption', 'redemption_url': apple_url(url)}
    if parsed.scheme != 'https' or parsed.hostname != 'plus.migu.cn' or parsed.username or parsed.password:
        raise ValueError('Only the supplied Migu campaign or official Apple redemption link is supported')
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15'})
    with urllib.request.urlopen(request, timeout=30) as response:
        final = response.url
        if urllib.parse.urlsplit(final).hostname != 'plus.migu.cn':
            raise ValueError('Unexpected campaign redirect; inspect it instead of sending a request')
        body = response.read(2_000_000).decode('utf-8')
    parser = OfferParser()
    parser.feed(body)
    configs = [d for d in parser.diversions if d.get('eventType') == 'APPLE_MUSIC_EXCHANGE']
    if not configs:
        raise ValueError('Campaign no longer exposes the observed Apple Music offer')
    if any(d.get('forceLogin') for d in configs):
        raise ValueError('Campaign now requires Migu login; use the official campaign UI')
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(final).query)
    match = re.search(r"window\.pageId\s*=\s*['\"](\d+)['\"]", body)
    payload = {'pageId': match[1] if match else query.get('page_id', [''])[0],
               'groupId': query.get('group_id', [''])[0],
               'channelId': query.get('channelid', [''])[0],
               'tCode': query.get('T', [''])[0][:6],
               'campsegId': query.get('campseg_id', [''])[0]}
    if not payload['pageId'] or not payload['groupId']:
        raise ValueError('Campaign parameters missing')
    if not issue:
        return {'kind': 'reusable_campaign', 'campaign_url': url, 'resolved_url': final,
                'page_id': payload['pageId'], 'exchange_available': True, 'redemption_requested': False}
    req = urllib.request.Request(MIGU_ENDPOINT, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json', 'Referer': final,
                                          'User-Agent': UA},
                                 method='POST')
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if str(result.get('code')) != '200' or not isinstance(result.get('data'), dict):
        raise ValueError(
            'Migu returned no redemption link (code=%r, message=%r). Do not retry blindly: '
            'run `preflight` first, then re-check the campaign with `inspect-offer`.'
            % (result.get('code'), result.get('message')))
    link = apple_url(result['data'].get('redirectUrl', ''))
    return {'kind': 'apple_redemption', 'redemption_url': link}


def native(action, app='Music', *extra):
    if platform.system() != 'Darwin':
        raise ValueError('This skill requires macOS')
    run = subprocess.run(['osascript', '-l', 'JavaScript', str(ROOT / 'native-ui.js'), action, app, *extra],
                         text=True, capture_output=True, timeout=55)
    if run.returncode:
        raise RuntimeError(run.stderr.strip() or 'Native UI operation failed')
    return json.loads(run.stdout)


def parse_proxy(text):
    """Pure parser for the `scutil --proxy` dump."""
    services = []
    for key in ('HTTP', 'HTTPS', 'SOCKS'):
        enabled = re.search(rf'{key}Enable\s*:\s*(\d)', text or '')
        if enabled and enabled.group(1) == '1':
            host = re.search(rf'{key}Proxy\s*:\s*(\S+)', text)
            port = re.search(rf'{key}Port\s*:\s*(\d+)', text)
            services.append({'service': key, 'host': host.group(1) if host else '',
                             'port': int(port.group(1)) if port else None})
    return {'known': True, 'enabled': bool(services), 'services': services}


def system_proxy():
    """Read the macOS system proxy. Apple apps honour it; curl/python urllib do not."""
    try:
        out = subprocess.run(['scutil', '--proxy'], text=True, capture_output=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return {'known': False}
    return parse_proxy(out)


def reachable(url, timeout=12):
    started = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read(2048)
            return {'ok': True, 'status': response.status, 'seconds': round(time.monotonic() - started, 2)}
    except Exception as exc:  # noqa: BLE001 - a probe reports, it never raises
        return {'ok': False, 'error': f'{type(exc).__name__}: {str(exc)[:120]}',
                'seconds': round(time.monotonic() - started, 2),
                'note': 'urllib ignores the macOS system proxy, so passing here does not clear a blocked Apple app'}


def preflight(app='Music'):
    """Environment gate before redemption: permissions, system proxy, reachability, live page."""
    report = {'macos': platform.system() == 'Darwin'}
    if not report['macos']:
        report['ok'] = False
        report['hint'] = 'This skill only runs on macOS.'
        return report
    report.update(native('doctor', app))
    report['proxy'] = system_proxy()
    report['apple_reachable'] = reachable('https://music.apple.com/')
    try:
        native('activate', app)
        page = native('page-health', app)
    except Exception as exc:  # noqa: BLE001
        page = {'status': 'unknown', 'error': str(exc)[:160]}
    report['page'] = page
    hints = []
    status = page.get('status')
    if page.get('errorText'):
        hints.append(f"App 页面报错：{page['errorText']}")
    if status in ('error', 'blank') and report['proxy'].get('enabled'):
        services = ', '.join(f"{s['service']} {s.get('host')}:{s.get('port')}" for s in report['proxy']['services'])
        hints.append(f'系统代理正开着（{services}）。Apple 的应用常因此加载不出来，先请用户关掉代理再重试。')
    elif status in ('error', 'blank'):
        hints.append('页面空白或报错，但没有系统代理：退出并重开 App 一次；仍然空白就停下来，不要反复点菜单。')
    elif status == 'ok' and report['proxy'].get('enabled'):
        hints.append('代理开着但页面渲染正常，可以继续，留意后续弹窗。')
    report['ok'] = status == 'ok' and report.get('accessibility') is True
    report['hint'] = ' '.join(hints) or '环境正常，可以继续。'
    return report


MANUAL_ENTRY_LABELS = ('手动输入兑换码', 'Enter Code Manually', 'Enter Code Manually…')

SHEET_ALERT = re.compile(
    r'上限|已达|已达到|无效|过期|不可用|失败|错误|无法|不支持'
    r'|limit|already|invalid|expired|unavailable|cannot|can\'t|not available', re.I)


def sheet_alert(sheet):
    """Surface an in-sheet error/limit message so a silent no-op is reported instead of retried."""
    hits = [t for t in sheet.get('texts', []) if t and SHEET_ALERT.search(t)]
    return hits[0] if hits else None


def open_redeem(app='Music', timeout_ms=6000):
    """Open the code sheet, reusing an already-open one.

    A presented sheet is modal: the Account menu item stays disabled while it is up, so a blind
    menu click finds nothing. Always look for an existing sheet first.
    """
    native('activate', app)
    sheet = native('sheet', app)
    reused = bool(sheet.get('exists'))
    clicked = None
    if not reused:
        clicked = native('redeem-menu', app)
        sheet = native('wait', app, 'sheet', str(timeout_ms))
    if not sheet.get('exists'):
        raise ValueError(
            f"点击 {(clicked or {}).get('clicked')!r} 之后兑换弹窗没有出现。先跑 `preflight`：页面空白或系统代理开着是常见原因。不要循环重复点菜单。")
    manual = [b for b in sheet.get('buttons', []) if b in MANUAL_ENTRY_LABELS]
    if not manual and not sheet.get('fields'):
        raise ValueError(f"兑换弹窗打开了，但既没有手动输入按钮也没有兑换码输入框：{sheet.get('buttons')}")
    return {'menu': clicked, 'reused_open_sheet': reused, 'manual_entry_label': manual[0] if manual else None,
            'sheet': sheet}


def enter_code(code, app='Music'):
    """Type the code with real keystrokes: setting AXValue does not fire the web form."""
    if not re.fullmatch(r'[A-Za-z0-9]{10,20}', code or ''):
        raise ValueError('兑换码应为 10-20 位字母或数字')
    return native('type', app, code)


def visible_text(snapshot):
    return '\n'.join(str(n.get(k, '')) for n in snapshot.get('nodes', [])
                     for k in ('name', 'description', 'text') if n.get(k))


def expiry(text, today=None):
    today = today or dt.date.today()
    # Restrict dates to expiry language; do not select a renewal or unrelated page date.
    match = re.search(r'(?:将于|可在|若要在|有效期至|到期[：:]?\s*)(?:(\d{4})年)?(\d{1,2})月(\d{1,2})日', text)
    if not match:
        return None
    year = int(match[1]) if match[1] else today.year
    try:
        date = dt.date(year, int(match[2]), int(match[3]))
        if not match[1] and date < today:
            date = dt.date(year + 1, date.month, date.day)
        return date.isoformat()
    except ValueError:
        return None


def classify(snapshot):
    text = visible_text(snapshot)
    if snapshot.get('truncated'):
        return {'state': 'needs_inspection', 'reason': 'UI truncated'}
    if any(n.get('subrole') == 'AXSecureTextField' for n in snapshot.get('nodes', [])) or re.search(r'需要登录|登录 Apple|Sign In|密码|验证码', text):
        return {'state': 'login_required'}
    if any(n.get('role') == 'AXBusyIndicator' for n in snapshot.get('nodes', [])):
        return {'state': 'loading'}
    if re.search(r'已兑换优惠|Offer redeemed|优惠已兑换', text):
        plan = re.search(r'(个人|学生|家庭|Individual|Student|Family)', text)
        period = re.search(r'(\d+)\s*(个月|月|month)', text)
        return {'state': 'redeemed', 'plan': plan.group(1) if plan else None,
                'free_period': period.group(0) if period else None,
                'evidence': 'App sheet shows the offer redeemed'}
    if 'Apple Music' not in text:
        return {'state': 'needs_inspection', 'reason': 'Not Apple Music subscription details'}
    has_cancel = bool(re.search(r'取消订阅|Cancel Subscription|取消免费试用|Cancel Free Trial', text))
    ending = '你的订阅即将到期' in text or bool(re.search(r'将于.{0,25}到期|Your subscription will expire|Expires on', text))
    date = expiry(text)
    renew_button = any(n.get('role') == 'AXButton' and (n.get('name') in ['订阅', 'Subscribe', '续订', 'Resubscribe'] or n.get('description') in ['订阅', 'Subscribe', '续订', 'Resubscribe']) for n in snapshot.get('nodes', []))
    if ending and renew_button and date and not has_cancel:
        return {'state': 'renewal_disabled', 'expires_on': date,
                'evidence': 'Explicit expiry text plus subscribe/resubscribe button; no cancel control'}
    if has_cancel:
        return {'state': 'cancellable', 'expires_on_if_cancelled': date,
                'retains_access': bool(re.search(r'如果现在取消，你仍可在\d{1,2}月\d{1,2}日前访问此订阅|you will still have access', text, re.I))}
    return {'state': 'needs_inspection', 'reason': 'Final renewal state not yet proven'}


def with_sheet_text(snapshot, app):
    """Merge the live sheet's texts/buttons into a snapshot: offer terms live there, not in the window."""
    try:
        sheet = native('sheet', app)
    except Exception:  # noqa: BLE001 - a missing sheet must not break the guard
        return snapshot
    merged = dict(snapshot)
    if not sheet.get('exists'):
        return merged
    merged['sheet'] = sheet
    nodes = list(snapshot.get('nodes', []))
    nodes += [{'role': 'AXStaticText', 'text': t} for t in sheet.get('texts', [])]
    nodes += [{'role': 'AXButton', 'name': b} for b in sheet.get('buttons', [])]
    nodes += [{'role': 'AXTextField', 'name': f.get('label', ''), 'text': 'code' if f.get('length') else ''}
              for f in sheet.get('fields', [])]
    merged['nodes'] = nodes
    return merged


def click_guard(snapshot, label, intent, free=False):
    text = visible_text(snapshot)
    sheet = snapshot.get('sheet') or {}
    code_sheet = bool(sheet.get('fields')) or any(b in ('Code', '验证码') for b in sheet.get('buttons', []))
    if classify(snapshot)['state'] == 'login_required':
        raise ValueError('User must complete login; no automated credential actions')
    if intent == 'navigate':
        # Two-step reality: "Redeem" only reveals the offer terms; "Confirm" is the commit.
        if re.search(r'取消|Cancel|购买|Buy|确认|Confirm|免费试用|Free Trial', label, re.I) or label in ['订阅', 'Subscribe', '续订', 'Resubscribe', '继续', 'Continue']:
            raise ValueError('Use the appropriate authorized claim/cancel intent for this control')
        if re.search(r'兑换|Redeem', label, re.I) and not code_sheet:
            raise ValueError('Submit-redeem needs an open code sheet; use the authorized claim intent')
    elif intent == 'claim':
        if re.search(r'升级|Upgrade|家人共享|Family', label, re.I):
            raise ValueError('Do not change plans through this workflow')
        if not code_sheet and re.search(r'你的订阅即将到期|优惠结束后继续订阅|已过期|has expired', text, re.I):
            raise ValueError('Expired/cancelled plan is not evidence of a new free offer')
        if not free or not re.search(r'免费|free|¥\s*0(?:\.00)?\b|RMB\s*0\b', text, re.I):
            raise ValueError('An observed free offer and --free-offer-confirmed are required')
    elif intent == 'cancel':
        if 'Apple Music' not in text:
            raise ValueError('Cancellation target must be observed Apple Music')
        if not re.search(r'取消|Cancel|确认|Confirm', label, re.I):
            raise ValueError('Not an observed cancellation/confirmation control')
        if not re.search(r'取消.*(?:订阅|试用)|cancel.*(?:subscription|trial)', text, re.I):
            raise ValueError('Current UI is not a subscription cancellation screen')
        if re.search(r'立即失去|立即结束|立即停止|immediately lose|lose access immediately', text, re.I):
            raise ValueError('Immediate loss of access: obtain explicit user confirmation and use native UI manually')
        if re.search(r'订阅即将到期|优惠结束后继续订阅', text):
            raise ValueError('Already cancelled; do not click resubscribe')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor')
    commands.add_parser('open-music')
    commands.add_parser('open-subscriptions')
    commands.add_parser('account-settings')
    sub = commands.add_parser('preflight')
    sub.add_argument('--app', choices=['Music', 'App Store'], default='Music')
    for name in ['page-health', 'read-sheet']:
        sub = commands.add_parser(name)
        sub.add_argument('--app', choices=['Music', 'App Store'], default='Music')
    sub = commands.add_parser('open-redeem')
    sub.add_argument('--timeout-ms', type=int, default=6000)
    sub = commands.add_parser('wait-sheet')
    sub.add_argument('--contains', default='')
    sub.add_argument('--app', choices=['Music', 'App Store'], default='Music')
    sub.add_argument('--timeout-ms', type=int, default=8000)
    sub = commands.add_parser('type-code')
    sub.add_argument('--code', required=True)
    for name in ['snapshot', 'status']:
        sub = commands.add_parser(name)
        sub.add_argument('--app', choices=['Music', 'App Store'], default='Music')
    for name in ['inspect-offer', 'redeem-link']:
        sub = commands.add_parser(name)
        sub.add_argument('--url', default=DEFAULT_OFFER)
        if name == 'redeem-link':
            sub.add_argument('--authorize', action='store_true', help='User has requested this membership claim')
    sub = commands.add_parser('open-redemption')
    sub.add_argument('--url', required=True)
    sub = commands.add_parser('decode-qr')
    sub.add_argument('path', nargs='?', default=str(ROOT.parent / 'assets' / '活动二维码.jpg'))
    sub = commands.add_parser('click')
    sub.add_argument('--app', choices=['Music', 'App Store'], default='Music')
    sub.add_argument('--label', required=True)
    sub.add_argument('--role', required=True)
    sub.add_argument('--intent', choices=['navigate', 'claim', 'cancel'], default='navigate')
    sub.add_argument('--authorize', action='store_true')
    sub.add_argument('--free-offer-confirmed', action='store_true')
    sub.add_argument('--scope', choices=['auto', 'sheet', 'window'], default='auto')
    args = parser.parse_args()
    if args.command == 'doctor':
        result = {'macos': platform.system() == 'Darwin', 'accessibility': False}
        if result['macos']:
            result.update(native('doctor'))
    elif args.command == 'open-music':
        result = native('activate')
    elif args.command == 'open-subscriptions':
        if platform.system() != 'Darwin':
            raise ValueError('macOS required')
        subprocess.run(['open', 'macappstore://apps.apple.com/account/subscriptions'], check=True, timeout=15)
        result = {'opened': 'App Store subscriptions', 'verified': False}
    elif args.command == 'account-settings':
        result = native('account-settings')
    elif args.command in ['snapshot', 'status']:
        snap = native('snapshot', args.app)
        result = snap if args.command == 'snapshot' else classify(snap)
    elif args.command in ['inspect-offer', 'redeem-link']:
        if args.command == 'redeem-link' and not args.authorize:
            raise ValueError('--authorize required before requesting a redemption link')
        result = request_offer(args.url, issue=args.command == 'redeem-link')
    elif args.command == 'open-redemption':
        if platform.system() != 'Darwin':
            raise ValueError('macOS required')
        link = native_redemption_url(args.url)
        subprocess.run(['open', '-a', 'Music', link], check=True, timeout=15)
        result = {'opened': 'Music redemption', 'verified': False}
    elif args.command == 'preflight':
        result = preflight(args.app)
    elif args.command == 'page-health':
        result = native('page-health', args.app)
    elif args.command == 'read-sheet':
        result = native('sheet', args.app)
        alert = sheet_alert(result)
        result['alert'] = alert
        if alert:
            result['next_step'] = ('兑换被拒（上面那条原文）。同一 Apple 账户的兑换次数有上限，'
                                   '不要换码重试；改为核验已有权益或让用户确认。')
    elif args.command == 'wait-sheet':
        result = native('wait', args.app, args.contains or 'sheet', str(args.timeout_ms))
    elif args.command == 'open-redeem':
        result = open_redeem('Music', args.timeout_ms)
    elif args.command == 'type-code':
        result = enter_code(args.code)
    elif args.command == 'decode-qr':
        if platform.system() != 'Darwin':
            raise ValueError('macOS required')
        path = Path(args.path).expanduser().resolve(strict=True)
        run = subprocess.run(['swift', '-module-cache-path', '/tmp/apple-music-skill-swift-cache',
                              str(ROOT / 'decode_qr.swift'), str(path)], capture_output=True, text=True, timeout=90)
        if run.returncode:
            raise RuntimeError(run.stderr.strip())
        result = json.loads(run.stdout)
    elif args.command == 'click':
        if args.intent != 'navigate' and not args.authorize:
            raise ValueError('--authorize required for claim/cancellation actions')
        snap = {'nodes': [], 'windows': []} if args.scope == 'sheet' else native('snapshot', args.app)
        if args.scope != 'window':
            snap = with_sheet_text(snap, args.app)
        click_guard(snap, args.label, args.intent, args.free_offer_confirmed)
        result = native('click', args.app, args.label, args.role, args.scope)
        result['verified'] = False  # A dispatched click is not a business outcome.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'verified': False}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
