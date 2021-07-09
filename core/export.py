from melodies.models import Chant
from django.http import HttpResponse

import csv

def export_to_csv(ids):

    chants = Chant.objects.filter(pk__in=ids)
    opts = chants.model._meta
    model = chants.model

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment;filename=dataset.csv'
    
    writer = csv.writer(response)
    field_names = [field.name for field in opts.fields]
    writer.writerow(field_names)
    for chant in chants:
        writer.writerow([getattr(chant, field) for field in field_names])
    print('here')
    return HttpResponse(response, content_type='text/csv')
