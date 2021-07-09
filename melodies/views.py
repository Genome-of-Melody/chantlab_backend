from django.shortcuts import render
from django.db.models import Max

from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status
 
from melodies.models import Chant
from melodies.serializers import ChantSerializer
from rest_framework.decorators import api_view

from core.alignment import alignment_full, alignment_syllables
from core.chant import get_JSON, get_stressed_syllables, get_syllables_from_text
from core.mafft import Mafft
from core.export import export_to_csv
from core.upload import upload_csv
import json
import os
import pandas as pd
import sqlite3
import os

@api_view(['POST'])
def chant_list(request):
    data_sources = json.loads(request.POST['dataSources'])
    incipit = request.POST['incipit']
    genres = json.loads(request.POST['genres'])
    offices = json.loads(request.POST['offices'])
    chants = Chant.objects.filter(dataset_idx__in=data_sources)\
                .filter(genre_id__in=genres)\
                .filter(office_id__in=offices)

    if incipit is not None:
        chants = chants.filter(incipit__icontains=incipit)
    
    chants_serializer = ChantSerializer(chants, many=True)
    return JsonResponse(chants_serializer.data, safe=False)


@api_view(['GET'])
def chant_display(request, pk):
    try:
        chant = Chant.objects.get(id=pk)
    except Chant.DoesNotExist:
        return JsonResponse({'message': 'The chant does not exist'}, status=status.HTTP_404_NOT_FOUND)   

    try:
        chant_json = get_JSON(chant.full_text, chant.volpiano)
    except:
        chant_json = None
    stresses = get_stressed_syllables(chant.full_text)
    return JsonResponse({
        'db_source': ChantSerializer(chant).data,
        'json_volpiano': json.loads(chant_json) if chant_json else None, 
        'stresses': stresses})


@api_view(['POST'])
def upload_data(request):
    if request.FILES['file']:
        file = request.FILES['file']
        name = request.POST['name']

        df = pd.read_csv(file)

        new_index = upload_csv(df, name)

        return JsonResponse({
            "name": name,
            "index": new_index})


@api_view(['GET'])
def get_sources(request):
    sources = Chant.objects.values_list('dataset_idx', 'dataset_name').distinct()
    return JsonResponse({"sources": list(sources)})


@api_view(['POST'])
def export_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    return export_to_csv(ids)


@api_view(['POST'])
def chant_align(request):
    ids = json.loads(request.POST['idsToAlign'])
    mode = request.POST['mode']
    
    if mode == "full":
        return JsonResponse(alignment_full(ids))
    else:
        return JsonResponse(alignment_syllables(ids))

    
@api_view(['POST'])
def chant_align_text(request):
    tmp_url = ''
    ids = JSONParser().parse(request)

    # to make sure the file is empty
    _cleanup(tmp_url + 'tmp.txt')

    # setup mafft
    mafft = Mafft()
    mafft.set_input(tmp_url + 'tmp.txt')
    mafft.add_option('--text')

    sources = []
    urls = []

    for id in ids:
        try:
            chant = Chant.objects.get(pk=id)
            siglum = chant.siglum if chant.siglum else ""
            position = chant.position if chant.position else ""
            folio = chant.folio if chant.folio else ""
            source = siglum + ", " + folio + ", " + position
            sources.append(source)
            urls.append(chant.drupal_path)
        except Chant.DoesNotExist:
            return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                status=status.HTTP_404_NOT_FOUND)

        mafft.add_text(chant.full_text)

    try:
        mafft.run()
    except RuntimeError as e:
        _cleanup(tmp_url + 'tmp.txt')
        return JsonResponse({'message': 'There was a problem with MAFFT'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    sequences = mafft.get_aligned_sequences()
    sequences = [sequence.replace('~', ' ') for sequence in sequences]
    sequences = [[char for char in sequence] for sequence in sequences]
    return JsonResponse({
        'sources': sources,
        'urls': urls,
        'ids': ids,
        'chants': sequences
    })
          

def _cleanup(file):
    if os.path.exists(file):
        os.remove(file)
