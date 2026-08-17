from django.db.models import Max

from django.conf import settings

from melodies.access import is_default_dataset_name
from melodies.models import Chant

import sqlite3

class Uploader():
    '''
    The Uploader class contains a method for uploading data
    '''

    @classmethod
    def upload_dataframe(cls, df, dataset_name, owner=None):
        '''
        Upload a dataframe to database
        '''
        db_name = settings.DATABASES['default']['NAME']
        con = sqlite3.connect(db_name)

        try:
            latest_id = Chant.objects.latest('id').id
        except Chant.DoesNotExist:
            latest_id = 0

        start_id = latest_id + 1
        df = df.copy()
        df.index = [id for id in range(start_id, len(df.values) + start_id)]

        df = cls._prepare_chant_dataframe(df, dataset_name, owner)

        max_dataset_idx = Chant.objects.aggregate(Max('dataset_idx'))['dataset_idx__max']
        new_dataset_index = 0 if max_dataset_idx is None else max_dataset_idx + 1
        df['dataset_idx'] = new_dataset_index

        df.to_sql('chant', con, if_exists='append', index=True, index_label="id")

        return new_dataset_index


    @classmethod
    def add_to_dataset(cls, df, idx, owner=None):
        '''
        Add data to existing dataset. If specified dataset does not exist,
        creates dataset with name 'Undefined'.
        '''
        db_name = settings.DATABASES['default']['NAME']
        con = sqlite3.connect(db_name)

        dataset = Chant.objects.filter(dataset_idx=idx)
        if dataset.exists():
            dataset_name = dataset[0].dataset_name
        else:
            dataset_name = 'Undefined'

        try:
            latest_id = Chant.objects.latest('id').id
        except Chant.DoesNotExist:
            latest_id = 0

        start_id = latest_id + 1
        df = df.copy()
        df.index = [id for id in range(start_id, len(df.values) + start_id)]

        df = cls._prepare_chant_dataframe(df, dataset_name, owner)
        df['dataset_idx'] = idx

        df.to_sql('chant', con, if_exists='append', index=True, index_label="id")

        return dataset_name


    @classmethod
    def delete_dataset(cls, dataset_name, owner):
        '''Remove all items that belong to the given `dataset_name` and owner.

        Default datasets are never deleted. Dataset indexes are left unchanged
        so other users' selections stay valid.
        '''
        if is_default_dataset_name(dataset_name) or owner is None:
            return False

        chants_to_remove = Chant.objects.filter(
            dataset_name__exact=dataset_name,
            owner=owner,
        )
        if not chants_to_remove.exists():
            return False

        chants_to_remove.delete()
        return True


    @classmethod
    def _prepare_chant_dataframe(cls, df, dataset_name, owner):
        for col in ('id', 'owner', 'owner_id', 'is_owned'):
            if col in df.columns:
                df.drop(columns=[col], inplace=True)

        df['dataset_name'] = dataset_name
        df['owner_id'] = owner.id if owner is not None else None
        return df
