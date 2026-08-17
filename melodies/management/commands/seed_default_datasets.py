import os

from django.conf import settings
from django.core.management.base import BaseCommand
import pandas as pd

from core.uploader import Uploader
from melodies.access import DEFAULT_DATASET_NAMES
from melodies.models import Chant

SEED_FILES = (
    ('CantusCorpus v0.2', 'cantuscorpus_v0.2.csv.gz'),
    ('netvor-0.3', 'netvor-0.3.csv.gz'),
)


def seed_dir():
    return os.path.join(settings.BASE_DIR, 'seeds', 'default_datasets')


class Command(BaseCommand):
    help = 'Load shared default datasets into the runtime database if they are missing.'

    def handle(self, *args, **options):
        for name, filename in SEED_FILES:
            if name not in DEFAULT_DATASET_NAMES:
                continue
            if Chant.objects.filter(dataset_name=name, owner__isnull=True).exists():
                self.stdout.write('{} already present, skipping.'.format(name))
                continue

            path = os.path.join(seed_dir(), filename)
            if not os.path.exists(path):
                self.stderr.write('Seed file missing: {}'.format(path))
                continue

            df = pd.read_csv(path, compression='gzip')
            Uploader.upload_dataframe(df, name, owner=None)
            self.stdout.write(self.style.SUCCESS(
                'Loaded {} from {} ({} rows).'.format(name, filename, len(df))
            ))
