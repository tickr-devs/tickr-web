"""The two native apps as public OAuth clients of tickr.bot (tickrweb/oidc.py)."""

from django.db import migrations

APPS = {"tickr-ios": "Tickr for iPhone and iPad", "tickr-mac": "Tickr for Mac"}


def add_clients(apps, schema_editor):
    client_model = apps.get_model("allauth_idp_oidc", "Client")
    for client_id, name in APPS.items():
        client_model.objects.update_or_create(
            id=client_id,
            defaults={
                "name": name,
                "type": "public",
                "secret": "!",  # public clients have no secret; "!" never matches one
                "scopes": "bot",
                "default_scopes": "bot",
                "grant_types": "authorization_code",
                "response_types": "code",
                "redirect_uris": "tickr://signin",
                "cors_origins": "",
                "allow_uri_wildcards": False,
                "skip_consent": True,
            },
        )


def remove_clients(apps, schema_editor):
    apps.get_model("allauth_idp_oidc", "Client").objects.filter(id__in=APPS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("tickrweb", "0001_initial"),
        ("allauth_idp_oidc", "0003_client_allow_uri_wildcards"),
    ]

    operations = [migrations.RunPython(add_clients, remove_clients)]
