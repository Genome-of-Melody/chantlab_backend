from django.http.response import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
import logging
from core.aligner import Aligner
from core import mrbayes
from core.chant_processor import ChantProcessor
from core.exporter import Exporter
from core.uploader import Uploader
import json
import pandas as pd
from django.db.models import Q

from melodies.access import (
    DEFAULT_DATASET_NAMES,
    all_ids_visible,
    is_default_dataset_name,
    ordered_data_sources,
    user_owns_dataset,
    visible_chants,
)
from melodies.models import Chant
from melodies.serializers import ChantSerializer


def _chants_dataframe(chants):
    field_names = [field.name for field in chants.model._meta.fields]
    return pd.DataFrame.from_records(list(chants.values_list()), columns=field_names)


def _validate_new_dataset_name(name, user):
    name = (name or '').strip()
    if not name:
        return None, JsonResponse({'message': 'Dataset name is required'}, status=status.HTTP_400_BAD_REQUEST)
    if is_default_dataset_name(name):
        return None, JsonResponse(
            {'message': 'That name is reserved for a default dataset'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if Chant.objects.filter(owner=user, dataset_name=name).exists():
        return None, JsonResponse(
            {'message': 'You already have a dataset with that name'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return name, None


@api_view(['POST'])
def chant_list(request):
    try:
        data_sources = json.loads(request.POST.get('dataSources', '[]'))
        genres = json.loads(request.POST.get('genres', '[]'))
        offices = json.loads(request.POST.get('offices', '[]'))
        fontes = json.loads(request.POST.get('fontes', '[]'))
        incipit = request.POST.get('incipit', None)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

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

    chants = visible_chants(request.user).filter(filters).order_by('incipit')
    chants_serializer = ChantSerializer(chants, many=True, context={'request': request})
    return JsonResponse(chants_serializer.data, safe=False)


@api_view(['GET'])
def chant_display(request, pk):
    try:
        chant = visible_chants(request.user).get(id=pk)
    except Chant.DoesNotExist:
        return JsonResponse({'message': 'The chant does not exist'}, status=status.HTTP_404_NOT_FOUND)

    try:
        chant_json = ChantProcessor.get_JSON(chant.full_text, chant.volpiano)
    except:
        chant_json = None
    stresses = ChantProcessor.get_stressed_syllables(chant.full_text)
    return JsonResponse({
        'db_source': ChantSerializer(chant, context={'request': request}).data,
        'json_volpiano': json.loads(chant_json) if chant_json else None,
        'stresses': stresses})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_data(request):
    if request.FILES.get('file'):
        file = request.FILES['file']
        name, error = _validate_new_dataset_name(request.POST.get('name'), request.user)
        if error:
            return error

        df = pd.read_csv(file)
        new_index = Uploader.upload_dataframe(df, name, owner=request.user)

        return JsonResponse({
            "name": name,
            "index": new_index
        })

    return JsonResponse({'message': 'File is required'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_volpiano(request):
    id = int(request.POST['id'])
    volpiano = request.POST['volpiano']

    try:
        chant = Chant.objects.get(pk=id, owner=request.user)
    except Chant.DoesNotExist:
        return JsonResponse(
            {'message': 'You can only edit volpiano in your own datasets'},
            status=status.HTTP_403_FORBIDDEN,
        )

    chant.volpiano = volpiano
    chant.save()
    return JsonResponse({"updated": id})


@api_view(['GET'])
def get_data_sources(request):
    return JsonResponse({
        "dataSources": ordered_data_sources(request.user),
        "defaultDatasetNames": list(DEFAULT_DATASET_NAMES),
    })


@api_view(['POST'])
def get_sigla(request):
    data_sources = json.loads(request.POST['dataSources'])
    fontes = visible_chants(request.user).filter(
        dataset_idx__in=data_sources
    ).values_list('siglum').distinct()
    return JsonResponse({"fontes": sorted(list(fontes))})


@api_view(['POST'])
def export_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    visible_ids = list(
        visible_chants(request.user).filter(pk__in=ids).values_list('id', flat=True)
    )
    return Exporter.export_to_csv(visible_ids)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    dataset_name, error = _validate_new_dataset_name(request.POST.get('name'), request.user)
    if error:
        return error

    chants = visible_chants(request.user).filter(pk__in=ids)
    if not chants.exists():
        return JsonResponse({'message': 'No visible chants to copy'}, status=status.HTTP_400_BAD_REQUEST)

    chants_df = _chants_dataframe(chants)
    new_index = Uploader.upload_dataframe(chants_df, dataset_name, owner=request.user)

    return JsonResponse({
        "name": dataset_name,
        "index": new_index
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def add_to_dataset(request):
    ids = json.loads(request.POST['idsToExport'])
    dataset_idx = int(request.POST['idx'])

    if not user_owns_dataset(request.user, dataset_idx):
        return JsonResponse(
            {'message': 'You can only add chants to your own datasets'},
            status=status.HTTP_403_FORBIDDEN,
        )

    chants = visible_chants(request.user).filter(pk__in=ids)
    if not chants.exists():
        return JsonResponse({'message': 'No visible chants to copy'}, status=status.HTTP_400_BAD_REQUEST)

    chants_df = _chants_dataframe(chants)
    dataset_name = Uploader.add_to_dataset(chants_df, dataset_idx, owner=request.user)

    return JsonResponse({
        "name": dataset_name,
        "index": dataset_idx
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_dataset(request):
    dataset_name = request.POST['name']
    if is_default_dataset_name(dataset_name):
        return JsonResponse(
            {'message': 'Default datasets cannot be deleted'},
            status=status.HTTP_403_FORBIDDEN,
        )

    deleted = Uploader.delete_dataset(dataset_name, request.user)
    if not deleted:
        return JsonResponse({'message': 'Dataset not found'}, status=status.HTTP_404_NOT_FOUND)

    return JsonResponse({})


@api_view(['POST'])
def chant_align(request):
    ids = json.loads(request.POST['idsToAlign'])
    mode = request.POST['mode']
    keep_liquescents = json.loads(request.POST['keepLiquescents'])
    concatenated = json.loads(request.POST['concatenated'])

    if not all_ids_visible(request.user, ids):
        return JsonResponse({'message': 'One or more chants are not available'}, status=status.HTTP_403_FORBIDDEN)

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
        if not all_ids_visible(request.user, ids):
            return JsonResponse({
                'newick': "",
                'mbScript': "",
                'nexusAlignment': "",
                'nexusConTre': "",
                'error': 'One or more chants are not available'
            }, status=status.HTTP_403_FORBIDDEN)
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
