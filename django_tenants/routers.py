from django.conf import settings
from django.apps import apps as django_apps


def _get_connection(db):
    # the imports below need to be done here else django <1.5 goes crazy
    # https://code.djangoproject.com/ticket/20704
    from django.db import connections
    return connections[db]

class TenantSyncRouter(object):
    """
    A router to control which applications will be synced,
    depending if we are syncing the shared apps or the tenant apps.
    """
    def __init__(self):
        from django_tenants.utils import get_public_schema_name, get_tenant_database_alias
        self.tenant_database_alias = get_tenant_database_alias()
        self.public_schema_name = get_public_schema_name()


    def app_in_list(self, app_label, apps_list):
        """
        Is 'app_label' present in 'apps_list'?

        apps_list is either settings.SHARED_APPS or settings.TENANT_APPS, a
        list of app names.

        We check the presence of the app's name or the full path to the apps's
        AppConfig class.
        https://docs.djangoproject.com/en/1.8/ref/applications/#configuring-applications
        """
        appconfig = django_apps.get_app_config(app_label)
        appconfig_full_name = '{}.{}'.format(
            appconfig.__module__, appconfig.__class__.__name__)
        return (appconfig.name in apps_list) or (appconfig_full_name in apps_list)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db != self.tenant_database_alias:
            return False

        connection = _get_connection(db)
        if connection.schema_name == self.public_schema_name:
            if not self.app_in_list(app_label, settings.SHARED_APPS):
                return False
        else:
            if not self.app_in_list(app_label, settings.TENANT_APPS):
                return False

        return None

class TenantOverrideRouter(TenantSyncRouter):
    def __init__(self):
        super().__init__()
        from django_tenants.utils import get_tenant_model_override
        self.public_models, self.tenant_models = get_tenant_model_override()

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name is None:
            return None
            
        model_qualname = '%s.%s' % (app_label, model_name)
        connection = _get_connection(db)

        if model_qualname in self.public_models:
            if connection.schema_name == self.public_schema_name:
                return True
            else:
                return False
        elif model_qualname in self.tenant_models:
            if connection.schema_name == self.public_schema_name:
                return False
            else:
                return True
