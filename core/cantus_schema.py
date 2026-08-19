'''CantusCorpus v1.0 CSV schema and v0.2 compatibility mapping.

Download format matches the published chants.csv header
(chantlink … full_text, melody, db, image). There is no century column
on chants. ``volpiano`` is accepted on upload as an alias of ``melody``.
'''

import math
import os
import re

import pandas as pd
from django.conf import settings

# Exact chants.csv columns from the published CantusCorpus v1.0 file.
V1_EXPORT_FIELDS = (
    'chantlink',
    'incipit',
    'cantus_id',
    'mode',
    'siglum',
    'position',
    'folio',
    'sequence',
    'feast',
    'feast_code',
    'genre',
    'office',
    'srclink',
    'melody_id',
    'full_text',
    'melody',
    'db',
    'image',
)

# User/CSV must never set these; they are assigned by ChantLab.
PROTECTED_FIELDS = frozenset({
    'id',
    'owner',
    'owner_id',
    'is_owned',
    'dataset_name',
    'dataset_idx',
})

LINK_FIELDS = frozenset({'chantlink', 'srclink', 'image'})
_UNSAFE_LINK_SCHEMES = (
    'javascript:',
    'data:',
    'vbscript:',
    'file:',
    'about:',
)
_MAX_UPLOAD_ROWS = 1_000_000
_MAX_CELL_CHARS = 100_000
_COLUMN_NAME_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')

# Apply v0.2 names first, then v1.0 names so a mixed file prefers v1.0.
_V02_TO_DB = {
    'drupal_path': 'chantlink',
    'source_id': 'srclink',
    'notes': 'image',
    'volpiano': 'volpiano',
    'feast_id': 'feast_id',
    'genre_id': 'genre_id',
    'office_id': 'office_id',
    'century_code': 'century_code',
    'century': 'century_code',
    'corpus_id': 'corpus_id',
    'incipit': 'incipit',
    'cantus_id': 'cantus_id',
    'mode': 'mode',
    'finalis': 'finalis',
    'differentia': 'differentia',
    'siglum': 'siglum',
    'position': 'position',
    'folio': 'folio',
    'sequence': 'sequence',
    'marginalia': 'marginalia',
    'cao_concordances': 'cao_concordances',
    'melody_id': 'melody_id',
    'full_text': 'full_text',
    'full_text_manuscript': 'full_text_manuscript',
}

_V1_TO_DB = {
    'chantlink': 'chantlink',
    'srclink': 'srclink',
    'image': 'image',
    'volpiano': 'volpiano',
    'melody': 'volpiano',
    'feast': 'feast_id',
    'genre': 'genre_id',
    'office': 'office_id',
    'db': 'db',
    'cantus_id': 'cantus_id',
    'incipit': 'incipit',
    'siglum': 'siglum',
    'folio': 'folio',
    'sequence': 'sequence',
    'position': 'position',
    'melody_id': 'melody_id',
    'mode': 'mode',
    'full_text': 'full_text',
}

_LOOKUP_CACHE = {}


class UploadError(ValueError):
    '''Raised when an uploaded CSV cannot be imported safely.'''


def text_value(value):
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() in ('nan', 'none', 'null', '<na>'):
        return None
    if len(text) > _MAX_CELL_CHARS:
        return text[:_MAX_CELL_CHARS]
    return text


def safe_link(value):
    '''Keep catalogue URLs/ids; drop javascript/data/file schemes and markup.'''
    text = text_value(value)
    if text is None:
        return None
    if any(ch in text for ch in ('\n', '\r', '\x00', '<', '>')):
        return None
    lowered = text.lstrip().lower()
    if lowered.startswith(_UNSAFE_LINK_SCHEMES):
        return None
    return text


def _looks_like_url(value):
    text = text_value(value)
    if text is None:
        return False
    lowered = text.lower()
    return lowered.startswith('http://') or lowered.startswith('https://') or '://' in text


def _static_csv_path(filename):
    return os.path.join(settings.BASE_DIR, 'scripts', 'static', filename)


def _lookup_table(filename, name_column='name'):
    cache_key = (filename, name_column)
    cached = _LOOKUP_CACHE.get(cache_key)
    if cached is not None:
        return cached

    path = _static_csv_path(filename)
    id_to_name = {}
    name_to_id = {}
    canonical_ids = {}
    id_to_code = {}
    if os.path.exists(path):
        table = pd.read_csv(path, dtype=str)
        for _, row in table.iterrows():
            item_id = text_value(row.get('id'))
            name = text_value(row.get(name_column))
            if not item_id:
                continue
            canonical_ids[item_id] = item_id
            canonical_ids[item_id.lower()] = item_id
            id_to_name[item_id] = name or item_id
            if name:
                name_to_id.setdefault(name, item_id)
                name_to_id.setdefault(name.lower(), item_id)
            feast_code = text_value(row.get('feast_code'))
            if feast_code:
                name_to_id.setdefault(feast_code, item_id)
                id_to_code[item_id] = feast_code
                id_to_code[item_id.lower()] = feast_code
    mapping = {
        'id_to_name': id_to_name,
        'name_to_id': name_to_id,
        'canonical_ids': canonical_ids,
        'id_to_code': id_to_code,
    }
    _LOOKUP_CACHE[cache_key] = mapping
    return mapping


def _normalize_catalog_id(value, filename):
    key = text_value(value)
    if key is None:
        return None
    table = _lookup_table(filename)
    if key in table['canonical_ids']:
        return table['canonical_ids'][key]
    return (
        table['name_to_id'].get(key)
        or table['name_to_id'].get(key.lower())
        or key
    )


def _catalog_name_for_export(value, filename):
    key = text_value(value)
    if key is None:
        return ''
    table = _lookup_table(filename)
    canonical = table['canonical_ids'].get(key) or table['canonical_ids'].get(key.lower())
    if canonical:
        return table['id_to_name'].get(canonical) or canonical
    return key


def normalize_genre_id(value):
    return _normalize_catalog_id(value, 'genre.csv')


def normalize_office_id(value):
    return _normalize_catalog_id(value, 'office.csv')


def normalize_feast_id(value):
    return _normalize_catalog_id(value, 'feast.csv')


def genre_for_export(value):
    return _catalog_name_for_export(value, 'genre.csv')


def office_for_export(value):
    return _catalog_name_for_export(value, 'office.csv')


def feast_for_export(value):
    return _catalog_name_for_export(value, 'feast.csv')


def feast_code_for_export(value):
    key = text_value(value)
    if key is None:
        return ''
    table = _lookup_table('feast.csv')
    canonical = table['canonical_ids'].get(key) or table['canonical_ids'].get(key.lower())
    if canonical:
        return table['id_to_code'].get(canonical) or ''
    return table['id_to_code'].get(key) or ''


def century_code_from_value(value):
    text = text_value(value)
    if text is None:
        return None
    if text.startswith('century_'):
        return text
    try:
        century = int(float(text))
    except (TypeError, ValueError):
        return text
    if century <= 0:
        return None
    start = (century - 1) * 100
    return 'century_{}_{}'.format(start, start + 99)


def century_for_export(century_code):
    text = text_value(century_code)
    if text is None:
        return ''
    if text.startswith('century_'):
        parts = text.split('_')
        if len(parts) >= 2:
            try:
                start_year = int(parts[1])
                return str((start_year // 100) + 1)
            except (TypeError, ValueError):
                return text
    return text


def export_cell(value):
    text = text_value(value)
    return '' if text is None else text


def chant_to_v1_row(chant):
    '''Map a Chant model instance to a CantusCorpus v1.0 chants.csv row.'''
    return {
        'chantlink': export_cell(chant.chantlink),
        'incipit': export_cell(chant.incipit),
        'cantus_id': export_cell(chant.cantus_id),
        'mode': export_cell(chant.mode),
        'siglum': export_cell(chant.siglum),
        'position': export_cell(chant.position),
        'folio': export_cell(chant.folio),
        'sequence': export_cell(chant.sequence),
        'feast': feast_for_export(chant.feast_id),
        'feast_code': feast_code_for_export(chant.feast_id),
        'genre': genre_for_export(chant.genre_id),
        'office': office_for_export(chant.office_id),
        'srclink': export_cell(chant.srclink),
        'melody_id': export_cell(chant.melody_id),
        'full_text': export_cell(chant.full_text),
        'melody': export_cell(chant.volpiano),
        'db': export_cell(chant.db),
        'image': export_cell(chant.image),
    }


def _columns_by_lower(df):
    mapping = {}
    for column in df.columns:
        key = str(column).strip()
        lower = key.lower()
        if lower and lower not in mapping:
            mapping[lower] = column
    return mapping


def _copy_mapped_column(source, dest, src_name, dest_name, existing_lower):
    if dest_name in dest.columns:
        return
    src_col = existing_lower.get(src_name)
    if src_col is None:
        return
    dest[dest_name] = source[src_col]


def normalize_chant_dataframe(df):
    '''Map a v1.0 or v0.2 CSV/dataframe onto ChantLab database columns.

    Extra columns are dropped. Protected columns are ignored. Missing
    database columns are left absent so the caller can fill defaults.
    '''
    if df is None or not hasattr(df, 'columns'):
        raise UploadError('The uploaded file is not a valid CSV table')
    if len(df.index) > _MAX_UPLOAD_ROWS:
        raise UploadError('The CSV file has too many rows')

    source = df.copy()
    source.columns = [str(column).strip() for column in source.columns]
    lower = _columns_by_lower(source)
    mapped = pd.DataFrame(index=source.index)

    for csv_name, db_name in _V02_TO_DB.items():
        _copy_mapped_column(source, mapped, csv_name, db_name, lower)
    for csv_name, db_name in _V1_TO_DB.items():
        if db_name in mapped.columns:
            src_col = lower.get(csv_name)
            if src_col is None:
                continue
            mapped[db_name] = source[src_col]
        else:
            _copy_mapped_column(source, mapped, csv_name, db_name, lower)

    id_col = lower.get('id')
    if id_col is not None:
        from_id = source[id_col].map(lambda value: text_value(value) if _looks_like_url(value) else None)
        if 'chantlink' not in mapped.columns:
            mapped['chantlink'] = from_id
        else:
            mapped['chantlink'] = mapped['chantlink'].where(mapped['chantlink'].notna(), from_id)

    if 'genre_id' in mapped.columns:
        mapped['genre_id'] = mapped['genre_id'].map(normalize_genre_id)
    if 'office_id' in mapped.columns:
        mapped['office_id'] = mapped['office_id'].map(normalize_office_id)
    if 'feast_id' in mapped.columns:
        mapped['feast_id'] = mapped['feast_id'].map(normalize_feast_id)
    feast_code_col = lower.get('feast_code')
    if feast_code_col is not None:
        from_code = source[feast_code_col].map(normalize_feast_id)
        if 'feast_id' not in mapped.columns:
            mapped['feast_id'] = from_code
        else:
            mapped['feast_id'] = mapped['feast_id'].where(mapped['feast_id'].notna(), from_code)
    if 'century_code' in mapped.columns:
        mapped['century_code'] = mapped['century_code'].map(century_code_from_value)

    for field in LINK_FIELDS:
        if field in mapped.columns:
            mapped[field] = mapped[field].map(safe_link)

    for column in list(mapped.columns):
        if column in PROTECTED_FIELDS or not _COLUMN_NAME_RE.match(column):
            mapped.drop(columns=[column], inplace=True)

    return mapped


def float_or_none(value):
    text = text_value(value)
    if text is None:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number
