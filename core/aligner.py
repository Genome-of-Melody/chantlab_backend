import os
import re
import uuid
import logging
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
    '''
    The Aligner class provides methods to compute chants' alignment
    '''


    @classmethod
    def alignment_syllables(cls, ids, concatenated = False, add_empty_chant = False):
        '''
        Align chants using the word-based algorithm
        '''
        
        sources, urls, texts, volpianos, names, siglums, cantus_ids = cls._get_alignment_data_from_db(ids)
        if concatenated:
           return cls._concatenated_alignment(ids, siglums, cantus_ids, cls.alignment_syllables)
        error_sources = []
        error_ids = []
        success_sources = []
        success_ids = []
        success_urls = []

        volpianos_to_align = []
        texts_to_align = []

        for i in range(len(ids)):
            volpiano_separators = ChantProcessor.insert_separator_chars(volpianos[i])
            volpiano_syllables = ChantProcessor.get_syllables_from_alpiano(volpiano_separators)[1:-1]
            text_syllables = ChantProcessor.get_syllables_from_text(texts[i])

            if not ChantProcessor.check_volpiano_text_compatibility(volpiano_syllables, text_syllables):
                text_syllables = ChantProcessor.generate_placehoder_text(volpiano_syllables)
                error_sources.append(sources[i])
                error_ids.append(i)
            success_sources.append(sources[i])
            success_ids.append(ids[i])
            success_urls.append(urls[i])
            volpianos_to_align.append(volpiano_syllables)
            texts_to_align.append(text_syllables)

        if add_empty_chant:
            volpianos_to_align.append([])
            texts_to_align.append([])

        aligned_volpianos = cls._get_volpiano_syllable_alignment(volpianos_to_align)
        volpiano_strings = [cls._get_volpiano_string_from_syllables(volpiano)
                                for volpiano in aligned_volpianos]

        chants = []
        for i in range(len(success_ids) + int(add_empty_chant)):
            text = cls._extend_text_to_volpiano(texts_to_align[i], aligned_volpianos[i])
            chants.append(cls._combine_volpiano_and_text([['']]+aligned_volpianos[i]+[['']], text))

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
            },
            'guideTree': None,
            'newickNamesDict': None,
            'alignmentMode': 'syllables'
        }

        return result


    @classmethod
    def alignment_pitches(cls, ids, concatenated = False, add_empty_chant = False):
        '''
        Align chants using MSA on pitch values
        '''
        _, _, _, _, _, siglums, cantus_ids = cls._get_alignment_data_from_db(ids)
        if concatenated:
           return cls._concatenated_alignment(ids, siglums, cantus_ids, cls.alignment_pitches)
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
        mafft.set_input(mafft_inputs_path)#.replace("\\", "/")) 
        mafft.add_option('--text')
        mafft.add_option('--textmatrix resources/00_textmatrix_complete')

        # save errors
        error_sources = []
        error_ids = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos, newick_names, _, _ = cls._get_alignment_data_from_db(ids)
            newick_names_dict = {name: id for id, name in zip(ids, newick_names)}

            ### DEBUG
            #print('Aligning IDs: {}'.format(ids))
            #print('Aligning names: {}'.format(names))

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for volpiano in volpianos:
                mafft.add_volpiano(ChantProcessor.process_volpiano_flats(volpiano))

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
            if not add_empty_chant:
                guide_tree = mafft.get_guide_tree()
                guide_tree = cls._rename_tree_nodes(guide_tree, newick_names)
            else:
                guide_tree = None

            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts] # - removed text from mafft alignment
            chants = []
            next_iteration_ids = []
            aligned_melodies_with_text_boundaries = Mafft.add_text_boundaries(aligned_melodies, volpianos, melody_order)
            for i, id in enumerate(melody_order):
                try:
                    aligned_chant_with_text, is_text_compatible = cls._get_volpiano_text_JSON(aligned_melodies_with_text_boundaries[i], text_syllabified[id])
                    chants.append(aligned_chant_with_text)
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(aligned_melodies[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                    if not is_text_compatible:
                        raise RuntimeError("Unequal text and alpiano word/syllable counts")
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    # finished = False
                    logging.error(str(e))
                    error_sources.append(sources[id])
                    error_ids.append(id)
            # Add the empty chant at the end
            if add_empty_chant and len(success_volpianos) > 0: 
                empty_volpiano = re.sub(r'[a-zA-Z89]', '-', success_volpianos[0])
                empty_chant = cls._get_volpiano_text_JSON(empty_volpiano, [])
                chants.append(empty_chant)
                success_volpianos.append(empty_volpiano)

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
            'guideTree': guide_tree,
            'newickNamesDict': newick_names_dict,
            'alignmentMode': 'full'
        }

        return result


    @classmethod
    def alignment_intervals(cls, ids, concatenated = False, add_empty_chant = False):
        '''
        Align chants using MSA on interval values
        '''
        _, _, _, _, _, siglums, cantus_ids = cls._get_alignment_data_from_db(ids)
        if concatenated:
           return cls._concatenated_alignment(ids, siglums, cantus_ids, cls.alignment_intervals)
        logging.info('DEBUG: running MAFFT intervals with ids {}'.format(ids))

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
        mafft.set_input(mafft_inputs_path)#.replace("\\", "/"))
        mafft.add_option('--text')
        mafft.add_option('--textmatrix resources/00_textmatrix_complete')

        # save errors
        error_sources = []
        error_ids = []
        finished = False

        # iterate until there are no alignment errors
        while not finished:
            finished = True

            sources, urls, texts, volpianos, newick_names, siglums, cantus_ids = cls._get_alignment_data_from_db(ids)
            newick_names_dict = {name: id for id, name in zip(ids, newick_names)}

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for volpiano in volpianos:
                interval_repr = IntervalProcessor.transform_volpiano_to_intervals(
                    ChantProcessor.process_volpiano_flats(volpiano))
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

            logging.info('DEBUG: Aligned melodies volpianos:')
            logging.info(aligned_melodies_volpianos)

            if not add_empty_chant:
                # retrieve guide tree
                guide_tree = mafft.get_guide_tree()
                # print('DEBUG: Intervals alignment, guide tree: {}').format(guide_tree)
                guide_tree = cls._rename_tree_nodes(guide_tree, newick_names)
                # print('DEBUG: Intervals alignment, named guide tree: {}').format(guide_tree)
            else:
                guide_tree = None

            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            next_iteration_ids = []
            aligned_melodies_with_text_boundaries = Mafft.add_text_boundaries(aligned_melodies_volpianos, volpianos, sequence_order, keep_liquescents=False)
            for i, id in enumerate(sequence_order):
                try:
                    aligned_chant_with_text, is_text_compatible = cls._get_volpiano_text_JSON(aligned_melodies_with_text_boundaries[i], text_syllabified[id])
                    chants.append(aligned_chant_with_text)
                    success_sources.append(sources[id])
                    success_ids.append(ids[id])
                    success_volpianos.append(aligned_melodies_intervals[i])
                    success_urls.append(urls[id])
                    # store chant id in case it is going to be aligned again
                    next_iteration_ids.append(ids[id])
                    if not is_text_compatible:
                        raise RuntimeError("Unequal text and alpiano word/syllable counts")
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    # finished = False
                    logging.error(str(e))
                    error_sources.append(sources[id])
                    error_ids.append(id)
            # Add the empty chant at the end
            if add_empty_chant and len(success_volpianos) > 0: 
                empty_volpiano = re.sub(r'[a-zA-Z89]', '-', success_volpianos[0])
                empty_chant = cls._get_volpiano_text_JSON(empty_volpiano, [])
                chants.append(empty_chant)
                success_volpianos.append(empty_volpiano)
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
            },
            'guideTree': guide_tree,
            'newickNamesDict': newick_names_dict,
            'alignmentMode': 'intervals'
        }

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
            'volpiano': [*volpiano[0][0]] + ["-"],
            'text': ''
        }]]

        for i, word in enumerate(volpiano[1:-1]):
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
            if i != len(volpiano[1:-1]) - 1:
                current_word.append({
                    'type': 'word-space',
                    'volpiano': ['3'],
                    'text': ''
                })

            combined.append(current_word)

        # finally, append end-of-sequence character
        combined.append([{
            'type': 'end-sequence',
            'volpiano': [*volpiano[-1][0]] + ['4'],
            'text': ''
        }])

        return combined


    @classmethod
    def _get_volpiano_text_JSON(cls, alpiano, text_words):
        is_combatible_text = True
        alpiano_words = ChantProcessor.get_syllables_from_alpiano(alpiano)
        
        if len(alpiano_words) == 0:
            return [[{
                'type': 'clef',
                'volpiano': ['1'],
                'text': ''
            }, {
                'type': 'word-space',
                'volpiano': ['-'],
                'text': ''
            }],
            [{
                'type': 'syllable',
                'volpiano': alpiano.split(),
                'text': ''
            }],
            [{
                'type': 'end-sequence',
                'volpiano': ['4'],
                'text': ''
            }]], is_combatible_text

        if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words[1:-1], text_words):
            # This is a problem. Often a melody has a doxology without text at the end,
            # and therefore we get a failure unnecessarily. There should be a solution
            # for this that pads the fulltext with extra empty syllables (or just a
            # character such as "#"). Therefore, we attempt to try fixing this issue with dummy
            # syllables.
            is_combatible_text = False
            _, text_words = ChantProcessor.pad_doxology_text(alpiano_words[1:-1], text_words)
            if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words[1:-1], text_words):
                text_words = ChantProcessor.generate_placehoder_text(alpiano_words[1:-1])

        return cls._combine_volpiano_and_text(alpiano_words, text_words), is_combatible_text


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
        newick_names = []
        siglums = []
        cantus_ids = []

        for id in ids:
            try:
                chant = Chant.objects.get(pk=id)

                siglum = chant.siglum if chant.siglum else ""
                position = chant.position if chant.position else ""
                folio = chant.folio if chant.folio else ""
                source = siglum + ", " + folio + ", " + position
                cantus_id = chant.cantus_id if chant.cantus_id else ""
                sources.append(source)

                urls.append(chant.drupal_path)

                newick_name = ChantProcessor.build_chant_newick_name(chant)
                newick_names.append(newick_name)
                siglums.append(siglum)
                cantus_ids.append(cantus_id)
            except Chant.DoesNotExist:
                return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                    status=status.HTTP_404_NOT_FOUND)

            texts.append(chant.full_text)
            volpianos.append(chant.volpiano)

        return sources, urls, texts, volpianos, newick_names, siglums, cantus_ids


    @classmethod
    def _concatenated_alignment(cls, ids, siglums, cantus_ids, alignment_funct):
            final_error_sources = []
            final_error_ids = []
            # Prepare information for concatenation
            unique_sources = list(set(siglums))
            source_alignment_count = {}
            for source in unique_sources:
                source_alignment_count[source] = 0
            id2source_map = {}
            for id, siglum in zip(ids, siglums):
                id2source_map[id] = siglum
            # Split chants by their cantus ids
            cantus_subids = {}
            used_sources = {}
            for id, cid in zip(ids, cantus_ids):
                if not cid in cantus_subids:
                    cantus_subids[cid] = []
                # check the cantus id is not duplicated for the same siglum
                if not cid in used_sources:
                    used_sources[cid] = set()
                if id2source_map[id] in used_sources[cid]:
                    final_error_sources.append(id2source_map[id])
                    final_error_ids.append(id)
                else:
                    used_sources[cid].add(id2source_map[id])
                    cantus_subids[cid].append(id)
            # Collect all alignments by corpus ids
            final_chants = []
            final_volpiano_strings = []
            for _ in unique_sources:
                final_chants.append([])
                final_volpiano_strings.append("")
            final_success_sources = []
            final_success_ids = []
            final_success_urls = []
            alignment_mode = ""
            # Align all cantus ids separatly
            for cantus_id in cantus_subids:
                subids = cantus_subids[cantus_id]
                sub_result = alignment_funct(subids, concatenated = False, add_empty_chant = True)
                # Collect successes and errors
                for id in sub_result["errors"]["ids"]:
                    final_error_ids.append(id)
                for source in sub_result["errors"]["sources"]:
                    final_error_sources.append(source)
                for id in sub_result["success"]["ids"]:
                    final_success_ids.append(id)
                for source in sub_result["success"]["sources"]:
                    final_success_sources.append(source)
                for url in sub_result["success"]["urls"]:
                    final_success_urls.append(url)
                if len(sub_result["success"]["ids"]) == 0:
                    continue
                # Get alignment length from alpiano
                volpiano_length = len(sub_result["success"]["volpianos"][0])
                # Create map to map sources with successful ids
                success_ids_map = {}
                for i, id in enumerate(sub_result["success"]["ids"]):
                    success_ids_map[id2source_map[id]] = i
                    assert len(sub_result["success"]["volpianos"][i]) == volpiano_length
                # Collect parsed chants and alpianos
                for i, source in enumerate(unique_sources):
                    if source in success_ids_map:
                        final_chants[i] += sub_result["chants"][success_ids_map[source]]
                        if len(final_volpiano_strings[i]) > 0:
                            final_volpiano_strings[i] += "#"
                        final_volpiano_strings[i] += sub_result["success"]["volpianos"][success_ids_map[source]]
                        source_alignment_count[source] += 1
                    else:
                        final_chants[i] += sub_result["chants"][-1]
                        if len(final_volpiano_strings[i]) > 0:
                            final_volpiano_strings[i] += "#"
                        final_volpiano_strings[i] += sub_result["success"]["volpianos"][-1]
                alignment_mode = sub_result["alignmentMode"]
            # Remove sources that don't contain alignments
            filtered_volpianos = []
            filtered_chants = []
            sources = []
            for i, source in enumerate(unique_sources):
                if source_alignment_count[source] > 0:
                    filtered_chants.append(final_chants[i])
                    filtered_volpianos.append(final_volpiano_strings[i])
                    sources.append(source)
            return {
                'chants': filtered_chants,
                'errors': {
                    "sources": final_error_sources,
                    "ids": final_error_ids
                }, 
                'success': {
                    'sources': sources,
                    'ids': final_success_ids[:len(filtered_volpianos)], # ToDo design more suitable format and return all successful ids
                    'volpianos': filtered_volpianos,
                    'urls': final_success_urls[:len(filtered_volpianos)] # ToDo design more suitable format and return all urls
                },
                'guideTree': None, # ToDo return all guide trees, but first figure it out how
                'newickNamesDict': None,
                'alignmentMode': alignment_mode
            }

    @classmethod
    def _rename_tree_nodes(cls, tree_string, names):
        """The guide tree from MAFFT uses numerical indices instead of meaningful names
        for its leafs. We re-insert the meaningful names here.
        """
        ## DEBUG
        # print('_rename_tree_nodes(): names total: {}'.format(len(names)))

        def _sub_group(match, names):
            # print('Matched ID: {}'.format(match.group()))
            return names[int(match.group())]

        # get rid of newlines
        tree_string = ''.join(tree_string.split('\n'))
        named_tree_string = re.sub('(?<=[0-9]__)([0-9]+)',
                                   lambda m: _sub_group(m, names),
                                   tree_string)

        return named_tree_string