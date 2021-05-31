from django.shortcuts import render

from django.http.response import JsonResponse
from rest_framework.parsers import JSONParser 
from rest_framework import status
 
from melodies.models import Chant
from melodies.serializers import ChantSerializer
from rest_framework.decorators import api_view

from core.chant import get_JSON, get_stressed_syllables, get_syllables, align_syllables_and_volpiano
from core.mafft import Mafft
import json
import os

@api_view(['GET'])
def melody_list(request):
    if request.method == 'GET':
        melodies = Chant.objects.all()
        
        title = request.GET.get('incipit', None)
        if title is not None:
            melodies = melodies.filter(incipit__icontains=title)
        
        melodies_serializer = ChantSerializer(melodies, many=True)
        return JsonResponse(melodies_serializer.data, safe=False)
        # 'safe=False' for objects serialization
    elif request.method == 'POST':
        melody_data = JSONParser().parse(request)
        melody_serializer = ChantSerializer(data=melody_data)
        if melody_serializer.is_valid():
            melody_serializer.save()
            return JsonResponse(melody_serializer.data, status=status.HTTP_201_CREATED) 
        return JsonResponse(melody_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    elif request.method == 'DELETE':
        count = Chant.objects.all().delete()
        return JsonResponse({'message': '{} Melodies were deleted successfully!'.format(count[0])}, status=status.HTTP_204_NO_CONTENT)
 
 
@api_view(['GET'])
def melody_detail(request, pk):
    # find chant by pk (id)
    try: 
        melody = Chant.objects.get(id=pk) 
    except Chant.DoesNotExist: 
        return JsonResponse({'message': 'The melody does not exist'}, status=status.HTTP_404_NOT_FOUND) 

    if request.method == 'GET': 
        melody_serializer = ChantSerializer(melody) 
        return JsonResponse(melody_serializer.data)
    elif request.method == 'PUT': 
        melody_data = JSONParser().parse(request) 
        melody_serializer = ChantSerializer(melody, data=melody_data) 
        if melody_serializer.is_valid(): 
            melody_serializer.save() 
            return JsonResponse(melody_serializer.data) 
        return JsonResponse(melody_serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
    elif request.method == 'DELETE': 
        melody.delete() 
        return JsonResponse({'message': 'Chant was deleted successfully!'}, status=status.HTTP_204_NO_CONTENT)


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
    print(request.FILES)
    if request.FILES['fileKey']:
        print("file uploaded")
        return JsonResponse({"result": "done"})


@api_view(['POST'])
def chant_align(request):
    tmp_url = ''
    ids = JSONParser().parse(request)

    # to make sure the file is empty
    _cleanup(tmp_url + 'tmp.txt')

    texts = []
    mafft = Mafft()
    mafft.set_input(tmp_url + 'tmp.txt')
    mafft.add_option('--text')

    # save errors
    sources = []
    urls = []
    error_sources = []
    success_sources = []
    success_ids = []
    success_volpianos = []
    success_urls = []

    for id in ids:
        try:
            chant = Chant.objects.get(id=id)
            siglum = chant.siglum if chant.siglum else ""
            position = chant.position if chant.position else ""
            folio = chant.folio if chant.folio else ""
            source = siglum + ", " + position + ", " + folio
            sources.append(source)
            urls.append(chant.drupal_path)
        except Chant.DoesNotExist:
            return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                status=status.HTTP_404_NOT_FOUND)

        mafft.add_volpiano(chant.volpiano)
        texts.append(chant.full_text)

    try:
        mafft.run()
    except RuntimeError as e:
        _cleanup(tmp_url + 'tmp.txt')
        return JsonResponse({'message': 'There was a problem with MAFFT'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    sequences = mafft.get_aligned_sequences()
    syllables = [get_syllables(text) for text in texts]
    chants = []
    for i, sequence in enumerate(sequences):
        try:
            chants.append(align_syllables_and_volpiano(syllables[i], sequence))
            success_sources.append(sources[i])
            success_ids.append(ids[i])
            success_volpianos.append(sequence)
            success_urls.append(urls[i])
        except RuntimeError as e:
            error_sources.append(sources[i])

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
          

def _cleanup(file):
    if os.path.exists(file):
        os.remove(file)
