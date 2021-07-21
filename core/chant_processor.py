import chant21
from cltk.phonology.lat.syllabifier import syllabify
from cltk.phonology.lat.transcription import Transcriber
import re

class ChantProcessor():
    '''
    The ChantProcessor class provides method to process chants' texts and melodies
    '''

    @classmethod
    def get_syllables_from_text(cls, text):
        """
        Divides latin text into words and syllables.

        @returns: list of words, where each word is a list of syllables
        """
        text = re.sub('[^0-9a-zA-Z ]', ' ', text)
        words = text.split(' ')
        syllables = [syllabify(word) for word in words]
        return syllables


    @classmethod
    def get_syllables_from_volpiano(cls, volpiano):
        """
        Divides a string of volpiano notation with separator signs
        into words and syllables.

        @returns: list of words, where each word is a list of syllables
        """
        volpiano_words = volpiano.split('~')    # divides volpiano into words
        volpiano_words = volpiano_words[1:-1]   # discard 1st (clef) and last (bar) words
        volpiano_syllables = [volpiano_word.split('|') for volpiano_word in volpiano_words]

        return volpiano_syllables


    @classmethod
    def insert_separator_chars(cls, volpiano):
        """
        Replaces volpiano word boundaries ('---') by '~'
        and syllable boundaries ('--') by '|'
        """
        volpiano = volpiano.replace('---', '~')
        volpiano = volpiano.replace('--', '|')
        volpiano = volpiano.replace('-', '')

        return volpiano


    @classmethod
    def check_volpiano_text_compatibility(cls, volpiano, text):
        '''
        Check whether melody and text can be combined
        '''
        return len(volpiano) == len(text)


    @classmethod
    def get_stressed_syllables(cls, text):
        '''
        Compute the stressed syllables of Latin text
        '''
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


    @classmethod
    def get_JSON(cls, text, melody):
        '''
        Return an easily renderable representation of a chant
        '''
        converter = chant21.cantus.ConverterCantusVolpiano(strict=True)
        converter.parseData(melody + '/' + text)
        chant = converter.stream

        return chant.toCHSON()

