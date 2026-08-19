from django.http import HttpResponse

import csv

from core.cantus_schema import V1_EXPORT_FIELDS, chant_to_v1_row
from melodies.models import Chant


class Exporter():
    '''
    The Exporter class provides a method to download a set of chants
    '''

    @classmethod
    def export_to_csv(cls, ids):
        '''
        Create a CantusCorpus v1.0 CSV file of chants
        '''

        chants = Chant.objects.filter(pk__in=ids)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment;filename=dataset.csv'

        writer = csv.writer(response)
        writer.writerow(V1_EXPORT_FIELDS)
        for chant in chants:
            row = chant_to_v1_row(chant)
            writer.writerow([row[field] for field in V1_EXPORT_FIELDS])

        return response
