"""Builds the tickr.bot static site (the public pages Caddy serves from /srv/site) from pages/*.html.

    python3 web/site/build.py            -> web/site/out/site/ (pretty links, for web/deploy/ship.sh)
    python3 web/site/build.py preview    -> web/site/out/preview/ (relative links, opens from disk)

Design: the approved mockup page "tickr.bot site", board SiteLanding (app tokens, system fonts).
The wordmark is read from the Django templates, so the site and the app share one source.
Each page file starts with a JSON line: {"slug": "...", "title": "...", "desc": "...", "nav": "..."}
followed by the page body. Its Spanish is pages/<name>.es.json (keys of the page's data-i18n
attributes; "__title" is the tab title). Every page is built twice: English at /<slug>/ and Spanish at
/es/<slug>/, so a Spanish reader never sees English first.
"""

import hashlib
import html
import json
import pathlib
import re
import shutil
import sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).parent
PAGES = [
    "index",
    "404",
    "how-it-works",
    "apps",
    "security",
    "early-access",
    "faq",
    "contact",
    "privacy",
    "terms",
]

TEMPLATES = ROOT.parent / "tickrweb" / "templates"


def _svg(name):
    """An SVG from the Django templates, without its {# comment #} line."""
    return re.sub(r"\{#.*?#\}\s*", "", (TEMPLATES / name).read_text(), flags=re.S).strip()


WORDMARK = _svg("brand.svg")
# The brand inside pages is the wordmark, never the app-icon tile (mockup p-logo B).
CTA_MARK = f'<span class="cmark">{WORDMARK}</span>'

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect width=%2724%27 height=%2724%27 rx=%275%27 fill=%27%23070A16%27/%3E"
    "%3Cpath fill=%27%23E7EAF6%27 d=%27M7.5 7.5 L10.5 4.5 L10.5 15 A3 3 0 0 0 13.5 18 L18 18 L15 21 L13.5 21 A6 6 0 0 1 7.5 15 Z M4.5 9 H7.5 V12 H4.5 Z%27/%3E%3Cpath fill=%27%232DD4BF%27 d=%27M12 9 H19.5 V12 H12 Z%27/%3E%3C/svg%3E"
)


def head_js(other, other_url):
    """Runs in <head> before the page paints. It marks that scripts run (only then may [data-reveal]
    blocks start hidden; without scripts every block is simply shown), and sends a reader to the other
    language's copy of the page when they chose that language before or, on a first visit, when the
    browser asks for it."""
    return (
        "(function(){var d=document.documentElement,c=null;d.className='js';"
        "try{c=localStorage.getItem('tk-lang')}catch(e){}"
        f"if(!c&&'{other}'==='es'&&(navigator.language||'').toLowerCase().indexOf('es')===0)c='es';"
        + (f"if(c==='{other}')location.replace('{other_url}')" if other_url else "")
        + "})();"
    )


NAV = [
    ("how-it-works", "nHow", "How it works"),
    ("apps", "nApps", "Apps"),
    ("security", "nSec", "Security"),
    ("faq", "nFaq", "FAQ"),
]


def form(n, lang):
    """The early-access form; n tells apart the forms on one page (the home page has two)."""
    i = "" if n == 1 else str(n)
    return f"""<form id="signup{i}" class="signup" action="/api/waitlist" method="post" novalidate>
<label class="sr" for="email{i}" data-i18n="emailLabel">Email address</label>
<div class="hp" aria-hidden="true"><label for="website{i}">Website</label><input id="website{i}" name="website" type="text" tabindex="-1" autocomplete="off"></div>
<input type="hidden" name="lang" value="{lang}">
<div class="field-row">
<input id="email{i}" name="email" type="email" required maxlength="254" autocomplete="email" placeholder="you@example.com" data-i18n-ph="emailPh">
<button type="submit" data-i18n="cta">Join the beta</button>
</div>
<p class="note msg" role="status" aria-live="polite" data-i18n="formNote">One email when the beta opens. Nothing else.</p>
<div class="done" tabindex="-1" role="status" hidden>
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.8"/></svg>
<span class="done-text" data-i18n="ok">You're on the list. Check your email to confirm.</span>
</div>
</form>"""


# Spanish for the parts every page shares. US Spanish, "usted" everywhere (as the apps).
COMMON_ES = {
    "emailLabel": "Correo electrónico",
    "emailPh": "usted@ejemplo.com",
    "cta": "Unirse a la beta",
    "formNote": "Un solo correo cuando abra la beta. Nada más.",
    "ok": "Ya está en la lista. Revise su correo para confirmar.",
    "confirm": "Casi listo. Revise su correo y confirme su dirección.",
    "skip": "Saltar al contenido",
    "menu": "Menú",
    "langLabel": "Idioma",
    "home": "Inicio de tickr.bot",
    "nHow": "Cómo funciona",
    "nApps": "Apps",
    "nSec": "Seguridad",
    "nAccess": "Beta",
    "nFaq": "Preguntas",
    "nJoin": "Unirse a la beta",
    "signIn": "Iniciar sesión",
    "fTag": "Automatización intradía para acciones de EE. UU., con stops que guarda su bróker.",
    "fProduct": "Producto",
    "fHelp": "Ayuda",
    "fLegal": "Legal",
    "nContact": "Contacto",
    "nPrivacy": "Privacidad",
    "nTerms": "Términos",
    "status": "En pruebas privadas",
    "risk": "tickr.bot es software, no asesoría de inversión. Usted elige cada ajuste con el que opera. Operar implica riesgos, incluida la pérdida del dinero invertido. Los resultados pasados no garantizan resultados futuros.",
}


def url(slug, mode, depth, lang="en"):
    """A link to a page; depth counts the folders between the linking page and the site root."""
    pre = "es/" if lang == "es" else ""
    if mode == "site":
        return f"/{pre}" if slug == "index" else f"/{pre}{slug}/"
    up = "../" * depth
    return f"{up}{pre}index.html" if slug == "index" else f"{up}{pre}{slug}/index.html"


def asset(name, mode, depth):
    # ?v= is the file's content hash: a deploy changes the URL, so no browser keeps an old copy.
    v = hashlib.sha256((ROOT / "assets" / name).read_bytes()).hexdigest()[:10]
    path = f"/assets/{name}" if mode == "site" else "../" * depth + f"assets/{name}"
    return f"{path}?v={v}"


def header(cur, mode, depth, lang):
    links = "".join(
        f'<a href="{url(s, mode, depth, lang)}" data-i18n="{k}"{" aria-current=page" if s == cur else ""}>{t}</a>'
        for s, k, t in NAV
    )
    links += '<a class="nav-in" href="/login" data-i18n="signIn">Sign in</a>'
    links += f'<a class="nav-cta" href="{url("early-access", mode, depth, lang)}#signup" data-i18n="nJoin">Join the beta</a>'
    page = "index" if cur == "404" else cur
    seg = "".join(
        f'<a href="{url(page, mode, depth, code)}" hreflang="{code}" lang="{code}" data-lang="{code}"'
        f"{' aria-current=true' if code == lang else ''}>{code.upper()}</a>"
        for code in ("en", "es")
    )
    return f'''<a class="skip" href="#main" data-i18n="skip">Skip to content</a>
<header class="site-h">
<div class="wrap top">
<a class="brand" href="{url("index", mode, depth, lang)}" aria-label="tickr.bot" data-i18n-aria="home">{WORDMARK}</a>
<nav class="nav" id="nav" aria-label="Main">{links}</nav>
<div class="top-r">
<nav class="seg" aria-label="Language" data-i18n-aria="langLabel">{seg}</nav>
<a class="signin" href="/login" data-i18n="signIn">Sign in</a>
<a class="btn" href="{url("early-access", mode, depth, lang)}#signup" data-i18n="nJoin">Join the beta</a>
<button class="menu-b" type="button" aria-controls="nav" aria-expanded="false" aria-label="Menu" data-i18n-aria="menu"><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M3 7h16M3 15h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
</div>
</div>
</header>'''


def footer(mode, depth, lang):
    def u(slug):
        return url(slug, mode, depth, lang)

    return f'''<footer class="site-f">
<div class="wrap">
<div class="fgrid">
<div><a class="brand" href="{u("index")}" aria-label="tickr.bot" data-i18n-aria="home">{WORDMARK}</a><p class="tag" data-i18n="fTag">Intraday automation for US stocks, with stops your broker holds.</p></div>
<div><h4 data-i18n="fProduct">Product</h4><ul><li><a href="{u("how-it-works")}" data-i18n="nHow">How it works</a></li><li><a href="{u("apps")}" data-i18n="nApps">Apps</a></li><li><a href="{u("security")}" data-i18n="nSec">Security</a></li><li><a href="{u("early-access")}" data-i18n="nAccess">Beta</a></li></ul></div>
<div><h4 data-i18n="fHelp">Help</h4><ul><li><a href="{u("faq")}" data-i18n="nFaq">FAQ</a></li><li><a href="{u("contact")}" data-i18n="nContact">Contact</a></li><li><a href="/login" data-i18n="signIn">Sign in</a></li></ul></div>
<div><h4 data-i18n="fLegal">Legal</h4><ul><li><a href="{u("privacy")}" data-i18n="nPrivacy">Privacy</a></li><li><a href="{u("terms")}" data-i18n="nTerms">Terms</a></li></ul></div>
</div>
<p class="risk" data-i18n="risk">tickr.bot is software, not investment advice. You choose every setting it trades by. Trading involves risk, including loss of the money you invest. Past results do not guarantee future results.</p>
<p class="fmeta">© 2026 tickr.bot · <span data-i18n="status">In private testing</span></p>
</div>
</footer>'''


class _Translate(HTMLParser):
    """Copies HTML, putting the Spanish for each data-i18n key in place of the element's content and
    for each data-i18n-aria/-ph/-alt key in place of that attribute. A key with no Spanish refuses the
    build: a half-English Spanish page is never shipped."""

    ATTRS = {"data-i18n-aria": "aria-label", "data-i18n-ph": "placeholder", "data-i18n-alt": "alt"}
    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }

    def __init__(self, es, page):
        super().__init__(convert_charrefs=False)
        self.es, self.page, self.out, self.skip = es, page, [], 0

    def _es(self, key):
        if key not in self.es:
            raise SystemExit(f"{self.page}: no Spanish for data-i18n key {key!r}")
        return self.es[key]

    def handle_starttag(self, tag, attrs):
        if self.skip:
            if tag not in self.VOID:
                self.skip += 1
            return
        text = self.get_starttag_text()
        names = dict(attrs)
        for data, attr in self.ATTRS.items():
            if data in names:
                value = html.escape(self._es(names[data]), quote=True)
                if attr in names:
                    text = re.sub(
                        rf'(\s{attr}=")[^"]*(")',
                        lambda m, v=value: m.group(1) + v + m.group(2),
                        text,
                        count=1,
                    )
                else:
                    text = text[:-1] + f' {attr}="{value}">'
        self.out.append(text)
        if "data-i18n" in names and tag not in self.VOID:
            self.out.append(self._es(names["data-i18n"]))
            self.skip = 1

    def handle_startendtag(self, tag, attrs):
        if not self.skip:
            self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
            if self.skip:
                return
        self.out.append(f"</{tag}>")

    def _raw(self, text):
        if not self.skip:
            self.out.append(text)

    def handle_data(self, data):
        self._raw(data)

    def handle_entityref(self, name):
        self._raw(f"&{name};")

    def handle_charref(self, name):
        self._raw(f"&#{name};")

    def handle_comment(self, data):
        self._raw(f"<!--{data}-->")

    def handle_decl(self, decl):
        self._raw(f"<!{decl}>")


def to_spanish(page_html, es, page):
    t = _Translate(es, page)
    t.feed(page_html)
    t.close()
    return "".join(t.out)


def build(mode):
    out = ROOT / "out" / mode
    if out.exists():
        shutil.rmtree(out)
    (out / "assets").mkdir(parents=True)
    for f in (ROOT / "assets").iterdir():
        shutil.copy(f, out / "assets" / f.name)
    for name in PAGES:
        raw = (ROOT / "pages" / f"{name}.html").read_text()
        meta_line, body = raw.split("\n", 1)
        meta = json.loads(meta_line)
        es = dict(COMMON_ES, **json.loads((ROOT / "pages" / f"{name}.es.json").read_text()))
        for lang in ("en", "es"):
            dest = (
                out
                / ("es" if lang == "es" else "")
                / (
                    "index.html"
                    if name == "index"
                    else "404.html"
                    if name == "404"
                    else f"{name}/index.html"
                )
            )
            depth = len(dest.relative_to(out).parts) - 1
            page = page_html(name, meta, body, mode, depth, lang)
            if lang == "es":
                page = to_spanish(page, es, name)
            page = re.sub(
                r"\{\{u:([a-z-]+)\}\}",
                lambda m, d=depth, lg=lang: url(m.group(1), mode, d, lg),
                page,
            )
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(page)
    print("built", mode)


def page_html(name, meta, body, mode, depth, lang):
    body = re.sub(r"\{\{icon:([a-z]+)\}\}", lambda m: _svg(f"icons/{m.group(1)}.svg"), body)
    body = (
        body.replace("{{form}}", form(1, lang))
        .replace("{{form2}}", form(2, lang))
        .replace("{{mark}}", CTA_MARK)
    )
    body = re.sub(r"\{\{a:([a-z.-]+)\}\}", lambda m, d=depth: asset(m.group(1), mode, d), body)
    robots = '\n<meta name="robots" content="noindex">' if meta.get("noindex") else ""
    other = "en" if lang == "es" else "es"
    title = html.escape(meta["title"])
    if lang == "es":
        title = html.escape(
            json.loads((ROOT / "pages" / f"{name}.es.json").read_text()).get(
                "__title", meta["title"]
            )
        )
    return f"""<!doctype html>
<html lang="{lang}" class="no-js">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{title}</title>
<meta name="description" content="{meta["desc"]}">{robots}
<meta name="theme-color" content="#05070F" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#E9EDF7" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<script>{head_js(other, None if name == "404" else url(name, mode, depth, other))}</script>
<link rel="stylesheet" href="{asset("site.css", mode, depth)}">
</head>
<body>
{header(name, mode, depth, lang)}
<main id="main">
{body.strip()}
</main>
{footer(mode, depth, lang)}
<script src="{asset("site.js", mode, depth)}"></script>
</body>
</html>
"""


if __name__ == "__main__":
    for m in sys.argv[1:] or ["site", "preview"]:
        build(m)
