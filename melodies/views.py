from django.shortcuts import render
from django.db.models import Max

from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status
 
from melodies.models import Chant
from melodies.serializers import ChantSerializer
from rest_framework.decorators import api_view
import logging
from core.aligner import Aligner
from core import mrbayes
from core.chant_processor import ChantProcessor
from core.exporter import Exporter
from core.uploader import Uploader
import json
import pandas as pd
from django.db.models import Q



@api_view(['POST'])
def chant_list(request):
    # Parse all filters once
    try:
        data_sources = json.loads(request.POST.get('dataSources', '[]'))
        genres = json.loads(request.POST.get('genres', '[]'))
        offices = json.loads(request.POST.get('offices', '[]'))
        fontes = json.loads(request.POST.get('fontes', '[]'))
        incipit = request.POST.get('incipit', None)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Build filters dynamically
    filters = Q()
    
    if data_sources:
        filters &= Q(dataset_idx__in=data_sources)
    if genres:
        filters &= Q(genre_id__in=genres)
    if offices:
        filters &= Q(office_id__in=offices)
    if fontes:
        filters &= Q(siglum__in=fontes)
    if incipit:
        filters &= Q(incipit__icontains=incipit)

    # Query with combined filters and ordering
    chants = Chant.objects.filter(filters).order_by('incipit')

    # Serialize and return the results
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


@api_view(['POST'])
def update_volpiano(request):
    id = int(request.POST['id'])
    volpiano = request.POST['volpiano']

    chant = Chant.objects.get(pk=id)
    chant.volpiano = volpiano
    chant.save()
    return JsonResponse({"updated": id})


@api_view(['GET'])
def get_data_sources(request):
    data_sources = Chant.objects.values_list('dataset_idx', 'dataset_name').distinct()
    return JsonResponse({"dataSources": list(data_sources)})


@api_view(['POST'])
def get_sigla(request):
    data_sources = json.loads(request.POST['dataSources'])

    # This needs to be re-done so that only fontes pertaining to the current
    # dataset selection are displayed.
    fontes = Chant.objects.filter(dataset_idx__in=data_sources).values_list('siglum').distinct()
    return JsonResponse({"fontes": sorted(list(fontes))})


@api_view(['POST'])
def export_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    return Exporter.export_to_csv(ids)


@api_view(['POST'])
def create_dataset(request):
    print('Creating dataset with name: {}'.format(request.POST['name']))

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


@api_view(['GET', 'POST'])
def add_to_dataset(request):

    ids = json.loads(request.POST['idsToExport'])
    dataset_idx = int(request.POST['idx'])

    chants = Chant.objects.filter(pk__in=ids)
    chants_df = pd.DataFrame.from_records(
       chants.values_list()
    )
    opts = chants.model._meta
    field_names = [field.name for field in opts.fields]
    chants_df.columns = field_names

    dataset_name = Uploader.add_to_dataset(chants_df, dataset_idx)

    return JsonResponse({
        "name": dataset_name,
        "index": dataset_idx
    })


@api_view(['POST'])
def delete_dataset(request):
    dataset_name = request.POST['name']

    Uploader.delete_dataset(dataset_name)

    return JsonResponse({})


@api_view(['POST'])
def chant_align(request):
    ids = json.loads(request.POST['idsToAlign'])
    mode = request.POST['mode']
    keep_liquescents = request.POST['keep_liquescents']
    concatenated = json.loads(request.POST['concatenated'])
    
    if mode == "full":
        return JsonResponse(Aligner.alignment_pitches(ids, concatenated, keep_liquescents))
    elif mode == "intervals":
        return JsonResponse(Aligner.alignment_intervals(ids, concatenated, keep_liquescents))
    else:
        return JsonResponse(Aligner.alignment_syllables(ids, concatenated, keep_liquescents))

    
@api_view(['POST'])
def chant_align_text(request):
    
    return JsonResponse({})

@api_view(['POST'])
def mrbayes_volpiano(request):
    try:
        ids = json.loads(request.POST['ids'])
        alpianos = json.loads(request.POST['alpianos'])
        alignment_names = json.loads(request.POST['alignment_names'])
        number_of_generations = int(request.POST['numberOfGenerations'])
        return JsonResponse(mrbayes.mrbayes_analyzis(ids, alpianos, number_of_generations, alignment_names))
    except Exception as e:
        logging.error("mrbayes volpiano error: {}".format(e))
        return JsonResponse({
            'newick': "",
            'mbScript': "",
            'nexusAlignment': "",
            'nexusConTre': "",
            'error': str(e)
        })