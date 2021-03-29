import music21
import chant21
from cltk.phonology.lat.syllabifier import syllabify
from cltk.phonology.lat.transcription import Transcriber
import re

def get_stressed_syllables(text):
    text = re.sub('[^0-9a-zA-Z ]', ' ', text)       # remove non-alphanumeric characters
    transcriber = Transcriber("Classical", "Allen")
    transcription = transcriber.transcribe(text)
    stressed_words = [word.split('.') for word in transcription.split()]
    stresses = [[1 if syllable[0] == '\'' else 0 for syllable in word] \
        for word in stressed_words]
    return stresses


def get_html_repr(text, melody):
    converter = chant21.cantus.ConverterCantusVolpiano(strict=True)
    converter.parseData(melody + '/' + text)
    chant = converter.stream

    return chant.toHTML()

