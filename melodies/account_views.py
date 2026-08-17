import json
import logging

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http.response import JsonResponse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from melodies.models import SavedAlignment, UserSettings


def _request_value(request, key, default=None):
    if hasattr(request, 'data') and key in request.data:
        return request.data.get(key)
    return request.POST.get(key, default)


def _token_payload(user):
    token, _ = Token.objects.get_or_create(user=user)
    return {
        'token': token.key,
        'username': user.username,
        'id': user.id,
    }


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    username = (_request_value(request, 'username') or '').strip()
    password = _request_value(request, 'password') or ''

    if not username or not password:
        return JsonResponse(
            {'message': 'Username and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(username=username).exists():
        return JsonResponse(
            {'message': 'That username is already taken'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(password)
    except ValidationError as exc:
        return JsonResponse(
            {'message': ' '.join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User.objects.create_user(username=username, password=password)
    return JsonResponse(_token_payload(user), status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    username = (_request_value(request, 'username') or '').strip()
    password = _request_value(request, 'password') or ''

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return JsonResponse(
            {'message': 'Invalid username or password'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not user.check_password(password) or not user.is_active:
        return JsonResponse(
            {'message': 'Invalid username or password'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return JsonResponse(_token_payload(user))


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    Token.objects.filter(user=request.user).delete()
    return JsonResponse({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return JsonResponse({
        'id': request.user.id,
        'username': request.user.username,
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def alignment_list(request):
    if request.method == 'GET':
        alignments = SavedAlignment.objects.filter(user=request.user).order_by('name')
        return JsonResponse({
            'alignments': [{'name': item.name} for item in alignments]
        })

    name = (_request_value(request, 'name') or '').strip()
    data = _request_value(request, 'data')
    if not name:
        return JsonResponse({'message': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)
    if data is None:
        return JsonResponse({'message': 'Alignment data is required'}, status=status.HTTP_400_BAD_REQUEST)

    if not isinstance(data, str):
        data = json.dumps(data)

    alignment, _created = SavedAlignment.objects.update_or_create(
        user=request.user,
        name=name,
        defaults={'data': data},
    )
    return JsonResponse({'name': alignment.name})


@api_view(['GET', 'DELETE'])
@permission_classes([IsAuthenticated])
def alignment_detail(request, name):
    try:
        alignment = SavedAlignment.objects.get(user=request.user, name=name)
    except SavedAlignment.DoesNotExist:
        return JsonResponse({'message': 'Alignment not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'DELETE':
        alignment.delete()
        return JsonResponse({'ok': True})

    try:
        payload = json.loads(alignment.data)
    except json.JSONDecodeError:
        payload = alignment.data
    return JsonResponse({'name': alignment.name, 'data': payload})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def user_settings(request):
    settings_row, _created = UserSettings.objects.get_or_create(
        user=request.user,
        defaults={'data': '{}'},
    )

    if request.method == 'GET':
        try:
            payload = json.loads(settings_row.data)
        except json.JSONDecodeError:
            payload = {}
        return JsonResponse({'settings': payload})

    data = _request_value(request, 'settings')
    if data is None:
        data = request.data
    if isinstance(data, dict) and 'settings' in data and 'alignment' not in data:
        data = data.get('settings') or {}
    if data is None:
        data = {}
    if isinstance(data, str):
        settings_row.data = data
    else:
        settings_row.data = json.dumps(data)
    settings_row.save()
    return JsonResponse({'ok': True})
