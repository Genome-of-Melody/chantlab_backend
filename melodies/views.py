from django.shortcuts import render
from django.db.models import Max

from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status
 
from melodies.models import Chant
from melodies.serializers import ChantSerializer
from rest_framework.decorators import api_view

from core.aligner import Aligner
from core.chant_processor import ChantProcessor
from core.exporter import Exporter
from core.uploader import Uploader
import json
import pandas as pd

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
        chant_json = ChantProcessor.get_JSON(chant.full_text, chant.volpiano)
    except:
        chant_json = None
    stresses = ChantProcessor.get_stressed_syllables(chant.full_text)
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

        new_index = Uploader.upload_dataframe(df, name)

        return JsonResponse({
            "name": name,
            "index": new_index
        })


@api_view(['GET'])
def get_sources(request):
    sources = Chant.objects.values_list('dataset_idx', 'dataset_name').distinct()
    return JsonResponse({"sources": list(sources)})


@api_view(['POST'])
def export_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    return Exporter.export_to_csv(ids)


@api_view(['POST'])
def create_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    dataset_name = request.POST['name']

    chants = Chant.objects.filter(pk__in=ids)
    chants_df = pd.DataFrame.from_records(
        chants.values_list()
    )
    opts = chants.model._meta
    field_names = [field.name for field in opts.fields]
    chants_df.columns = field_names

    new_index = Uploader.upload_dataframe(chants_df, dataset_name)

    return JsonResponse({
        "name": dataset_name,
        "index": new_index
    })


@api_view(['POST'])
def chant_align(request):
    ids = json.loads(request.POST['idsToAlign'])
    mode = request.POST['mode']
    
    if mode == "full":
        return JsonResponse(Aligner.alignment_pitches(ids))
    elif mode == "intervals":
        return JsonResponse(Aligner.alignment_intervals(ids))
    else:
        return JsonResponse(Aligner.alignment_syllables(ids))

    
@api_view(['POST'])
def chant_align_text(request):
    
    return JsonResponse({})
