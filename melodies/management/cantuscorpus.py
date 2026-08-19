import pandas as pd
from core.cantus_schema import (
    century_code_from_value,
    normalize_feast_id,
    normalize_genre_id,
    normalize_office_id,
    text_value,
)

DATASET_NAME = 'CantusCorpus v1.0'
PYCANTUS_DATASET_KEY = 'cantuscorpus_v1.0'


def load_cantuscorpus():
    '''Load CantusCorpus v1.0 from PyCantus and map it to the ChantLab schema.

    Uses ``pycantus.data.load_dataset``, which reads the packaged CSVs or
    downloads them from the CantusCorpus GitHub release if they are missing.
    All catalogue records are kept, including those without Volpiano.
    The chant list API hides them by default (hideChantsWithoutVolpiano).
    '''
    from pycantus.data import load_dataset

    corpus = load_dataset(PYCANTUS_DATASET_KEY)

    century_by_link = {
        source.srclink: source.numeric_century
        for source in corpus.sources
        if source.srclink
    }

    rows = []
    for chant in corpus.chants:
        century = chant.century if chant.century is not None else century_by_link.get(chant.srclink)
        sequence = pd.to_numeric(text_value(chant.sequence), errors='coerce')
        rows.append({
            'incipit': text_value(chant.incipit),
            'cantus_id': text_value(chant.cantus_id),
            'mode': text_value(chant.mode),
            'siglum': text_value(chant.siglum),
            'position': text_value(chant.position),
            'folio': text_value(chant.folio),
            'sequence': None if pd.isna(sequence) else float(sequence),
            'feast_id': normalize_feast_id(chant.feast),
            'genre_id': normalize_genre_id(chant.genre),
            'office_id': normalize_office_id(chant.office),
            'srclink': text_value(chant.srclink),
            'melody_id': text_value(chant.melody_id),
            'chantlink': text_value(chant.chantlink),
            'db': text_value(chant.db),
            'full_text': text_value(chant.full_text) or '',
            'volpiano': text_value(chant.melody),
            'image': text_value(chant.image),
            'dataset_name': DATASET_NAME,
            'century_code': century_code_from_value(century),
        })
    return pd.DataFrame(rows)
