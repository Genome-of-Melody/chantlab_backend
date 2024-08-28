import chant21
# from cltk.phonology.lat.syllabifier import syllabify
# from cltk.phonology.lat.transcription import Transcriber
from volpiano_display_utilities.cantus_text_syllabification import syllabify_text
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
        syllables = syllabify_text(text)[0][0].section
        # words = text.split(' ')
        # syllables = [syllabify(word) for word in words]
        return syllables


    @classmethod
    def get_syllables_from_alpiano(cls, volpiano):
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
    def check_volpiano_text_compatibility(cls, volpiano_words, text_words):
        '''
        Check whether melody and text can be combined. Implemented as a check
        just of the number of words.
        '''
        return len(volpiano_words) == len(text_words)

    @classmethod
    def try_fixing_volpiano_and_text_compatibility(cls, alpiano_words, text_words):
        '''Attempts to apply fixes to some trivial incompatibilities between text and volpiano.

        - Tries to pad the text so that it has the same number of words as the volpiano.

        :param alpiano_words:
        :param text_words:
        :return:
        '''
        _DUMMY_SYLLABLE_TEXT = '#'
        length_diff = len(alpiano_words) - len(text_words)
        if length_diff > 0:
            extra_alpiano_words = alpiano_words[-length_diff:]
            dummy_text_words = [[_DUMMY_SYLLABLE_TEXT for _ in al_word]
                                for al_word in extra_alpiano_words]
            text_words.extend(dummy_text_words)
        return alpiano_words, text_words

    @classmethod
    def get_stressed_syllables(cls, text):
        '''
        Compute the stressed syllables of Latin text
        '''
        try:
            text = re.sub('[^0-9a-zA-Z ]', ' ', text)       # remove non-alphanumeric characters
        except:
            return []
        # Stressed syllable detection removed because of CLTK dependency causing severe installation issues.
        # try:
        #     transcriber = Transcriber("Classical", "Allen")
        #     transcription = transcriber.transcribe(text)
        # except:
        #     return []
        # stressed_words = [word.split('.') for word in transcription.split()]
        # stresses = [[1 if syllable[0] == '\'' else 0 for syllable in word] \
        #    for word in stressed_words]
        stresses = []  # No stress information is computed now.
        return stresses


    @classmethod
    def get_JSON(cls, text, melody):
        '''
        Return an easily renderable representation of a chant
        '''
        converter = chant21.cantus.ConverterCantusVolpiano(strict=False)
        converter.parseData(melody + '/' + text)
        chant = converter.stream

        return chant.toCHSON()

    @classmethod
    def build_chant_newick_name(cls, chant):
        '''
        Returns a string for humans to read as the chant name: incipit
        (at most three words) and source name.

        :param chant: a models.Chant object retrieved from the database.

        :return: Incipit and source name. If either is missing, special
            token: [unnamed] if no incipit, [nosource] if no source.
        '''
        incipit = chant.incipit if chant.incipit else '[unnamed]'
        incipit_name = '_'.join(incipit.split())
        siglum = chant.siglum if chant.siglum else '[nosource]'
        siglum = '_'.join(siglum.replace('(', '').replace(')', '').split())
        return '{}__{}'.format(incipit_name, siglum)
