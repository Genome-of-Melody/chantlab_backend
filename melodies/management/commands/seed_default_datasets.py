import os

from django.conf import settings
from django.core.management.base import BaseCommand
import pandas as pd

from core.cantus_schema import UploadError
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

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Replace existing default datasets, keeping their dataset_idx values.',
        )

    def handle(self, *args, **options):
        force = options['force']

        if CANTUS_DATASET_NAME in DEFAULT_DATASET_NAMES:
            self._seed_dataset(
                CANTUS_DATASET_NAME,
                lambda: load_cantuscorpus(),
                force,
                source_label='PyCantus',
            )

        for name, filename in SEED_FILES:
            if name not in DEFAULT_DATASET_NAMES:
                continue
            path = os.path.join(seed_dir(), filename)
            self._seed_dataset(
                name,
                lambda seed_path=path: self._read_seed_csv(seed_path),
                force,
                source_label=filename,
            )

    def _read_seed_csv(self, path):
        if not os.path.exists(path):
            self.stderr.write('Seed file missing: {}'.format(path))
            return None
        return pd.read_csv(path, compression='gzip')

    def _seed_dataset(self, name, load_df, force, source_label):
        existing = Chant.objects.filter(dataset_name=name, owner__isnull=True)
        old_idx = None
        if existing.exists():
            if not force:
                self.stdout.write('{} already present, skipping.'.format(name))
                return
            old_idx = existing.values_list('dataset_idx', flat=True).first()

        self.stdout.write('Loading {} from {} ...'.format(name, source_label))
        df = load_df()
        if df is None:
            return

        if existing.exists():
            deleted, _ = existing.delete()
            self.stdout.write('Removed {} existing {} rows.'.format(deleted, name))

        try:
            new_idx = Uploader.upload_dataframe(df, name, owner=None, dataset_idx=old_idx)
        except UploadError as exc:
            self.stderr.write('Failed to load {}: {}'.format(name, exc))
            return
        self.stdout.write(self.style.SUCCESS(
            'Loaded {} from {} ({} rows, dataset_idx={}).'.format(
                name, source_label, len(df), new_idx
            )
        ))
