from django.db.models import Max
from django.conf import settings

from melodies.models import Chant

import sqlite3

class Uploader():

    @classmethod
    def upload_dataframe(cls, df, dataset_name):
        # establish db connection
        db_name = settings.DATABASE_NAME
        con = sqlite3.connect(db_name)

        # get current maximum id
        latest_id = Chant.objects.latest('id').id

        # set ids of dataframe
        start_id = latest_id + 1
        df.index = [id for id in range(start_id, len(df.values) + start_id)]

        # drop the id column
        df.drop(['id'], axis=1, inplace=True)

        # set dataset name and index
        df['dataset_name'] = dataset_name
        max_dataset_idx = Chant.objects.aggregate(Max('dataset_idx'))['dataset_idx__max']
        new_dataset_index = max_dataset_idx + 1
        df['dataset_idx'] = new_dataset_index

        # append data to database
        df.to_sql('chant', con, if_exists='append', index=True, index_label="id")

        return new_dataset_index
