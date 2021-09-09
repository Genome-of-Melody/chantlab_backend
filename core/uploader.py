from django.db.models import Max, F
from django.conf import settings

from melodies.models import Chant

import sqlite3

class Uploader():
    '''
    The Uploader class contains a method for uploading data
    '''

    @classmethod
    def upload_dataframe(cls, df, dataset_name):
        '''
        Upload a dataframe to database
        '''
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

    @classmethod
    def delete_dataset(cls, dataset_name):
        '''Remove all items that belong to the given `dataset_name`.

        :param dataset_name: A string. If there are no rows that belong to
            the requested dataset, nothing is done.

        :return:
        '''
        db_name = settings.DATABASE_NAME
        con = sqlite3.connect(db_name)

        # print('Uploader.delete_dataset: removing dataset name {}'.format(dataset_name))

        # Find all the rows in the dataset
        chants_to_remove = Chant.objects.filter(dataset_name__exact=dataset_name)
        if not chants_to_remove.exists():
            # We should possibly log this event.
            # print('Dataset for removal is empty: {}'.format(dataset_name))
            return

        # Find the given dataset idx
        chants_to_remove_idx = chants_to_remove.all()[:1].values_list('dataset_idx', flat=True)[0]
        # This needs to be debugged pre-emptively.
        # print('Dataset idx for removal: {}'.format(chants_to_remove_idx))

        # Remove the given rows in the dataset
        chants_to_remove.delete()

        # Set back the dataset idxs so that they remain contiguous
        chants_to_decrement = Chant.objects.filter(dataset_idx__gt=chants_to_remove_idx)
        chants_to_decrement.update(dataset_idx=F('dataset_idx') - 1)

        return



