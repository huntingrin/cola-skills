#!/usr/bin/env python3
"""Offline checks for packaging, discoverability, references and context size.

These do not simulate an agent or prove that it follows business instructions.
Browser extraction behavior is tested separately with Node, without a live site.
"""

import re
import subprocess
import sys
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parents[1]
ENTRY = "SKILL.md"
# Include the entry itself: counting only child files hid the largest fixed cost.
READ_PATHS = {
    "联通话费方法": (["skills/cucc-points-redeem/references/phonefee-text.md"], 3000),
    # Includes same-page recovery when the login URL lands on the homepage.
    "移动": (["skills/cmcc-points-redeem/GUIDE.md"], 4100),
    "联通查询": (["skills/cucc-points-redeem/GUIDE.md"], 4300),
    "联通选品": (["skills/cucc-points-redeem/GUIDE.md",
                 "skills/cucc-points-redeem/references/redemption-types.md"], 5600),
    # Conservatively count the complete adapter even though only its mobile section is needed.
    "电信直达登录": (["skills/ct-points-redeem/GUIDE.md"], 5100),
    "电信登录后兑换适配": (["skills/ct-points-redeem/GUIDE.md", "references/browser.md"], 7800),
}
EXAMPLE_NUMBERS = {"13800138000", "13900139000", "13900000000"}
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
MOBILE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")


def markdown_files():
    return sorted(p for p in ROOT.rglob("*.md") if ".git" not in p.parts)


class SkillBundle(unittest.TestCase):
    def test_relative_links_resolve(self):
        broken = []
        for path in markdown_files():
            for target in LINK.findall(path.read_text(encoding="utf-8")):
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                if not resolved.is_relative_to(ROOT) or not resolved.is_file():
                    broken.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(broken, [])

    def test_entry_links_to_all_carrier_guides(self):
        targets = set(LINK.findall((ROOT / ENTRY).read_text(encoding="utf-8")))
        self.assertTrue({
            f"skills/{carrier}-points-redeem/GUIDE.md"
            for carrier in ("cmcc", "cucc", "ct")
        }.issubset(targets))

    def test_only_one_discoverable_skill(self):
        exposed = sorted(str(p.relative_to(ROOT)) for p in ROOT.rglob("SKILL.md")
                         if ".git" not in p.parts)
        self.assertEqual(exposed, [ENTRY])

    def test_frontmatter_identifies_each_document(self):
        paths = [ROOT / ENTRY, *(ROOT / "skills").glob("*/GUIDE.md")]
        self.assertEqual(len(paths), 4)
        for path in paths:
            text = path.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("---\n"), path)
            metadata = text.split("---", 2)[1]
            expected_name = "carrier-points-redeem" if path.name == ENTRY else path.parent.name
            self.assertRegex(metadata, rf"(?m)^name: {re.escape(expected_name)}$")
            description = re.search(r"(?m)^description:\s*(.+)$", metadata)
            self.assertIsNotNone(description, path)
            self.assertLessEqual(len(description.group(1)), 1024)

    def test_context_budgets(self):
        entry_size = len((ROOT / ENTRY).read_text(encoding="utf-8"))
        self.assertLessEqual(entry_size, 2500)
        for name, (paths, budget) in READ_PATHS.items():
            with self.subTest(name=name):
                size = entry_size + sum(len((ROOT / p).read_text(encoding="utf-8"))
                                        for p in paths)
                self.assertLessEqual(size, budget)

    def test_docs_have_no_unmasked_nonexample_numbers(self):
        found = []
        for path in markdown_files():
            for number in MOBILE.findall(path.read_text(encoding="utf-8")):
                if number not in EXAMPLE_NUMBERS:
                    found.append(f"{path.relative_to(ROOT)}: {number[:3]}****{number[-4:]}")
        self.assertEqual(found, [])


class DirectLoginEntries(unittest.TestCase):
    """Check the actual first navigation target and its business return chain."""

    def first_url(self, carrier):
        text = (ROOT / f"skills/{carrier}-points-redeem/GUIDE.md").read_text(encoding="utf-8")
        urls = re.findall(r"<(https://[^>]+)>", text)
        self.assertTrue(urls)
        return urlsplit(urls[0])

    def test_mobile_starts_on_the_login_route(self):
        url = self.first_url("cmcc")
        self.assertEqual(url.netloc, "jf.10086.cn")
        self.assertEqual(url.fragment.split("?", 1)[0], "/loginPage")

    def test_unicom_starts_on_login_and_returns_to_points_mall(self):
        url = self.first_url("cucc")
        self.assertEqual((url.netloc, url.path), ("uac.10010.com", "/portal/mallLogin.jsp"))
        target = urlsplit(parse_qs(url.query)["redirectURL"][0])
        self.assertEqual((target.netloc, target.path),
                         ("img.client.10010.com", "/jifenshangchengpc/index.html"))

    def test_telecom_preserves_the_full_sso_callback(self):
        url = self.first_url("ct")
        self.assertEqual((url.netloc, url.path), ("m.telefen.com", "/MobileSSOV2/Login.aspx"))
        params = parse_qs(url.query)
        self.assertEqual(params["appCode"], ["CALLS"])
        self.assertEqual(params["channelCode"], ["HGOKHD"])
        callback = urlsplit(params["goBack"][0])
        self.assertEqual((callback.netloc, callback.path),
                         ("apps.telefen.com", "/jycalls/sso/ssoLogin/login"))
        inner = parse_qs(callback.query)
        self.assertEqual(inner["loginUrl"], ["https://apps.telefen.com/jycalls/sso/ssoLogin/login"])
        self.assertEqual(inner["goBack"], ["https://apps.telefen.com/jycalls/?channelCode=HGOKHD"])
        self.assertEqual(inner["channelCode"], ["HGOKHD"])
        self.assertEqual(inner["ssoType"], ["1"])
        self.assertEqual(inner["errPage"], ["https://cdn.img.telefen.com/webstatic/sso/error.html?msg="])


class ExistingSubmissionGuards(unittest.TestCase):
    def test_subskill_state_tests_pass(self):
        for name in ("ct-points-redeem", "cucc-points-redeem"):
            with self.subTest(name=name):
                completed = subprocess.run(
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests",
                     "-p", "test_transaction_state.py"],
                    cwd=ROOT / "skills" / name, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(completed.returncode, 0,
                                 completed.stdout + completed.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
