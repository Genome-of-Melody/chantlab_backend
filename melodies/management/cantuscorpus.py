import os

import pandas as pd
from django.conf import settings

DATASET_NAME = 'CantusCorpus v1.0'
PYCANTUS_DATASET_KEY = 'cantuscorpus_v1.0'


def _text(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() == 'nan':
        return None
    return text


def _lookup_map(csv_path, key_column):
    table = pd.read_csv(csv_path, dtype=str)
    mapping = {}
    for _, row in table.iterrows():
        key = _text(row.get(key_column))
        value = row.get('id')
        if key and value and key not in mapping:
            mapping[key] = value
            mapping[key.lower()] = value
    return mapping


def _lookup(mapping, value):
    key = _text(value)
    if key is None:
        return None
    return mapping.get(key) or mapping.get(key.lower())


def _century_code(num_century):
    try:
        century = int(float(num_century))
    except (TypeError, ValueError):
        return None
    start = (century - 1) * 100
    return 'century_{}_{}'.format(start, start + 99)


def load_cantuscorpus():
    '''Load CantusCorpus v1.0 from PyCantus and map it to the ChantLab schema.

    Uses ``pycantus.data.load_dataset``, which reads the packaged CSVs or
    downloads them from the CantusCorpus GitHub release if they are missing.
    Only chants with a melody are kept.
    '''
    from pycantus.data import load_dataset

    corpus = load_dataset(PYCANTUS_DATASET_KEY, is_editable=True)
    corpus.keep_melodic_chants()

    static_dir = os.path.join(settings.BASE_DIR, 'scripts', 'static')
    genre_map = _lookup_map(os.path.join(static_dir, 'genre.csv'), 'name')
    office_map = _lookup_map(os.path.join(static_dir, 'office.csv'), 'name')
    feast_map = _lookup_map(os.path.join(static_dir, 'feast.csv'), 'name')
    century_by_link = {
        source.srclink: source.numeric_century
        for source in corpus.sources
        if source.srclink
    }

    rows = []
    for chant in corpus.chants:
        century = chant.century if chant.century is not None else century_by_link.get(chant.srclink)
        sequence = pd.to_numeric(_text(chant.sequence), errors='coerce')
        rows.append({
            'incipit': _text(chant.incipit),
            'cantus_id': _text(chant.cantus_id),
            'mode': _text(chant.mode),
            'siglum': _text(chant.siglum),
            'position': _text(chant.position),
            'folio': _text(chant.folio),
            'sequence': None if pd.isna(sequence) else float(sequence),
            'feast_id': _lookup(feast_map, chant.feast),
            'genre_id': _lookup(genre_map, chant.genre),
            'office_id': _lookup(office_map, chant.office),
            'source_id': _text(chant.srclink),
            'melody_id': _text(chant.melody_id),
            'drupal_path': _text(chant.chantlink),
            'full_text': _text(chant.full_text),
            'volpiano': _text(chant.melody),
            'dataset_name': DATASET_NAME,
            'century_code': _century_code(century),
        })
    return pd.DataFrame(rows)
