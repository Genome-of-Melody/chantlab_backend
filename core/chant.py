import music21
import chant21
from cltk.phonology.lat.syllabifier import syllabify
from cltk.phonology.lat.transcription import Transcriber
import re


def get_syllables(text):
    text = re.sub('[^0-9a-zA-Z ]', ' ', text)
    words = text.split(' ')
    syllables = [syllabify(word) for word in words]
    return syllables


def align_syllables_and_volpiano(syllables, volpiano):

    whole_words = volpiano.split('~')
    # check if clef is present and remove first and last words
    if not whole_words or whole_words[0] != '1':
        raise RuntimeError("Incorrect volpiano format - no clef")
    whole_words = whole_words[1:-1]

    # start sequence with a clef
    aligned = [[{
        'type': 'clef',
        'volpiano': ['1'],
        'text': ''
    }, {
        'type': 'word-space',
        'volpiano': ['-', '-', '-'],
        'text': ''
    }]]

    words = [word.split('|') for word in whole_words]
    
    # TODO fix this check later
    if len(words) != len(syllables):
        raise RuntimeError("Unequal text and volpiano length")

    for i, word in enumerate(words):
        # if the number of text syllables is higher than the number
        # of volpiano syllables, truncate the last ones into one
        if len(word) < len(syllables[i]):
            new_syllables = syllables[i][:len(word) - 1]                    # n-1 syllables
            new_syllables.append(''.join(syllables[i][len(word) - 1:]))     # the rest combined into one
            syllables[i] = new_syllables

        # if the number of volpiano syllables is higher than the number
        # of text syllables, add empty syllables to text
        if len(syllables[i]) < len(word):
            syllables[i].extend([''] * (len(word) - len(syllables[i])))

        current_word = []
        # now process each syllable
        for j, syllable in enumerate(word):
            # this should not happen
            if not syllable:
                raise RuntimeError("Incorrect volpiano format - no syllable")
            
            volpiano = [char for char in syllable]
            current_word.append({
                'type': 'syllable',
                'volpiano': volpiano,
                'text': syllables[i][j]
            })

            if j != len(word) - 1:
                current_word.append({
                    'type': 'syllable-space',
                    'volpiano': ['-', '-'],
                    'text': '-'
                })

        # end word with a word space
        if i != len(words) - 1:
            current_word.append({
                'type': 'word-space',
                'volpiano': ['-', '-', '-'],
                'text': ''
            })

        aligned.append(current_word)

    # finally, append end-of-sequence character
    aligned.append([{
        'type': 'end-sequence',
        'volpiano': ['4'],
        'text': ''
    }])

    return aligned


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

