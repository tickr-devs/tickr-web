"""Absolute addresses of the images the site's emails show (tools/mail-images.cjs draws them)."""

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def mail_image(name: str, theme: str) -> str:
    # The un-hashed copy collectstatic keeps beside the hashed one: an email stays in a mailbox
    # for years, and its images must outlive the next deploy's new hashes.
    return f"https://{settings.SITE_HOST}{settings.STATIC_URL}web/mail/{name}-{theme}.png"
