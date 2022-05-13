#!/usr/bin/env python
"""This is a script that converts a JSON file downloaded
from Cantus Index through the json-cid interface into a CSV
file that can be uploaded into the database."""
from __future__ import print_function, unicode_literals
import argparse
import json
import csv
import logging
import os
import pprint
import time

__version__ = "0.0.1"
__author__ = "Jan Hajic jr."


CSV_KEYS = [
    'id',
    'corpus_id',
    'incipit',
    'cantus_id',
    'mode',
    'finalis',
    'differentia',
    'siglum',
    'position',
    'folio',
    'sequence',
    'marginalia',
    'cao_concordances',
    'feast_id',
    'genre_id',
    'office_id',
    'source_id',
    'melody_id',
    'drupal_path',
    'full_text',
    'full_text_manuscript',
    'volpiano',
    'notes',
    'dataset_name',
    'dataset_idx'
]
REQUIRED_NONNULL_CSV_KEYS = [
    'incipit',
    'siglum',
    'full_text',
    'volpiano',
]

JSON_KEYS = [
            "siglum",
            "incipit",
            "fulltext",
            "melody",
            "srclink",
            "chantlink",
            "folio",
            "feast",
            "genre",
            "office",
            "position",
            "image",
            "mode",
            "db",
]

JSON_KEYS2CSV_KEYS = {
    'siglum': 'siglum',
    'incipit': 'incipit',
    'fulltext': 'full_text',
    'melody': 'volpiano',
    'folio': 'folio',
    'feast': 'feast_id',
    'genre': 'genre_id',
    'office': 'office_id',
    'position': 'position',
    'mode': 'mode',
}
CSV_KEYS2JSON_KEYS = {v: k for k, v in JSON_KEYS2CSV_KEYS.items() }
# List of CSV columns to which nothing from JSON can be used to fill information
CSV_KEYS_NOT_IN_JSON = [k for k in CSV_KEYS if k not in JSON_KEYS2CSV_KEYS.values()]


# Some fields unfortunately require processing of their contents based
# on mappings between names in JSON and computed IDs in csv.
def load_mapping(path_to_file, from_column, to_column, delimiter=","):
    column_names = []
    mapping = {}
    with open(path_to_file) as inputfile:
        csv_reader = csv.reader(inputfile, delimiter=delimiter)
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                column_names = row
                line_count += 1
                continue
            mapping[row[from_column]] = row[to_column]
    return mapping


OFFICE_MAP_CSV2JSON = load_mapping(
    path_to_file=os.path.join(os.path.dirname(__file__), 'static', 'office.csv'),
    from_column=0, to_column=1
)
OFFICE_MAP_JSON2CSV = {v: k for k, v in OFFICE_MAP_CSV2JSON.items()}
def office2office_id(office: str):
    office_id = OFFICE_MAP_JSON2CSV[office]
    return office_id


FEAST_MAP_CSV2JSON = load_mapping(
    path_to_file=os.path.join(os.path.dirname(__file__), 'static', 'feast.csv'),
    from_column=0, to_column=1
)
FEAST_MAP_JSON2CSV = {v: k for k, v in FEAST_MAP_CSV2JSON.items()}
def feast2feast_id(feast: str):
    try:
        feast_id = FEAST_MAP_JSON2CSV[feast]
    except KeyError:
        logging.warning('Feast {} not found!'.format(feast))
        raise
    return feast_id


GENRE_MAP_CSV2JSON = load_mapping(
    path_to_file=os.path.join(os.path.dirname(__file__), 'static', 'genre.csv'),
    from_column=0, to_column=1
)
GENRE_MAP_JSON2CSV = {v: k for k, v in GENRE_MAP_CSV2JSON.items()}
def genre2genre_id(genre: str):
    genre_id = GENRE_MAP_JSON2CSV[genre]
    return genre_id

JSON_KEYS_REQUIRING_PROCESSING = {
    'office': office2office_id,
    'feast': feast2feast_id,
    'genre': genre2genre_id,
}




def convert_json_data_to_csv_data(json_data, external_csv_fields={}):
    """Takes a list of JSON chant objects and converts them to
    ChantLab-compatible CSV for dataset upload.

    :param json_data: A parsed Cantus Index json.


    :param external_csv_fields: A dictionary of constant values for CSV fields
        that are not among the JSON fields but should be added to the output csv.

    :return:
    """
    csv_data = []
    CSV_EMPTY_VALUE = ''

    for json_item in json_data:

        csv_row = []

        _skip_item = 0

        for csv_key in CSV_KEYS:

            # If the key is something not mapped:
            if csv_key not in CSV_KEYS2JSON_KEYS:
                # Check if it is externally supplied (e.g. a cantus ID)
                if csv_key in external_csv_fields:
                    csv_row.append(external_csv_fields[csv_key])
                else:
                    csv_row.append(CSV_EMPTY_VALUE)

            else:
                json_key = CSV_KEYS2JSON_KEYS[csv_key]
                try:
                    json_value = json_item['chant'][json_key]
                except KeyError:
                    if csv_key in REQUIRED_NONNULL_CSV_KEYS:
                        logging.info('JSON item does not contain required field {}.'
                                     ' SKIPPING ITEM.\nJSON:\n{}'.format(csv_key, json_item))
                        _skip_item = 1
                        break
                    else:
                        logging.info('JSON item does not contain field {}. Using empty value.\n'
                                     'JSON:\n{}'.format(csv_key, json_item))
                        csv_row.append(CSV_EMPTY_VALUE)

                # Check for presence of a required value
                if ((not json_value) or (json_value == '')) and (csv_key in REQUIRED_NONNULL_CSV_KEYS):
                    logging.info('JSON item does not contain value for required field'
                                 ' {}, or mapping is missing. SKIPPING. \nJSON:\n{}'
                                 ''.format(csv_key, json_item))
                    _skip_item = 1
                    break

                csv_value = json_value
                # Transform JSON value into CSV value if necessary
                if json_key in JSON_KEYS_REQUIRING_PROCESSING:
                    json_processing_fn = JSON_KEYS_REQUIRING_PROCESSING[json_key]
                    try:
                        csv_value = json_processing_fn(json_value)
                    except KeyError:
                        if csv_key in REQUIRED_NONNULL_CSV_KEYS:
                            logging.info('Could not process required field {} from JSON item.'
                                         ' SKIPPING ITEM.\nJSON:\n{}'.format(csv_key, json_item))
                            _skip_item = 1
                            break
                        else:
                            logging.info('Could not process JSON key {} with value {}. Using empty value.\n'
                                         'JSON:\n{}'
                                         ''.format(json_key, json_value, json_item))
                            csv_value = CSV_EMPTY_VALUE

                csv_row.append(csv_value)

        if _skip_item:
            _skip_item = 0
        else:
            csv_data.append(csv_row)

    return csv_data



def write_csv_data(csv_data, csv_writer):
    """Given a CSV writer over an open file handle, writes the CSV data.
    Adds header row at the beginning.

    :param csv_data: A list of lists of CSV values.
    :param csv_writer:
    :return:
    """
    header_row = CSV_KEYS
    csv_writer.writerow(header_row)
    for row in csv_data:
        csv_writer.writerow(row)


def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-i', '--input_json', action='store', required=True)
    parser.add_argument('-o', '--output_csv', action='store', required=True)

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on INFO messages.')
    parser.add_argument('--debug', action='store_true',
                        help='Turn on DEBUG messages.')

    return parser


def main(args):
    logging.info('Starting main...')
    _start_time = time.process_time()

    with open(args.input_json) as input_json:
        json_data = json.load(input_json)

    csv_data = convert_json_data_to_csv_data(json_data)

    # pprint.pprint(csv_data)

    with open(args.output_csv, 'w') as output_csv:
        csv_writer = csv.writer(output_csv)
        write_csv_data(csv_data, csv_writer)

    _end_time = time.process_time()
    logging.info('cantus_json_to_csv.py done in {0:.3f} s'.format(_end_time - _start_time))


if __name__ == '__main__':
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    if args.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    main(args)
