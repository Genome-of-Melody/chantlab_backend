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
        """
        volpiano_words = volpiano.split('~')    # divides volpiano into words
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
    def pad_doxology_text(cls, alpiano_words, text_words):
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
        siglum = chant.siglum if chant.siglum else '[nosource]'
        return '{} {} {} m{}'.format(incipit, siglum, chant.id, chant.mode)

    @staticmethod
    def concatenate_volpianos(sequences_to_align, sequence_as_list = False):
        volpiano_map, sequences = [], []
        unique_siglums = set()
        unique_cantus_ids = set()
        siglum_cantus_map = {}
        for seq, volpiano_id, cantus_id, siglum in sequences_to_align:
            if not siglum in siglum_cantus_map:
                siglum_cantus_map[siglum] = {}
            if not cantus_id in siglum_cantus_map[siglum]:
                siglum_cantus_map[siglum][cantus_id] = (seq, volpiano_id)
            unique_siglums.add(siglum)
            unique_cantus_ids.add(cantus_id)
        ordered_siglums = list(unique_siglums)
        ordered_cantus_ids = list(unique_cantus_ids)
        for siglum in ordered_siglums:
            volpiano_cantus_map = []
            new_sequence = []
            for cantus_id in ordered_cantus_ids:
                if cantus_id in siglum_cantus_map[siglum]:
                    seq, volpiano_id = siglum_cantus_map[siglum][cantus_id]
                else:
                    seq = '' if not sequence_as_list else []
                    volpiano_id = -1
                volpiano_cantus_map.append(volpiano_id)
                new_sequence.append(seq)
            volpiano_map.append(volpiano_cantus_map)
            sequences.append("#".join(new_sequence) if not sequence_as_list else new_sequence)
        return sequences, volpiano_map, ordered_siglums

    @staticmethod
    def process_volpiano_flats(volpiano):
        y = False # bb
        i = False # bb'
        x = False # eb'
        z = False # bb''
        processed_volpiano = ""
        for c in volpiano:
            if c == "y":
                y = True
            elif c == "Y": 
                y = False
            elif c == "i":
                i = True
            elif c == "I":
                i = False
            elif c == "x":
                x = True
            elif c == "X": 
                x = False
            elif c == "z":
                z = True
            elif c == "Z": 
                z = False
            elif c == "b" and y:
                processed_volpiano += "y"
            elif c == "j" and i:
                processed_volpiano += "i"
            elif c == "m" and x:
                processed_volpiano += "x"
            elif c == "q" and z:
                processed_volpiano += "z"
            else:
                processed_volpiano += c
        return processed_volpiano


    def fix_volpiano_beginnings_and_ends(volpiano):
        if volpiano[:4] != "1---" or volpiano[-4:] != "---4":
            fixed_volpiano = volpiano.strip("134-")
            fixed_volpiano = "1---" + fixed_volpiano + "---4"
            #logging.error("The correct beginning and end of volpiano '{}' is missing, fixed to '{}'".format(volpiano, fixed_volpiano))
            volpiano = fixed_volpiano
        return volpiano