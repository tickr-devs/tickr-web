"""Builds the tickr.bot static site (the public pages Caddy serves from /srv/site) from pages/*.html.

    python3 web/site/build.py            -> web/site/out/site/ (pretty links, for web/deploy/ship.sh)
    python3 web/site/build.py preview    -> web/site/out/preview/ (relative links, opens from disk)

Design: the approved mockup page "Сайт tickr.bot", board SiteLanding (app tokens, system fonts).
The wordmark and app tile are read from the Django templates, so the site and the app share one source.
Each page file starts with a JSON line: {"slug": "...", "title": "...", "desc": "...", "nav": "..."}
followed by the page body. Spanish strings for the page go in <script>window.TK_ES = {...}</script>
inside the body.
"""

import json
import pathlib
import re
import shutil
import sys

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
TILE = _svg("app/tile.html").replace("{{ size }}", "72")

FAVICON = (
    "data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27%3E%3Crect width=%2724%27 height=%2724%27 rx=%275%27 fill=%27%23070A16%27/%3E"
    "%3Cpath fill=%27%23E7EAF6%27 d=%27M7.5 7.5 L10.5 4.5 L10.5 15 A3 3 0 0 0 13.5 18 L18 18 L15 21 L13.5 21 A6 6 0 0 1 7.5 15 Z M4.5 9 H7.5 V12 H4.5 Z%27/%3E%3Cpath fill=%27%232DD4BF%27 d=%27M12 9 H19.5 V12 H12 Z%27/%3E%3C/svg%3E"
)

NAV = [
    ("how-it-works", "nHow", "How it works"),
    ("apps", "nApps", "Apps"),
    ("security", "nSec", "Security"),
    ("faq", "nFaq", "FAQ"),
]


def form(n):
    """The early-access form; n tells apart the forms on one page (the home page has two)."""
    i = "" if n == 1 else str(n)
    return f"""<form id="signup{i}" class="signup" action="/api/waitlist" method="post" novalidate>
<label class="sr" for="email{i}" data-i18n="emailLabel">Email address</label>
<div class="hp" aria-hidden="true"><label for="website{i}">Website</label><input id="website{i}" name="website" type="text" tabindex="-1" autocomplete="off"></div>
<input type="hidden" name="lang" value="en">
<div class="field-row">
<input id="email{i}" name="email" type="email" required maxlength="254" autocomplete="email" placeholder="you@example.com" data-i18n-ph="emailPh">
<button type="submit" data-i18n="cta">Notify me</button>
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
    "cta": "Avísenme",
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
    "nAccess": "Acceso anticipado",
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


def url(slug, mode, depth):
    if mode == "site":
        return "/" if slug == "index" else f"/{slug}/"
    up = "../" * depth
    return f"{up}index.html" if slug == "index" else f"{up}{slug}/index.html"


def asset(name, mode, depth):
    return f"/assets/{name}" if mode == "site" else "../" * depth + f"assets/{name}"


def header(cur, mode, depth):
    links = "".join(
        f'<a href="{url(s, mode, depth)}" data-i18n="{k}"{" aria-current=page" if s == cur else ""}>{t}</a>'
        for s, k, t in NAV
    )
    links += '<a class="nav-in" href="/login" data-i18n="signIn">Sign in</a>'
    links += f'<a class="nav-cta" href="{url("early-access", mode, depth)}#signup" data-i18n="nJoin">Join the beta</a>'
    return f'''<a class="skip" href="#main" data-i18n="skip">Skip to content</a>
<header class="site-h">
<div class="wrap top">
<a class="brand" href="{url("index", mode, depth)}" aria-label="tickr.bot" data-i18n-aria="home">{WORDMARK}</a>
<nav class="nav" id="nav" aria-label="Main">{links}</nav>
<div class="top-r">
<div class="seg" role="group" aria-label="Language" data-i18n-aria="langLabel"><button type="button" data-lang="en" aria-pressed="true">EN</button><button type="button" data-lang="es" aria-pressed="false">ES</button></div>
<a class="signin" href="/login" data-i18n="signIn">Sign in</a>
<a class="btn" href="{url("early-access", mode, depth)}#signup" data-i18n="nJoin">Join the beta</a>
<button class="menu-b" type="button" aria-controls="nav" aria-expanded="false" aria-label="Menu" data-i18n-aria="menu"><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><path d="M3 7h16M3 15h16" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button>
</div>
</div>
</header>'''


def footer(mode, depth):
    def u(slug):
        return url(slug, mode, depth)

    return f'''<footer class="site-f">
<div class="wrap">
<div class="fgrid">
<div><a class="brand" href="{u("index")}" aria-label="tickr.bot" data-i18n-aria="home">{WORDMARK}</a><p class="tag" data-i18n="fTag">Intraday automation for US stocks, with stops your broker holds.</p></div>
<div><h4 data-i18n="fProduct">Product</h4><ul><li><a href="{u("how-it-works")}" data-i18n="nHow">How it works</a></li><li><a href="{u("apps")}" data-i18n="nApps">Apps</a></li><li><a href="{u("security")}" data-i18n="nSec">Security</a></li><li><a href="{u("early-access")}" data-i18n="nAccess">Early access</a></li></ul></div>
<div><h4 data-i18n="fHelp">Help</h4><ul><li><a href="{u("faq")}" data-i18n="nFaq">FAQ</a></li><li><a href="{u("contact")}" data-i18n="nContact">Contact</a></li><li><a href="/login" data-i18n="signIn">Sign in</a></li></ul></div>
<div><h4 data-i18n="fLegal">Legal</h4><ul><li><a href="{u("privacy")}" data-i18n="nPrivacy">Privacy</a></li><li><a href="{u("terms")}" data-i18n="nTerms">Terms</a></li></ul></div>
</div>
<p class="risk" data-i18n="risk">tickr.bot is software, not investment advice. You choose every setting it trades by. Trading involves risk, including loss of the money you invest. Past results do not guarantee future results.</p>
<p class="fmeta">© 2026 tickr.bot · <span data-i18n="status">In private testing</span></p>
</div>
</footer>'''


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
        depth = 0 if name in ("index", "404") else 1
        body = re.sub(r"\{\{icon:([a-z]+)\}\}", lambda m: _svg(f"icons/{m.group(1)}.svg"), body)
        body = (
            body.replace("{{form}}", form(1))
            .replace("{{form2}}", form(2))
            .replace("{{tile}}", TILE)
        )
        body = re.sub(r"\{\{u:([a-z-]+)\}\}", lambda m, d=depth: url(m.group(1), mode, d), body)
        body = re.sub(r"\{\{a:([a-z.-]+)\}\}", lambda m, d=depth: asset(m.group(1), mode, d), body)
        robots = '\n<meta name="robots" content="noindex">' if meta.get("noindex") else ""
        html = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{meta["title"]}</title>
<meta name="description" content="{meta["desc"]}">{robots}
<meta name="theme-color" content="#05070F" media="(prefers-color-scheme: dark)">
<meta name="theme-color" content="#E9EDF7" media="(prefers-color-scheme: light)">
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<link rel="stylesheet" href="{asset("site.css", mode, depth)}">
</head>
<body>
{header(name, mode, depth)}
<main id="main">
{body.strip()}
</main>
{footer(mode, depth)}
<script>window.TK_COMMON_ES = {json.dumps(COMMON_ES, ensure_ascii=False)};</script>
<script src="{asset("site.js", mode, depth)}"></script>
</body>
</html>
'''
        dest = (
            out / "index.html"
            if name == "index"
            else out / "404.html"
            if name == "404"
            else out / name / "index.html"
        )
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(html)
    print("built", mode)


if __name__ == "__main__":
    for m in sys.argv[1:] or ["site", "preview"]:
        build(m)
