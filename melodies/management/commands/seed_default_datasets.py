import os

from django.conf import settings
from django.core.management.base import BaseCommand
import pandas as pd

from core.uploader import Uploader
from melodies.access import DEFAULT_DATASET_NAMES
from melodies.management.cantuscorpus import (
    DATASET_NAME as CANTUS_DATASET_NAME,
    load_cantuscorpus,
)
from melodies.models import Chant

SEED_FILES = (
    ('netvor-0.3', 'netvor-0.3.csv.gz'),
)


def seed_dir():
    return os.path.join(settings.BASE_DIR, 'seeds', 'default_datasets')


class Command(BaseCommand):
    help = 'Load shared default datasets into the runtime database if they are missing.'

    def handle(self, *args, **options):
        if CANTUS_DATASET_NAME in DEFAULT_DATASET_NAMES:
            if Chant.objects.filter(dataset_name=CANTUS_DATASET_NAME, owner__isnull=True).exists():
                self.stdout.write('{} already present, skipping.'.format(CANTUS_DATASET_NAME))
            else:
                self.stdout.write('Loading {} from PyCantus ...'.format(CANTUS_DATASET_NAME))
                df = load_cantuscorpus()
                new_idx = Uploader.upload_dataframe(df, CANTUS_DATASET_NAME, owner=None)
                self.stdout.write(self.style.SUCCESS(
                    'Loaded {} from PyCantus ({} rows, dataset_idx={}).'.format(
                        CANTUS_DATASET_NAME, len(df), new_idx
                    )
                ))

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
            new_idx = Uploader.upload_dataframe(df, name, owner=None)
            self.stdout.write(self.style.SUCCESS(
                'Loaded {} from {} ({} rows, dataset_idx={}).'.format(
                    name, filename, len(df), new_idx
                )
            ))
