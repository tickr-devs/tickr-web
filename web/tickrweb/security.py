"""Security headers Django's SecurityMiddleware does not set."""

# Scripts, styles, fonts and images come from this site only. allauth's passkey pages pass data
# in <script type="application/json">, which is never executed, so no inline script is allowed.
# Inline style attributes are allowed: allauth hides two forms with style="display: none".
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self'; style-src-attr 'unsafe-inline'; "
    "img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; object-src 'none'"
)


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        # Nothing the app serves (sign-in, cabinet, API) belongs in a search index.
        response.setdefault("X-Robots-Tag", "noindex, nofollow")
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            response.setdefault("Cache-Control", "no-store")
        return response
