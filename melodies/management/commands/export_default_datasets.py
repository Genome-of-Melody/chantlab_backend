import os

from django.conf import settings
from django.core.management.base import BaseCommand
import pandas as pd

from melodies.access import default_dataset_filter
from melodies.management.commands.seed_default_datasets import SEED_FILES, seed_dir
from melodies.models import Chant


class Command(BaseCommand):
    help = 'Write the shared default datasets from the current database into seed CSV files.'

    def handle(self, *args, **options):
        os.makedirs(seed_dir(), exist_ok=True)
        defaults = Chant.objects.filter(default_dataset_filter())

        for name, filename in SEED_FILES:
            chants = defaults.filter(dataset_name=name)
            if not chants.exists():
                self.stderr.write('No rows found for {}, skipping.'.format(name))
                continue

            field_names = [field.name for field in Chant._meta.fields if field.name != 'owner']
            df = pd.DataFrame.from_records(list(chants.values_list(*field_names)), columns=field_names)
            path = os.path.join(seed_dir(), filename)
            df.to_csv(path, index=False, compression='gzip')
            self.stdout.write(self.style.SUCCESS(
                'Wrote {} rows to {}.'.format(len(df), path)
            ))
