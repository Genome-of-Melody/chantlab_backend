from django.apps import AppConfig


class MelodiesConfig(AppConfig):
    name = 'melodies'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(seed_default_datasets_after_migrate, sender=self)


def seed_default_datasets_after_migrate(sender, **kwargs):
    from django.core.management import call_command
    call_command('seed_default_datasets')
