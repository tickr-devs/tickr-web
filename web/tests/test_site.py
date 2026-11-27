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
    assert len(pages) == 20  # ten pages, each in English and in Spanish
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


def test_spanish_pages_are_built_in_spanish_with_spanish_links():
    out = _build()
    html = (out / "es" / "faq" / "index.html").read_text()
    assert '<html lang="es"' in html
    assert "<title>Preguntas frecuentes · tickr.bot</title>" in html
    assert "¿Qué es tickr.bot?" in html and "What is tickr.bot?" not in html
    assert 'href="/es/security/"' in html  # links inside the Spanish text stay in Spanish
    assert 'name="lang" value="es"' in (out / "es" / "index.html").read_text()
    assert 'href="/faq/" hreflang="en"' in html and 'href="/es/faq/" hreflang="es"' in html
    assert "TK_ES" not in html


def test_reveal_never_hides_the_first_screen_or_reading_pages():
    out = _build()
    for page in ("index.html", "apps/index.html"):
        html = (out / page).read_text()
        hero = html[html.index('<main id="main">') : html.index("</section>")]
        assert "data-reveal" not in hero, page
    for page in ("faq", "how-it-works", "security", "early-access", "contact", "privacy", "terms"):
        assert "data-reveal" not in (out / page / "index.html").read_text(), page
    css = (SITE / "assets" / "site.css").read_text()
    assert ".js [data-reveal]{opacity:0" in css and "\n[data-reveal]{opacity:0" not in css


def test_one_word_for_signing_up_the_beta():
    out = _build()
    html = (out / "index.html").read_text()
    assert "Notify me" not in html and "Early access is by invite" not in html
    assert html.count(">Join the beta<") >= 3
    assert "La beta es por invitación." in (out / "es" / "index.html").read_text()
