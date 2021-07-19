import os

from django.http.response import JsonResponse
from rest_framework import status

from melodies.models import Chant

from core.chant_processor import ChantProcessor
from core.interval_processor import IntervalProcessor
from core.mafft import Mafft

from django.conf import settings

class Aligner():

    @classmethod
    def _get_volpiano_syllable_alignment(cls, volpianos):

        # extend each word to the same number of syllables
        # and each syllables to the same number of characters
        word_counts = [len(volpiano) for volpiano in volpianos]
        max_word_count = max(word_counts)
        extended_volpianos = [[[] for _ in range(max_word_count)] for _ in volpianos]
        for word in range(max_word_count):
            # get the maximum length of word in the current position over all volpiano-text pairs
            syllable_counts = []
            # for each pair, add the number of syllables in the volpiano
            for i in range(len(volpianos)):
                if len(volpianos[i]) < word + 1:
                    syllable_counts.append(0)
                    continue
                syllable_counts.append(len(volpianos[i][word]))
            max_syllable_count = max(syllable_counts)

            # add an empty string for each syllable to each word
            for i in range(len(volpianos)):
                extended_volpianos[i][word] = ["" for _ in range(max_syllable_count)]

            # iterate over syllables
            for syllable in range(max_syllable_count):
                # find the longest syllable in the current position
                char_counts = []
                for i in range(len(volpianos)):
                    if len(volpianos[i]) < word + 1 or len(volpianos[i][word]) < syllable + 1:
                        char_counts.append(0)
                        continue
                    char_counts.append(len(volpianos[i][word][syllable]))
                max_char_count = max(char_counts)

                # add the corresponding number of -s for each syllable
                for i in range(len(volpianos)):
                    extended_volpianos[i][word][syllable] = "-" * max_char_count

        # replace a portion of -s in each syllable by volpiano
        for i, volpiano in enumerate(volpianos):
            for word_idx, word in enumerate(volpiano):
                for syl_idx, syllable in enumerate(word):
                    extended_volpianos[i][word_idx][syl_idx] = \
                        syllable + extended_volpianos[i][word_idx][syl_idx][len(syllable):]

        return extended_volpianos


    @classmethod
    def _extend_text_to_volpiano(cls, text, volpiano):
        if len(text) < len(volpiano):
            text.extend([[] for _ in range(len(volpiano) - len(text))])

        for word in range(len(volpiano)):
            if len(text[word]) < len(volpiano[word]):
                text[word].extend([[] for _ in range(len(volpiano[word]) - len(text[word]))])

        return text


    @classmethod
    def _combine_volpiano_and_text(cls, volpiano, text):
        # start sequence with a clef
        combined = [[{
            'type': 'clef',
            'volpiano': ['1'],
            'text': ''
        }, {
            'type': 'word-space',
            'volpiano': ['-'],
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
                
                syllable_volpiano = [char for char in syllable]
                current_word.append({
                    'type': 'syllable',
                    'volpiano': syllable_volpiano,
                    'text': text[i][j]
                })

                if j != len(word) - 1:
                    current_word.append({
                        'type': 'syllable-space',
                        'volpiano': ['-'],
                        'text': '-'
                    })

            # end word with a word space
            if i != len(volpiano) - 1:
                current_word.append({
                    'type': 'word-space',
                    'volpiano': ['3'],
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


    @classmethod
    def alignment_pitches(cls, ids):
        temp_dir = settings.TEMP_DIR

        # to make sure the file is empty
        cls._cleanup(temp_dir + 'tmp.txt')

        # setup mafft
        mafft = Mafft()
        mafft.set_input(temp_dir + 'tmp.txt')
        mafft.add_option('--text')

        # save errors
        error_sources = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos = cls._get_alignment_data_from_db(ids)

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for volpiano in volpianos:
                mafft.add_volpiano(volpiano)

            # align the melodies
            try:
                mafft.run()
            except RuntimeError as e:
                cls._cleanup(temp_dir + 'tmp.txt')
                return JsonResponse({'message': 'There was a problem with MAFFT'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            sequences = mafft.get_aligned_sequences()
            sequence_order = mafft.get_sequence_order()

            # try aligning melody and text
            syllables = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            next_iteration_ids = []
            for i, id in enumerate(sequence_order):
                try:
                    chants.append(cls._align_volpiano_and_text(sequences[i], syllables[id]))
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(sequences[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    finished = False
                    error_sources.append(sources[id])

            ids = next_iteration_ids
            cls._cleanup(temp_dir + 'tmp.txt')

        result = {
            'chants': chants,
            'errors': error_sources, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': success_volpianos,
                'urls': success_urls
            }}

        return result


    @classmethod
    def alignment_syllables(cls, ids):
        sources, urls, texts, volpianos = cls._get_alignment_data_from_db(ids)

        error_sources = []
        success_sources = []
        success_ids = []
        success_urls = []

        volpianos_to_align = []
        texts_to_align = []

        for i in range(len(ids)):
            volpiano_separators = ChantProcessor.insert_separator_chars(volpianos[i])
            volpiano_syllables = ChantProcessor.get_syllables_from_volpiano(volpiano_separators)
            text_syllables = ChantProcessor.get_syllables_from_text(texts[i])

            if ChantProcessor.check_volpiano_text_compatibility(volpiano_syllables, text_syllables):
                success_sources.append(sources[i])
                success_ids.append(ids[i])
                success_urls.append(urls[i])
                volpianos_to_align.append(volpiano_syllables)
                texts_to_align.append(text_syllables)
            else:
                error_sources.append(sources[i])

        aligned_volpianos = cls._get_volpiano_syllable_alignment(volpianos_to_align)
        volpiano_strings = [cls._get_volpiano_string_from_syllables(volpiano)
                                for volpiano in aligned_volpianos]

        chants = []
        for i in range(len(success_ids)):
            text = cls._extend_text_to_volpiano(texts_to_align[i], aligned_volpianos[i])
            chants.append(cls._combine_volpiano_and_text(aligned_volpianos[i], text))

        result = {
            'chants': chants,
            'errors': error_sources, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': volpiano_strings,
                'urls': success_urls
            }
        }

        return result


    @classmethod
    def alignment_intervals(cls, ids):
        temp_dir = settings.TEMP_DIR

        # to make sure the file is empty
        cls._cleanup(temp_dir + 'tmp.txt')

        # setup mafft
        mafft = Mafft()
        mafft.set_input(temp_dir + 'tmp.txt')
        mafft.add_option('--text')

        # save errors
        error_sources = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos = cls._get_alignment_data_from_db(ids)

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for volpiano in volpianos:
                interval_repr = IntervalProcessor.transform_volpiano_to_intervals(volpiano)
                mafft.add_volpiano(interval_repr)

            # align the melodies
            try:
                mafft.run()
            except RuntimeError as e:
                cls._cleanup(temp_dir + 'tmp.txt')
                return JsonResponse({'message': 'There was a problem with MAFFT'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            sequences_intervals = mafft.get_aligned_sequences()
            sequences_volpianos = [IntervalProcessor.transform_intervals_to_volpiano(intervals)
                for intervals in sequences_intervals
            ]
            sequence_order = mafft.get_sequence_order()


            # try aligning melody and text
            syllables = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            next_iteration_ids = []
            for i, id in enumerate(sequence_order):
                try:
                    chants.append(cls._align_volpiano_and_text(sequences_volpianos[i], syllables[id]))
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(sequences_intervals[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    finished = False
                    error_sources.append(sources[id])

            ids = next_iteration_ids
            cls._cleanup(temp_dir + 'tmp.txt')

        result = {
            'chants': chants,
            'errors': error_sources, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': success_volpianos,
                'urls': success_urls
            }}

        return result


    @classmethod
    def _align_volpiano_and_text(cls, volpiano, text):

        words = ChantProcessor.get_syllables_from_volpiano(volpiano)
        
        if not ChantProcessor.check_volpiano_text_compatibility(words, text):
            raise RuntimeError("Unequal text and volpiano length")

        return cls._combine_volpiano_and_text(words, text)


    @classmethod
    def _get_volpiano_string_from_syllables(cls, volpiano_syllables, contains_clef=False):
        words = ['|'.join(word) for word in volpiano_syllables]
        complete_volpiano = '~'.join(words)
        if not contains_clef:
            complete_volpiano = '1~' + complete_volpiano
        return complete_volpiano


    @classmethod
    def _cleanup(cls, file):
        if os.path.exists(file):
            os.remove(file)


    @classmethod
    def _get_alignment_data_from_db(cls, ids):
        sources = []
        urls = []
        texts = []
        volpianos = []

        for id in ids:
            try:
                chant = Chant.objects.get(pk=id)
                siglum = chant.siglum if chant.siglum else ""
                position = chant.position if chant.position else ""
                folio = chant.folio if chant.folio else ""
                source = siglum + ", " + folio + ", " + position
                sources.append(source)
                urls.append(chant.drupal_path)
            except Chant.DoesNotExist:
                return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                    status=status.HTTP_404_NOT_FOUND)

            texts.append(chant.full_text)
            volpianos.append(chant.volpiano)

        return (sources, urls, texts, volpianos)