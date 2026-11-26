"""Admin pages (staff only, /app/admin/)."""

from django.contrib import admin

from .models import Subscriber


@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "lang", "signed_up_at", "confirmed_at"]
    list_filter = ["lang", ("confirmed_at", admin.EmptyFieldListFilter)]
    search_fields = ["email"]
