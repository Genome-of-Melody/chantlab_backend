from django.shortcuts import render
from django.db.models import Max

from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status
 
from melodies.models import Chant
from melodies.serializers import ChantSerializer
from rest_framework.decorators import api_view

from core.alignment import get_volpiano_syllable_alignment, combine_volpiano_and_text, align_syllables_and_volpiano
from core.chant import get_JSON, get_stressed_syllables, get_syllables_from_text
from core.mafft import Mafft
import json
import os
import pandas as pd
import sqlite3
import os

@api_view(['POST'])
def chant_list(request):
    data_sources = json.loads(request.POST['dataSources'])
    incipit = request.POST['incipit']
    chants = Chant.objects.filter(dataset_idx__in=data_sources)

    if incipit is not None:
        chants = chants.filter(incipit__icontains=incipit)
    
    chants_serializer = ChantSerializer(chants, many=True)
    return JsonResponse(chants_serializer.data, safe=False)


    # if request.method == 'GET':
    #     melodies = Chant.objects.all()
        
    #     title = request.GET.get('incipit', None)
    #     if title is not None:
    #         melodies = melodies.filter(incipit__icontains=title)
        
    #     melodies_serializer = ChantSerializer(melodies, many=True)
    #     return JsonResponse(melodies_serializer.data, safe=False)
    #     # 'safe=False' for objects serialization
    # elif request.method == 'POST':
    #     melody_data = JSONParser().parse(request)
    #     melody_serializer = ChantSerializer(data=melody_data)
    #     if melody_serializer.is_valid():
    #         melody_serializer.save()
    #         return JsonResponse(melody_serializer.data, status=status.HTTP_201_CREATED) 
    #     return JsonResponse(melody_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    # elif request.method == 'DELETE':
    #     count = Chant.objects.all().delete()
    #     return JsonResponse({'message': '{} Melodies were deleted successfully!'.format(count[0])}, status=status.HTTP_204_NO_CONTENT)
 
 
# @api_view(['GET'])
# def chant_detail(request, pk):
#     # find chant by pk (id)
#     try: 
#         melody = Chant.objects.get(pk=pk) 
#     except Chant.DoesNotExist: 
#         return JsonResponse({'message': 'The melody does not exist'}, status=status.HTTP_404_NOT_FOUND) 

#     if request.method == 'GET': 
#         melody_serializer = ChantSerializer(melody) 
#         return JsonResponse(melody_serializer.data)
#     elif request.method == 'PUT': 
#         melody_data = JSONParser().parse(request) 
#         melody_serializer = ChantSerializer(melody, data=melody_data) 
#         if melody_serializer.is_valid(): 
#             melody_serializer.save() 
#             return JsonResponse(melody_serializer.data) 
#         return JsonResponse(melody_serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
#     elif request.method == 'DELETE': 
#         melody.delete() 
#         return JsonResponse({'message': 'Chant was deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)


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
        # establish db connection
        con = sqlite3.connect("chants.db")

        # read the provided file
        df = pd.read_csv(request.FILES['file'])

        # change the database to fit the format
        df.rename(columns={'id': 'corpus_id'}, inplace=True)
        df.drop(['Unnamed: 0'], axis=1, inplace=True)
        df['dataset_name'] = request.POST['name']
        max_idx = Chant.objects.aggregate(Max('dataset_idx'))['dataset_idx__max']
        new_index = max_idx + 1
        df['dataset_idx'] = new_index

        # append data to database
        df.to_sql('chant', con, if_exists='append', index=True, index_label="id")

        return JsonResponse({
            "name": request.POST['name'],
            "index": new_index})


@api_view(['GET'])
def get_sources(request):
    sources = Chant.objects.values_list('dataset_idx', 'dataset_name').distinct()
    return JsonResponse({"sources": list(sources)})


@api_view(['POST'])
def chant_align(request):
    ids = json.loads(request.POST['idsToAlign'])
    mode = request.POST['mode']
    
    tmp_url = ''

    # to make sure the file is empty
    _cleanup(tmp_url + 'tmp.txt')

    # setup mafft
    mafft = Mafft()
    mafft.set_input(tmp_url + 'tmp.txt')
    mafft.add_option('--text')

    # save errors
    error_sources = []
    finished = False

    # iterate until there are no alignment errors
    while not finished:
        finished = True

        sources = []
        urls = []
        texts = []
        volpianos = []

        success_sources = []
        success_ids = []
        success_volpianos = []
        success_urls = []

        # store chant data
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

            mafft.add_volpiano(chant.volpiano)
            volpianos.append(chant.volpiano)
            texts.append(chant.full_text)

        # align the melodies
        try:
            mafft.run()
        except RuntimeError as e:
            _cleanup(tmp_url + 'tmp.txt')
            return JsonResponse({'message': 'There was a problem with MAFFT'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # retrieve alignments
        sequences = mafft.get_aligned_sequences()

        # try aligning melody and text
        syllables = [get_syllables_from_text(text) for text in texts]
        chants = []
        next_iteration_ids = []
        for i, sequence in enumerate(sequences):
            try:
                chants.append(align_syllables_and_volpiano(syllables[i], sequence))
                success_sources.append(sources[i])
                success_ids.append(ids[i])
                success_volpianos.append(sequence)
                success_urls.append(urls[i])
                # store chant id in case it is going to be aligned again
                next_iteration_ids.append(ids[i])
            except RuntimeError as e:
                # found an error, the alignment will be run again
                finished = False
                error_sources.append(sources[i])

        ids = next_iteration_ids
        _cleanup(tmp_url + 'tmp.txt')

    response = JsonResponse({
        'chants': chants,
        'errors': error_sources, 
        'success': {
            'sources': success_sources,
            'ids': success_ids,
            'volpianos': success_volpianos,
            'urls': success_urls
        }})

    return response


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
