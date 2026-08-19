from django.db.models import Max

from core.cantus_schema import (
    PROTECTED_FIELDS,
    UploadError,
    float_or_none,
    normalize_chant_dataframe,
    text_value,
)
from melodies.access import is_default_dataset_name
from melodies.models import Chant

_FLOAT_FIELDS = frozenset({'sequence', 'cao_concordances'})
_BATCH_SIZE = 5000


class Uploader():
    '''
    The Uploader class contains a method for uploading data
    '''

    @classmethod
    def upload_dataframe(cls, df, dataset_name, owner=None, dataset_idx=None):
        '''
        Upload a dataframe to database
        '''
        rows = cls._rows_from_dataframe(df, dataset_name, owner)
        if not rows:
            raise UploadError('The CSV file contains no chant rows')

        if dataset_idx is None:
            max_dataset_idx = Chant.objects.aggregate(Max('dataset_idx'))['dataset_idx__max']
            dataset_idx = 0 if max_dataset_idx is None else max_dataset_idx + 1

        for row in rows:
            row['dataset_idx'] = dataset_idx

        cls._bulk_insert(rows)
        return dataset_idx

    @classmethod
    def add_to_dataset(cls, df, idx, owner=None):
        '''
        Add data to existing dataset. If specified dataset does not exist,
        creates dataset with name 'Undefined'.
        '''
        dataset = Chant.objects.filter(dataset_idx=idx)
        if dataset.exists():
            dataset_name = dataset[0].dataset_name
        else:
            dataset_name = 'Undefined'

        rows = cls._rows_from_dataframe(df, dataset_name, owner)
        if not rows:
            raise UploadError('No chant rows to add')

        for row in rows:
            row['dataset_idx'] = idx

        cls._bulk_insert(rows)
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
    def _rows_from_dataframe(cls, df, dataset_name, owner):
        mapped = normalize_chant_dataframe(df)
        allowed = {
            field.attname if field.is_relation else field.name
            for field in Chant._meta.fields
        } - PROTECTED_FIELDS
        allowed.discard('id')

        rows = []
        owner_id = owner.id if owner is not None else None
        for record in mapped.to_dict(orient='records'):
            row = {}
            for key, value in record.items():
                if key not in allowed:
                    continue
                if key in _FLOAT_FIELDS:
                    row[key] = float_or_none(value)
                else:
                    row[key] = text_value(value)
            row['dataset_name'] = dataset_name
            row['owner_id'] = owner_id
            rows.append(row)
        return rows

    @classmethod
    def _bulk_insert(cls, rows):
        chants = [Chant(**row) for row in rows]
        Chant.objects.bulk_create(chants, batch_size=_BATCH_SIZE)
