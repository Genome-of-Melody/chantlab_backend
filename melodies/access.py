from django.db.models import Q

from melodies.models import Chant

DEFAULT_DATASET_NAMES = ('CantusCorpus v0.2', 'netvor-0.3')


def is_default_dataset_name(name):
    return name in DEFAULT_DATASET_NAMES


def default_dataset_filter():
    return Q(dataset_name__in=DEFAULT_DATASET_NAMES, owner__isnull=True)


def visible_chants(user):
    defaults = default_dataset_filter()
    if user is not None and user.is_authenticated:
        return Chant.objects.filter(defaults | Q(owner=user))
    return Chant.objects.filter(defaults)


def flatten_ids(ids):
    result = []
    if ids is None:
        return result
    for item in ids:
        if isinstance(item, (list, tuple)):
            result.extend(flatten_ids(item))
        else:
            result.append(item)
    return result


def all_ids_visible(user, ids):
    flat = flatten_ids(ids)
    if not flat:
        return True
    visible = set(
        visible_chants(user).filter(pk__in=flat).values_list('id', flat=True)
    )
    return all(item in visible for item in flat)


def user_owns_dataset(user, dataset_idx):
    if user is None or not user.is_authenticated:
        return False
    dataset = Chant.objects.filter(dataset_idx=dataset_idx)
    if not dataset.exists():
        return False
    if is_default_dataset_name(dataset[0].dataset_name):
        return False
    return (
        dataset.filter(owner=user).exists()
        and not dataset.exclude(owner=user).exists()
    )
