import os
import re
import uuid

from django.http.response import JsonResponse
from rest_framework import status

from melodies.models import Chant

from core.chant_processor import ChantProcessor
from core.interval_processor import IntervalProcessor
from core.mafft import Mafft

from django.conf import settings

class Aligner():
    '''
    The Aligner class provides methods to compute chants' alignment
    '''


    @classmethod
    def alignment_syllables(cls, ids):
        '''
        Align chants using the word-based algorithm
        '''
        sources, urls, texts, volpianos, names = cls._get_alignment_data_from_db(ids)

        error_sources = []
        error_ids = []
        success_sources = []
        success_ids = []
        success_urls = []

        volpianos_to_align = []
        texts_to_align = []

        for i in range(len(ids)):
            volpiano_separators = ChantProcessor.insert_separator_chars(volpianos[i])
            volpiano_syllables = ChantProcessor.get_syllables_from_alpiano(volpiano_separators)
            text_syllables = ChantProcessor.get_syllables_from_text(texts[i])

            if ChantProcessor.check_volpiano_text_compatibility(volpiano_syllables, text_syllables):
                success_sources.append(sources[i])
                success_ids.append(ids[i])
                success_urls.append(urls[i])
                volpianos_to_align.append(volpiano_syllables)
                texts_to_align.append(text_syllables)
            else:
                error_sources.append(sources[i])
                error_ids.append(i)

        aligned_volpianos = cls._get_volpiano_syllable_alignment(volpianos_to_align)
        volpiano_strings = [cls._get_volpiano_string_from_syllables(volpiano)
                                for volpiano in aligned_volpianos]

        chants = []
        for i in range(len(success_ids)):
            text = cls._extend_text_to_volpiano(texts_to_align[i], aligned_volpianos[i])
            chants.append(cls._combine_volpiano_and_text(aligned_volpianos[i], text))

        result = {
            'chants': chants,
            'errors': {
                "sources": error_sources,
                "ids": error_ids
            }, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': volpiano_strings,
                'urls': success_urls
            }
        }

        return result


    @classmethod
    def alignment_pitches(cls, ids):
        '''
        Align chants using MSA on pitch values
        '''
        # Dealing with alignment temporary files to avoid elementary race conditions.
        temp_dir = settings.TEMP_DIR
        if not os.path.isdir(temp_dir):
            os.mkdir(temp_dir)

        mafft_job_name = str(uuid.uuid4().hex)
        mafft_inputs_temp_file_name = mafft_job_name + '_mafft-inputs.txt'
        mafft_inputs_path = os.path.join(temp_dir, mafft_inputs_temp_file_name)

        # Make sure the file is empty:
        cls._cleanup(mafft_inputs_path)

        # setup mafft
        mafft = Mafft()
        mafft.set_input(mafft_inputs_path)
        mafft.add_option('--text')

        # save errors
        error_sources = []
        error_ids = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos, names = cls._get_alignment_data_from_db(ids)
            names_dict = {id: name for name, id in zip(ids, names)}

            ### DEBUG
            print('Aligning IDs: {}'.format(ids))
            print('Aligning names: {}'.format(names))

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
                cls._cleanup(mafft_inputs_path)
                return JsonResponse({'message': 'There was a problem with MAFFT runtime'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            aligned_melodies = mafft.get_aligned_sequences()
            melody_order = mafft.get_sequence_order()

            # retrieve guide tree
            guide_tree = mafft.get_guide_tree()
            guide_tree = cls._rename_tree_nodes(guide_tree, names)

            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            next_iteration_ids = []
            for i, id in enumerate(melody_order):
                try:
                    chants.append(cls._get_volpiano_text_JSON(aligned_melodies[i], text_syllabified[id]))
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(aligned_melodies[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    # finished = False
                    error_sources.append(sources[id])
                    error_ids.append(id)

            ids = next_iteration_ids
            cls._cleanup(mafft_inputs_path)   # Comment out this cleanup to retain MAFFT output files

        result = {
            'chants': chants,
            'errors': {
                "sources": error_sources,
                "ids": error_ids
            }, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': success_volpianos,
                'urls': success_urls
            },
            'guide_tree': guide_tree,
        }

        return result


    @classmethod
    def alignment_intervals(cls, ids):
        '''
        Align chants using MSA on interval values
        '''
        temp_dir = settings.TEMP_DIR
        if not os.path.isdir(temp_dir):
            os.mkdir(temp_dir)

        mafft_job_name = str(uuid.uuid4().hex)
        mafft_inputs_temp_file_name = mafft_job_name + '_mafft-inputs.txt'
        mafft_inputs_path = os.path.join(temp_dir, mafft_inputs_temp_file_name)

        # Make sure the file is empty:
        cls._cleanup(mafft_inputs_path)

        # setup mafft
        mafft = Mafft()
        mafft.set_input(temp_dir + 'tmp.txt')
        mafft.add_option('--text')

        # save errors
        error_sources = []
        error_ids = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos, names = cls._get_alignment_data_from_db(ids)

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
                cls._cleanup(mafft_inputs_path)
                return JsonResponse({'message': 'There was a problem with MAFFT'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            aligned_melodies_intervals = mafft.get_aligned_sequences()
            aligned_melodies_volpianos = [IntervalProcessor.transform_intervals_to_volpiano(intervals)
                for intervals in aligned_melodies_intervals
            ]
            sequence_order = mafft.get_sequence_order()


            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            next_iteration_ids = []
            for i, id in enumerate(sequence_order):
                try:
                    chants.append(cls._get_volpiano_text_JSON(aligned_melodies_volpianos[i], text_syllabified[id]))
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(aligned_melodies_intervals[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    finished = False
                    error_sources.append(sources[id])
                    error_ids.append(id)

            ids = next_iteration_ids
            cls._cleanup(mafft_inputs_path)

        cls._cleanup(mafft_inputs_path)

        result = {
            'chants': chants,
            'errors': {
                "sources": error_sources,
                "ids": error_ids
            }, 
            'success': {
                'sources': success_sources,
                'ids': success_ids,
                'volpianos': success_volpianos,
                'urls': success_urls
            }}

        return result


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
    def _combine_volpiano_and_text(cls, volpiano, text_syllabified):
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
            if len(word) < len(text_syllabified[i]):
                new_syllables = text_syllabified[i][:len(word) - 1]                    # n-1 syllables
                new_syllables.append(''.join(text_syllabified[i][len(word) - 1:]))     # the rest combined into one
                text_syllabified[i] = new_syllables

            # if the number of volpiano syllables is higher than the number
            # of text syllables, add empty syllables to text
            if len(text_syllabified[i]) < len(word):
                text_syllabified[i].extend([''] * (len(word) - len(text_syllabified[i])))

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
                    'text': text_syllabified[i][j]
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
    def _get_volpiano_text_JSON(cls, alpiano, text_words):

        alpiano_words = ChantProcessor.get_syllables_from_alpiano(alpiano)
        
        if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words, text_words):
            # This is a problem. Often a melody has a doxology without text at the end,
            # and therefore we get a failure unnecessarily. There should be a solution
            # for this that pads the fulltext with extra empty syllables (or just a
            # character such as "#"). Therefore, we attempt to try fixing this issue with dummy
            # syllables.
            alpiano_words, text_words = ChantProcessor.try_fixing_volpiano_and_text_compatibility(alpiano_words, text_words)
            if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words, text_words):
                raise RuntimeError("Unequal text and alpiano word/syllable counts")

        return cls._combine_volpiano_and_text(alpiano_words, text_words)


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

        treefile = file + '.tree'
        if os.path.exists(treefile):
            os.remove(treefile)


    @classmethod
    def _get_alignment_data_from_db(cls, ids):
        sources = []
        urls = []
        texts = []
        volpianos = []
        names = []

        for id in ids:
            try:
                chant = Chant.objects.get(pk=id)

                siglum = chant.siglum if chant.siglum else ""
                position = chant.position if chant.position else ""
                folio = chant.folio if chant.folio else ""
                source = siglum + ", " + folio + ", " + position
                sources.append(source)

                urls.append(chant.drupal_path)

                name = ChantProcessor.build_chant_name(chant)
                names.append(name)
            except Chant.DoesNotExist:
                return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                    status=status.HTTP_404_NOT_FOUND)

            texts.append(chant.full_text)
            volpianos.append(chant.volpiano)

        return sources, urls, texts, volpianos, names

    @classmethod
    def _rename_tree_nodes(cls, tree_string, names):
        """The guide tree from MAFFT uses numerical indices instead of meaningful names
        for its leafs. We re-insert the meaningful names here.
        """
        ## DEBUG
        print('_rename_tree_nodes(): names total: {}'.format(len(names)))

        def _sub_group(match, names):
            print('Matched ID: {}'.format(match.group()))
            return names[int(match.group())]

        # get rid of newlines
        tree_string = ''.join(tree_string.split('\n'))
        named_tree_string = re.sub('(?<=[0-9]__)([0-9]+)',
                                   lambda m: _sub_group(m, names),
                                   tree_string)

        return named_tree_string