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
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
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
                                 headers={'Content-Type': 'application/json', 'Referer': final}, method='POST')
    with urllib.request.urlopen(req, timeout=30) as response:
        result = json.load(response)
    if str(result.get('code')) != '200' or not isinstance(result.get('data'), dict):
        raise ValueError('Offer service did not return a redemption link; do not retry issuance blindly')
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


def click_guard(snapshot, label, intent, free=False):
    text = visible_text(snapshot)
    if classify(snapshot)['state'] == 'login_required':
        raise ValueError('User must complete login; no automated credential actions')
    if intent == 'navigate':
        if re.search(r'取消|Cancel|购买|Buy|确认|Confirm|兑换|Redeem|免费试用|Free Trial', label, re.I) or label in ['订阅', 'Subscribe', '续订', 'Resubscribe', '继续', 'Continue']:
            raise ValueError('Use the appropriate authorized claim/cancel intent for this control')
    elif intent == 'claim':
        if re.search(r'你的订阅即将到期|优惠结束后继续订阅|已过期|has expired', text, re.I):
            raise ValueError('Expired/cancelled plan is not evidence of a new free offer')
        if not free or not re.search(r'免费|free|¥\s*0(?:\.00)?\b|RMB\s*0\b', text, re.I):
            raise ValueError('An observed free offer and --free-offer-confirmed are required')
        if re.search(r'升级|Upgrade|家人共享|Family', label, re.I):
            raise ValueError('Do not change plans through this workflow')
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
        snap = native('snapshot', args.app)
        click_guard(snap, args.label, args.intent, args.free_offer_confirmed)
        result = native('click', args.app, args.label, args.role)
        result['verified'] = False  # A dispatched click is not a business outcome.
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'error': str(exc), 'verified': False}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
