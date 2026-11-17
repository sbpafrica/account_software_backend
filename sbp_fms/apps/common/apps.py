from django.apps import AppConfig


class CommonConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.common'
    verbose_name = 'Common Base Utilities & Models'

    def ready(self):
        # Python 3.14+ compatibility patch for Django 5.x BaseContext.__copy__
        # In Python 3.14, duplicate = copy(super()) fails with:
        # AttributeError: 'super' object has no attribute 'dicts' and no __dict__
        try:
            from django.template import context as django_context

            def _safe_basecontext_copy(self):
                duplicate = object.__new__(self.__class__)
                duplicate.__dict__.update(self.__dict__)
                duplicate.dicts = self.dicts[:]
                return duplicate

            django_context.BaseContext.__copy__ = _safe_basecontext_copy
        except Exception:
            pass
