from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'
    verbose_name = 'User Management, RBAC & Authentication'

    def ready(self):
        try:
            import jazzmin.utils
            from django.contrib import admin

            def safe_get_view_permissions(user):
                """
                Safe adapter for Jazzmin menu generation with custom RBAC user models.
                Prevents ValueError on '*' wildcard or colon-delimited permission codes.
                """
                if getattr(user, 'is_superuser', False):
                    model_perms = set()
                    for model in admin.site._registry.keys():
                        model_perms.add(f"{model._meta.app_label}.{model._meta.model_name}")
                    return model_perms

                perms = user.get_all_permissions()
                lower_perms = []
                for perm in perms:
                    if not isinstance(perm, str) or '.' not in perm:
                        continue
                    app, perm_codename = perm.split(".", 1)
                    lower_perms.append(f"{app}.{perm_codename.lower()}")
                return {x.replace("view_", "") for x in lower_perms if "view" in x or "change" in x}

            jazzmin.utils.get_view_permissions = safe_get_view_permissions
        except ImportError:
            pass
