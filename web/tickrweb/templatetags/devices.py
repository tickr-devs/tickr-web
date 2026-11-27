"""A readable name for a signed-in browser ("Safari on Mac") instead of its user-agent string."""

from django import template
from django.utils.translation import gettext as _

register = template.Library()

# First match wins, so the browsers built on Chrome come before Chrome and Chrome before Safari.
_BROWSERS = [
    ("Edg/", "Edge"),
    ("OPR/", "Opera"),
    ("Firefox/", "Firefox"),
    ("FxiOS/", "Firefox"),
    ("CriOS/", "Chrome"),
    ("Chrome/", "Chrome"),
    ("Safari/", "Safari"),
]
_SYSTEMS = [
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Android", "Android"),
    ("Macintosh", "Mac"),
    ("Windows", "Windows"),
    ("CrOS", "ChromeOS"),
    ("Linux", "Linux"),
]


def _first(agent, table):
    return next((name for mark, name in table if mark in agent), None)


@register.filter
def device_system(agent):
    """The operating system's name, or None when the user agent does not say."""
    return _first(agent or "", _SYSTEMS)


@register.filter
def device_name(agent):
    browser, system = _first(agent or "", _BROWSERS), device_system(agent)
    if browser and system:
        return _("%(browser)s on %(system)s") % {"browser": browser, "system": system}
    return browser or system or _("Unknown browser")
