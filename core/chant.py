import music21
import chant21
from cltk.phonology.lat.syllabifier import syllabify
from cltk.phonology.lat.transcription import Transcriber
import re

def get_syllables_from_text(text):
    text = re.sub('[^0-9a-zA-Z ]', ' ', text)
    words = text.split(' ')
    syllables = [syllabify(word) for word in words]
    return syllables


def get_syllables_from_volpiano(volpiano):
    # insert syllable and word boundary signs into volpiano
    volpiano = volpiano.replace('---', '~')
    volpiano = volpiano.replace('--', '|')
    volpiano = volpiano.replace('-', '')

    volpiano_words = volpiano.split('~')    # divides volpiano into words
    volpiano_words = volpiano_words[1:-1]   # discard 1st (clef) and last (bar) words
    volpiano_syllables = [volpiano_word.split('|') for volpiano_word in volpiano_words]

    return volpiano_syllables




def get_stressed_syllables(text):
    text = re.sub('[^0-9a-zA-Z ]', ' ', text)       # remove non-alphanumeric characters
    try:
        transcriber = Transcriber("Classical", "Allen")
        transcription = transcriber.transcribe(text)
    except:
        return []
    stressed_words = [word.split('.') for word in transcription.split()]
    stresses = [[1 if syllable[0] == '\'' else 0 for syllable in word] \
        for word in stressed_words]
    return stresses


def get_JSON(text, melody):
    converter = chant21.cantus.ConverterCantusVolpiano(strict=True)
    converter.parseData(melody + '/' + text)
    chant = converter.stream

    return chant.toCHSON()

