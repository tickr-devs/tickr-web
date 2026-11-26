from django.contrib.admin.apps import AdminConfig


class TickrAdminConfig(AdminConfig):
    default_site = "tickrweb.admin_site.TickrAdminSite"
