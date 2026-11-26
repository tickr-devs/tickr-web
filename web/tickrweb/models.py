"""Database tables of the web app (accounts are allauth's)."""

from django.db import models


class Subscriber(models.Model):
    """One address on the early-access list.

    The privacy page promises exactly these fields: no IP, no user agent, nothing else. A row is
    deleted when its owner unsubscribes; unconfirmed rows are deleted by `prune_waitlist`.
    """

    email = models.EmailField(unique=True)
    lang = models.CharField(max_length=2, choices=[("en", "English"), ("es", "Español")])
    signed_up_at = models.DateTimeField()
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["signed_up_at"]

    def __str__(self):
        return self.email
