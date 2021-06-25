from core.chant import get_syllables_from_volpiano, check_volpiano_text_compatibility, insert_separator_chars

def get_volpiano_syllable_alignment(volpianos):

    volpiano_separators = [insert_separator_chars(volpiano) for volpiano in volpianos]
    volpiano_words = [get_syllables_from_volpiano(volpiano) for volpiano in volpiano_separators]

    # extend each word to the same number of syllables
    # and each syllables to the same number of characters
    word_counts = [len(volpiano) for volpiano in volpiano_words]
    max_word_count = max(word_counts)
    extended_volpianos = [[[] for _ in range(max_word_count)] for _ in volpiano_words]
    for word in range(max_word_count):
        # get the maximum length of word in the current position over all volpiano-text pairs
        syllable_counts = []
        # for each pair, add the number of syllables in the volpiano
        for i in range(len(volpiano_words)):
            if len(volpiano_words[i]) < word - 1:
                syllable_counts.append(0)
                continue
            syllable_counts.append(len(volpiano_words[i][word]))
        max_syllable_count = max(syllable_counts)

        # add an empty string for each syllable to each word
        for i in range(len(volpiano_words)):
            extended_volpianos[i][word] = ["" for _ in range(max_syllable_count)]

        # iterate over syllables
        for syllable in range(max_syllable_count):
            # find the longest syllable in the current position
            char_counts = []
            for i in range(len(volpiano_words)):
                if len(volpiano_words[i]) < word - 1 or len(volpiano_words[i][word]) < syllable - 1:
                    char_counts.append(0)
                    continue
                char_counts.append(len(volpiano_words[i][word][syllable]))
            max_char_count = max(char_counts)

            # add the corresponding number of -s for each syllable
            for i in range(len(volpiano_words)):
                extended_volpianos[i][word][syllable] = "-" * max_char_count

    # replace a portion of -s in each syllable by volpiano
    for i, volpiano in enumerate(volpiano_words):
        for word_idx, word in enumerate(volpiano):
            for syl_idx, syllable in enumerate(word):
                extended_volpianos[i][word_idx][syl_idx] = \
                    syllable + extended_volpianos[i][word_idx][syl_idx][len(syllable):]

    return extended_volpianos


def combine_volpiano_and_text(volpiano, text):
    # start sequence with a clef
    combined = [[{
        'type': 'clef',
        'volpiano': ['1'],
        'text': ''
    }, {
        'type': 'word-space',
        'volpiano': ['-', '-', '-'],
        'text': ''
    }]]

    for i, word in enumerate(volpiano):
        # if the number of text syllables is higher than the number
        # of volpiano syllables, truncate the last ones into one
        if len(word) < len(text[i]):
            new_syllables = text[i][:len(word) - 1]                    # n-1 syllables
            new_syllables.append(''.join(text[i][len(word) - 1:]))     # the rest combined into one
            text[i] = new_syllables

        # if the number of volpiano syllables is higher than the number
        # of text syllables, add empty syllables to text
        if len(text[i]) < len(word):
            text[i].extend([''] * (len(word) - len(text[i])))

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
                'text': text[i][j]
            })

            if j != len(word) - 1:
                current_word.append({
                    'type': 'syllable-space',
                    'volpiano': ['-', '-'],
                    'text': '-'
                })

        # end word with a word space
        if i != len(volpiano) - 1:
            current_word.append({
                'type': 'word-space',
                'volpiano': ['-', '-', '-'],
                'text': ''
            })

        combined.append(current_word)

    # finally, append end-of-sequence character
    combined.append([{
        'type': 'end-sequence',
        'volpiano': ['4'],
        'text': ''
    }])

    return combined


def align_syllables_and_volpiano(syllables, volpiano):

    words = get_syllables_from_volpiano(volpiano)
    
    if not check_volpiano_text_compatibility(words, syllables):
        raise RuntimeError("Unequal text and volpiano length")

    return combine_volpiano_and_text(words, syllables)