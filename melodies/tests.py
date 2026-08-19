from io import StringIO

import pandas as pd
from django.contrib.auth.models import User
from django.test import TestCase

from core.cantus_schema import (
    V1_EXPORT_FIELDS,
    chant_to_v1_row,
    normalize_chant_dataframe,
    safe_link,
)
from core.exporter import Exporter
from core.uploader import Uploader
from melodies.models import Chant


class CantusSchemaTests(TestCase):
    def test_v1_columns_map_to_db_fields(self):
        df = pd.DataFrame([{
            'cantus_id': '007129a',
            'incipit': 'Non sufficiens',
            'siglum': 'A-ABC Fragm. 1',
            'srclink': 'https://example.org/source/123',
            'chantlink': 'https://example.org/chant/456',
            'folio': '001v',
            'db': 'CD',
            'sequence': '1',
            'feast': 'Abdonis, Sennis',
            'genre': 'A',
            'office': 'M',
            'position': '01',
            'melody_id': '001216m1',
            'image': 'https://example.org/image/1',
            'mode': '1',
            'full_text': 'Non sufficiens sibi',
            'melody': '1---d---d---4',
            'feast_code': '14073000',
            'extra_unknown': 'drop me',
        }])
        mapped = normalize_chant_dataframe(df)
        row = mapped.iloc[0]
        self.assertNotIn('extra_unknown', mapped.columns)
        self.assertEqual(row['cantus_id'], '007129a')
        self.assertEqual(row['chantlink'], 'https://example.org/chant/456')
        self.assertEqual(row['srclink'], 'https://example.org/source/123')
        self.assertEqual(row['image'], 'https://example.org/image/1')
        self.assertEqual(row['volpiano'], '1---d---d---4')
        self.assertEqual(row['genre_id'], 'genre_a')
        self.assertEqual(row['office_id'], 'office_m')
        self.assertEqual(row['feast_id'], 'feast_0001')
        self.assertEqual(row['db'], 'CD')

    def test_v02_columns_are_aliased(self):
        df = pd.DataFrame([{
            'id': 46,
            'incipit': 'A timore',
            'cantus_id': '1196',
            'siglum': 'NL-Uu 406',
            'source_id': 'https://example.org/source/573',
            'drupal_path': 'https://example.org/chant/493007',
            'notes': 'https://example.org/image/old',
            'volpiano': '1---f---4',
            'full_text': 'A timore inimici',
            'genre_id': 'genre_a',
            'office_id': 'office_m',
            'feast_id': 'feast_0696',
            'century_code': 'century_1100_1199',
            'dataset_idx': 99,
            'owner_id': 123,
        }])
        mapped = normalize_chant_dataframe(df)
        row = mapped.iloc[0]
        self.assertNotIn('dataset_idx', mapped.columns)
        self.assertNotIn('owner_id', mapped.columns)
        self.assertEqual(row['chantlink'], 'https://example.org/chant/493007')
        self.assertEqual(row['srclink'], 'https://example.org/source/573')
        self.assertEqual(row['image'], 'https://example.org/image/old')
        self.assertEqual(row['volpiano'], '1---f---4')
        self.assertEqual(row['genre_id'], 'genre_a')
        self.assertEqual(row['office_id'], 'office_m')

    def test_v1_names_win_over_v02_aliases(self):
        df = pd.DataFrame([{
            'drupal_path': 'https://old.example/chant',
            'chantlink': 'https://new.example/chant',
            'source_id': 'https://old.example/source',
            'srclink': 'https://new.example/source',
            'notes': 'https://old.example/image',
            'image': 'https://new.example/image',
            'volpiano': 'old-volpiano',
            'melody': 'new-melody',
        }])
        row = normalize_chant_dataframe(df).iloc[0]
        self.assertEqual(row['chantlink'], 'https://new.example/chant')
        self.assertEqual(row['srclink'], 'https://new.example/source')
        self.assertEqual(row['image'], 'https://new.example/image')
        self.assertEqual(row['volpiano'], 'new-melody')

    def test_unsafe_links_and_injected_columns_are_dropped(self):
        df = pd.DataFrame([{
            'chantlink': 'javascript:alert(1)',
            'srclink': 'https://example.org/source/1',
            'image': '<script>x</script>',
            '); DROP TABLE chant; --': '1',
        }])
        mapped = normalize_chant_dataframe(df)
        self.assertIsNone(mapped.iloc[0]['chantlink'])
        self.assertIsNone(mapped.iloc[0]['image'])
        self.assertEqual(mapped.iloc[0]['srclink'], 'https://example.org/source/1')
        self.assertNotIn('); DROP TABLE chant; --', mapped.columns)

    def test_safe_link_rejects_dangerous_schemes(self):
        self.assertIsNone(safe_link('javascript:alert(1)'))
        self.assertIsNone(safe_link('data:text/html,hi'))
        self.assertEqual(safe_link('https://cantusindex.org/chant/1'), 'https://cantusindex.org/chant/1')


class UploaderExporterTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('vojtech', 'vojtech@example.com', 'password')

    def test_upload_ignores_extra_fields_and_fills_defaults(self):
        df = pd.DataFrame([{
            'incipit': 'Ave Maria',
            'volpiano': '1---g---4',
            'genre': 'A',
            'hack_column': 'nope',
            'dataset_idx': 777,
            'owner_id': 999,
        }])
        dataset_idx = Uploader.upload_dataframe(df, 'mine', owner=self.user)
        chant = Chant.objects.get(dataset_name='mine')
        self.assertEqual(chant.incipit, 'Ave Maria')
        self.assertEqual(chant.volpiano, '1---g---4')
        self.assertEqual(chant.genre_id, 'genre_a')
        self.assertIsNone(chant.full_text)
        self.assertIsNone(chant.chantlink)
        self.assertEqual(chant.dataset_idx, dataset_idx)
        self.assertNotEqual(chant.dataset_idx, 777)
        self.assertEqual(chant.owner_id, self.user.id)

    def test_export_uses_cantuscorpus_v1_header(self):
        chant = Chant.objects.create(
            incipit='Ave Maria',
            cantus_id='001234',
            siglum='F-Pn lat. 1',
            srclink='https://example.org/source/1',
            chantlink='https://example.org/chant/1',
            folio='001r',
            db='CD',
            sequence=2,
            feast_id='feast_0001',
            genre_id='genre_a',
            office_id='office_m',
            volpiano='1---g---4',
            image='https://example.org/image/1',
            full_text='Ave Maria gratia plena',
            century_code='century_1100_1199',
            dataset_name='mine',
            dataset_idx=1,
            owner=self.user,
        )
        response = Exporter.export_to_csv([chant.id])
        body = response.content.decode('utf-8')
        reader_file = StringIO(body)
        header = next(reader_file).strip().split(',')
        self.assertEqual(header, list(V1_EXPORT_FIELDS))
        self.assertNotIn('id', header)
        self.assertNotIn('volpiano', header)
        self.assertNotIn('century', header)
        self.assertNotIn('drupal_path', header)
        self.assertNotIn('source_id', header)
        self.assertIn('melody', header)
        self.assertIn('feast_code', header)
        row = chant_to_v1_row(chant)
        self.assertEqual(row['melody'], '1---g---4')
        self.assertEqual(row['genre'], 'A')
        self.assertEqual(row['office'], 'M')
        self.assertEqual(row['feast'], 'Abdonis, Sennis')
        self.assertEqual(row['feast_code'], '14073000')
        self.assertEqual(row['chantlink'], 'https://example.org/chant/1')
