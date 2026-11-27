"""The public site builds from web/site, in the app brand, with no third-party requests."""

import importlib.util
import pathlib
import re

SITE = pathlib.Path(__file__).resolve().parents[1] / "site"


def _build():
    spec = importlib.util.spec_from_file_location("site_build", SITE / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.build("site")
    return SITE / "out" / "site"


def test_every_page_builds_without_leftovers_or_outside_hosts():
    out = _build()
    pages = sorted(out.rglob("*.html"))
    assert len(pages) == 10
    for page in pages:
        html = page.read_text()
        assert "{{" not in html, page
        assert "{#" not in html, page
        assert not re.search(r"(href|src)=\"https?://", html), page
        assert 'href="/login"' in html, page
        assert "Webull" not in html, page


def test_home_has_two_early_access_forms_posting_to_the_waitlist():
    html = (_build() / "index.html").read_text()
    assert html.count('action="/api/waitlist"') == 2
    assert 'id="signup"' in html and 'id="signup2"' in html


def test_assets_carry_their_content_hash():
    html = (_build() / "index.html").read_text()
    assert re.search(r'href="/assets/site\.css\?v=[0-9a-f]{10}"', html)
    assert re.search(r'src="/assets/site\.js\?v=[0-9a-f]{10}"', html)
