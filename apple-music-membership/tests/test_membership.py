"""Offline pure-function/mock tests; never open apps or change memberships."""
import datetime as dt
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'music_membership.py'
SPEC = importlib.util.spec_from_file_location('music_membership_under_test', SCRIPT)
membership = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(membership)
TODAY = dt.date(2026, 10, 27)
# Synthetic fixture only; this is not a user-issued redemption code.
OFFICIAL = 'https://music.apple.com/redeem/?code=TEST-ONLY&ctx=Music'


def snapshot(text='', extra=None, **flags):
    return {'nodes': [{'role': 'AXStaticText', 'text': text}] + (extra or []), **flags}


def button(label):
    return {'role': 'AXButton', 'name': label, 'enabled': True}


class MembershipTests(unittest.TestCase):
    def setUp(self):
        # Date-sensitive classification uses a fixed reference date, not the clock.
        original_expiry = membership.expiry
        patcher = mock.patch.object(membership, 'expiry',
                                    side_effect=lambda text, today=None: original_expiry(text, today or TODAY))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_official_url(self):
        self.assertEqual(membership.apple_url(OFFICIAL), OFFICIAL)

    def test_alternate_official_path(self):
        url = OFFICIAL.replace('/redeem/', '/includes/commerce/redeem')
        self.assertEqual(membership.apple_url(url), url)

    def test_reject_wrong_host_and_non_https(self):
        for url in [OFFICIAL.replace('music.apple.com', 'music.apple.com.example.org'),
                    OFFICIAL.replace('https:', 'http:'),
                    OFFICIAL.replace('music.apple.com', 'example.org')]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                membership.apple_url(url)

    def test_reject_credentials(self):
        with self.assertRaises(ValueError):
            membership.apple_url(OFFICIAL.replace('music.apple.com', 'user:secret@music.apple.com'))

    def test_reject_missing_duplicate_or_invalid_code(self):
        for query in ['ctx=Music', 'code=TEST-ONLY&code=OTHER-TEST', 'code=!', 'code=abc']:
            with self.subTest(query=query), self.assertRaises(ValueError):
                membership.apple_url('https://music.apple.com/redeem/?' + query)

    def test_reject_wrong_path_or_context(self):
        for url in [OFFICIAL.replace('/redeem/', '/subscribe/'), OFFICIAL.replace('ctx=Music', 'ctx=Apps')]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                membership.apple_url(url)

    def test_native_protocol_conversion_is_pure(self):
        self.assertEqual(membership.native_redemption_url(OFFICIAL),
                         'musics://music.apple.com/redeem/?code=TEST-ONLY&ctx=Music')

    def test_official_request_does_not_access_network(self):
        with mock.patch.object(membership.urllib.request, 'urlopen') as network:
            result = membership.request_offer(OFFICIAL)
        network.assert_not_called()
        self.assertEqual(result['kind'], 'apple_redemption')

    def test_campaign_inspection_is_mocked_get_only(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.url = 'https://plus.migu.cn/c/0fxt2u?group_id=fixture'
        response.read.return_value = (b'<script>window.pageId="123";</script>'
            b'<a data-diversion=\'{"eventType":"APPLE_MUSIC_EXCHANGE","forceLogin":false}\'></a>')
        with mock.patch.object(membership.urllib.request, 'urlopen', return_value=response) as network:
            result = membership.request_offer(membership.DEFAULT_OFFER, issue=False)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(network.call_args.args[0].get_method(), 'GET')
        self.assertFalse(result['redemption_requested'])
        self.assertTrue(result['exchange_available'])

    def test_campaign_login_guard_no_post(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.url = membership.DEFAULT_OFFER
        response.read.return_value = b'<a data-diversion=\'{"eventType":"APPLE_MUSIC_EXCHANGE","forceLogin":true}\'></a>'
        with mock.patch.object(membership.urllib.request, 'urlopen', return_value=response) as network:
            with self.assertRaises(ValueError):
                membership.request_offer(membership.DEFAULT_OFFER, issue=True)
        self.assertEqual(network.call_count, 1)
        self.assertEqual(network.call_args.args[0].get_method(), 'GET')

    def test_redemption_post_includes_campaign_user_agent(self):
        campaign = mock.MagicMock()
        campaign.__enter__.return_value = campaign
        campaign.url = membership.DEFAULT_OFFER + '?group_id=fixture'
        campaign.read.return_value = (b'<script>window.pageId="123";</script>'
            b'<a data-diversion=\'{"eventType":"APPLE_MUSIC_EXCHANGE","forceLogin":false}\'></a>')
        expected_ua = 'Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/605.1.15'

        def service(request, **kwargs):
            if request.get_method() == 'GET':
                return campaign
            response = mock.MagicMock()
            response.__enter__.return_value = response
            # Model the observed service rejecting issuance without the browser UA.
            data = {'code': '200', 'data': {'redirectUrl': OFFICIAL}} if request.get_header('User-agent') == expected_ua else {'code': '400'}
            response.read.return_value = json.dumps(data).encode()
            return response

        with mock.patch.object(membership.urllib.request, 'urlopen', side_effect=service) as network:
            result = membership.request_offer(membership.DEFAULT_OFFER, issue=True)
        self.assertEqual(result['redemption_url'], OFFICIAL)
        self.assertEqual([call.args[0].get_method() for call in network.call_args_list], ['GET', 'POST'])

    def test_paid_offer_guard(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('Apple Music 每月 12 元'), '订阅', 'claim', free=True)

    def test_free_offer_requires_flag(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('Apple Music 免费 2 个月'), '兑换', 'claim', free=False)

    def test_free_offer_allowed_after_confirmation(self):
        self.assertTrue(membership.click_guard(snapshot('Apple Music 免费 2 个月'), '兑换', 'claim', free=True))

    def test_no_family_upgrade(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('Apple Music 免费'), '升级 Family', 'claim', free=True)

    def test_login_guard(self):
        snap = snapshot('Apple Music 免费，需要登录 Apple')
        self.assertEqual(membership.classify(snap)['state'], 'login_required')
        with self.assertRaises(ValueError):
            membership.click_guard(snap, '兑换', 'claim', free=True)

    def test_secure_field_login_guard(self):
        snap = snapshot('Apple Music', [{'role': 'AXTextField', 'subrole': 'AXSecureTextField'}])
        self.assertEqual(membership.classify(snap)['state'], 'login_required')

    def test_renewal_disabled_requires_all_evidence(self):
        snap = snapshot('Apple Music 你的订阅即将到期，将于12月27日到期', [button('订阅')])
        result = membership.classify(snap)
        self.assertEqual(result['state'], 'renewal_disabled')
        self.assertEqual(result['expires_on'], '2026-12-27')

    def test_missing_subscribe_or_date_is_unknown(self):
        for snap in [snapshot('Apple Music 将于12月27日到期'),
                     snapshot('Apple Music 你的订阅即将到期', [button('订阅')])]:
            with self.subTest(snap=snap):
                self.assertEqual(membership.classify(snap)['state'], 'needs_inspection')

    def test_cancellable_overrides_ending(self):
        snap = snapshot('Apple Music 将于12月27日到期', [button('订阅'), button('取消订阅')])
        self.assertEqual(membership.classify(snap)['state'], 'cancellable')

    def test_cancellable_retains_access(self):
        snap = snapshot('Apple Music 如果现在取消，你仍可在12月27日前访问此订阅', [button('取消订阅')])
        result = membership.classify(snap)
        self.assertEqual(result['state'], 'cancellable')
        self.assertTrue(result['retains_access'])

    def test_unknown_non_music(self):
        self.assertEqual(membership.classify(snapshot('其他订阅 将于12月27日到期', [button('订阅')]))['state'],
                         'needs_inspection')

    def test_truncated_never_final(self):
        snap = snapshot('Apple Music 将于12月27日到期', [button('订阅')], truncated=True)
        self.assertEqual(membership.classify(snap)['state'], 'needs_inspection')

    def test_loading(self):
        snap = snapshot('Apple Music', [{'role': 'AXBusyIndicator'}])
        self.assertEqual(membership.classify(snap)['state'], 'loading')

    def test_expiry_year_rollover(self):
        self.assertEqual(membership.expiry('将于1月2日到期', dt.date(2026, 12, 30)), '2027-01-02')

    def test_explicit_year_and_invalid_date(self):
        self.assertEqual(membership.expiry('将于2027年1月2日到期', TODAY), '2027-01-02')
        self.assertIsNone(membership.expiry('将于2月30日到期', TODAY))

    def test_unrelated_date_is_not_expiry(self):
        self.assertIsNone(membership.expiry('今天10月27日 Apple Music', TODAY))

    def test_cancel_guard_wrong_subscription(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('其他订阅'), '取消订阅', 'cancel')

    def test_cancel_guard_immediate_loss(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('Apple Music 立即失去权益'), '确认取消', 'cancel')

    def test_cancel_guard_already_cancelled(self):
        with self.assertRaises(ValueError):
            membership.click_guard(snapshot('Apple Music 你的订阅即将到期'), '确认取消', 'cancel')

    def test_navigation_cannot_bypass_claim_or_cancel(self):
        for label in ['兑换', '取消订阅', '订阅', '继续']:
            with self.subTest(label=label), self.assertRaises(ValueError):
                membership.click_guard(snapshot('Apple Music'), label, 'navigate')

    def test_cli_claim_authorization_guard_has_no_side_effects(self):
        with mock.patch.object(membership.sys, 'argv', ['music_membership.py', 'redeem-link']), \
             mock.patch.object(membership, 'request_offer') as request:
            with self.assertRaises(ValueError):
                membership.main()
        request.assert_not_called()

    def test_cli_cancel_authorization_guard_has_no_native_call(self):
        argv = ['music_membership.py', 'click', '--label', '取消订阅', '--role', 'AXButton', '--intent', 'cancel']
        with mock.patch.object(membership.sys, 'argv', argv), mock.patch.object(membership, 'native') as native:
            with self.assertRaises(ValueError):
                membership.main()
        native.assert_not_called()

    def test_cli_status_uses_mock_snapshot_only(self):
        snap = snapshot('Apple Music 将于12月27日到期', [button('订阅')])
        with mock.patch.object(membership.sys, 'argv', ['music_membership.py', 'status', '--app', 'App Store']), \
             mock.patch.object(membership, 'native', return_value=snap) as native, \
             mock.patch('sys.stdout', new_callable=io.StringIO) as output:
            membership.main()
        native.assert_called_once_with('snapshot', 'App Store')
        self.assertEqual(json.loads(output.getvalue())['state'], 'renewal_disabled')


if __name__ == '__main__':
    unittest.main()
