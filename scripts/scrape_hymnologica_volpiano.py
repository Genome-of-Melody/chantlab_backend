#!/usr/bin/env python
"""This is a script that attempts to fill in volpiano strings from hymnologica.cz
into a Cantus Index JSON file."""
from __future__ import print_function, unicode_literals
import argparse
import json
import logging
import time
import requests
import bs4

__version__ = "0.0.1"
__author__ = "Jan Hajic jr."


def get_hymnologica_page(chant_url):
    try:
        response = requests.get(chant_url)
        if response.status_code != 200:
            return None
        html_text = response.text
        return html_text
    except Exception:
        return None


def parse_melody_from_html(hymnologica_html):
    soup = bs4.BeautifulSoup(hymnologica_html, 'html.parser')
    melody_divs = soup.find_all('div', {'class': 'melody'})
    melody_fragments = [melody_div.text.strip() for melody_div in melody_divs]
    melody = ''.join(melody_fragments)
    return melody


def parse_office_from_html(hymnologica_html):
    soup = bs4.BeautifulSoup(hymnologica_html, 'html.parser')
    if soup is None:
        return None
    office_container_div = soup.find('div', {'class': 'field-name-field-office'})
    if office_container_div is None:
        return None
    office_content_div = office_container_div.find('div', {'class': 'field-item'})
    if office_content_div is None:
        return None
    office = office_content_div.text.strip()
    return office


def try_to_find_melody_and_office(chant):
    chant_url = chant['chantlink']
    hymnologica_marker_url = 'hymnologica.cz'
    if hymnologica_marker_url not in chant_url:
        return None, None

    hymnologica_html = get_hymnologica_page(chant_url)
    if not hymnologica_html:
        return None, None

    melody = parse_melody_from_html(hymnologica_html)
    office = parse_office_from_html(hymnologica_html)

    return melody, office


def find_hymnologica_melodies(json_data):
    enriched_json_data = []
    for item in json_data:
        chant = item['chant']

        melody, office = try_to_find_melody_and_office(chant)

        if melody:
            chant['melody'] = melody
        if (not chant['office']) and (office is not None):
            chant['office'] = office

        enriched_json_data.append({'chant': chant})
    return enriched_json_data


def build_argument_parser():
    parser = argparse.ArgumentParser(description=__doc__, add_help=True,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument('-i', '--input_json', action='store', required=True,
                        help='A JSON file conforming to the Cantus Index export standard.')
    parser.add_argument('-o', '--output_json', action='store', required=True,
                        help='The file to which the JSON with melodies will be exported.')

    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Turn on INFO messages.')
    parser.add_argument('--debug', action='store_true',
                        help='Turn on DEBUG messages.')

    return parser


def main(args):
    logging.info('Starting main...')
    _start_time = time.process_time()

    with open(args.input_json) as input_fh:
        json_data = json.load(input_fh)

    enriched_json_data = find_hymnologica_melodies(json_data)

    with open(args.output_json, 'w') as output_fh:
        json.dump(enriched_json_data, output_fh)

    _end_time = time.process_time()
    logging.info('scrape_hymnologica_data.py done in {0:.3f} s'.format(_end_time - _start_time))


if __name__ == '__main__':
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.INFO)
    if args.debug:
        logging.basicConfig(format='%(levelname)s: %(message)s', level=logging.DEBUG)

    main(args)
