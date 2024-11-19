import os
import re
import uuid
import logging
from django.http.response import JsonResponse
from rest_framework import status
from core import pycantus # TODO replace by pycantus library once it will be public
 

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
    def alignment_syllables(cls, ids, concatenated = False):
        '''
        Align chants using the word-based algorithm
        '''
        
        sources, urls, texts, volpianos, newick_names, siglums, cantus_ids = cls._get_alignment_data_from_db(ids)

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
                text_syllables = cls._extend_text_to_volpiano([], volpiano_syllables)
                error_sources.append(sources[i])
                error_ids.append(i)
            success_sources.append(sources[i])
            success_ids.append(ids[i])
            success_urls.append(urls[i])
            volpianos_to_align.append(volpiano_syllables)
            texts_to_align.append(text_syllables)
        

        volpiano_map, ordered_siglums = [], []

        if concatenated:
            sequences_to_align = list(zip(volpianos_to_align, range(len(volpianos_to_align)), cantus_ids, siglums))
            sequences, volpiano_map, ordered_siglums = ChantProcessor.concatenate_volpianos(sequences_to_align, sequence_as_list=True)
            align_groups = [list(x) for x in zip(*[seq for seq in sequences])]
            newick_names_dict = {name: [ids[j] for j in volpiano_map[i] if j != -1] for i, name in enumerate(ordered_siglums)}
        else:
            align_groups = [volpianos_to_align]
            newick_names_dict = {name: id for id, name in zip(ids, newick_names)}
        volpiano_strings = []
        aligned_volpianos = []
        for align_group in align_groups:
            alignment = cls._get_volpiano_syllable_alignment(align_group)
            volpiano_strings.append([cls._get_volpiano_string_from_syllables(volpiano)
                                    for volpiano in alignment])
            aligned_volpianos += alignment

        melody_order = []
        if concatenated:
            for cantus_id_id in range(len(volpiano_map[0]) if len(volpiano_map) > 0 else 0):
                for siglum_id in range(len(ordered_siglums)):
                    melody_order.append(volpiano_map[siglum_id][cantus_id_id])
        else:
            melody_order = list(range(len(aligned_volpianos)))

        chants = []
        for i, id in enumerate(melody_order):
            text = cls._extend_text_to_volpiano(texts_to_align[id] if id != -1 else [], aligned_volpianos[i])
            chants.append(cls._combine_volpiano_and_text([['']]+aligned_volpianos[i]+[['']], text))
        
        if concatenated:
            success_volpianos = ["#".join(melodies) for melodies in [list(x) for x in zip(*volpiano_strings)]]
            success_sources = ordered_siglums
            success_ids = [[ids[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            success_urls = [[urls[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            grouped_chants = list(map(list, zip(*[chants[i:i + len(ordered_siglums)] for i in range(0, len(chants), len(ordered_siglums))])))
            chants = [[item for sublist in group for item in sublist] for group in grouped_chants]
        else:
            success_volpianos = volpiano_strings[0]
            used_ids = set(success_ids)
            newick_names_dict = {name: id for name, id in newick_names_dict.items() if id in used_ids}
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
            'guideTree': None,
            'newickNamesDict': newick_names_dict,
            'alignmentMode': 'syllables'
        }

        return result


    @classmethod
    def alignment_pitches(cls, ids, concatenated = False):
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

            ### DEBUG
            #print('Aligning IDs: {}'.format(ids))
            #print('Aligning names: {}'.format(names))

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for i, (volpiano, cantus_id, siglum) in enumerate(zip(volpianos, cantus_ids, siglums)):
                mafft.add_volpiano(ChantProcessor.process_volpiano_flats(volpiano), i, cantus_id, siglum)

            # align the melodies
            try:
                volpiano_map, ordered_siglums = mafft.run(concatenate=concatenated)
            except RuntimeError as e:
                cls._cleanup(mafft_inputs_path)
                return JsonResponse({'message': 'There was a problem with MAFFT runtime'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            aligned_melodies = mafft.get_aligned_sequences()
            melody_order = mafft.get_sequence_order()


            # retrieve guide tree
            if concatenated:
                guide_tree = mafft.get_guide_tree(ordered_siglums)
                newick_names_dict = {name: [ids[j] for j in volpiano_map[i] if j != -1] for i, name in enumerate(ordered_siglums)}
            else:
                guide_tree = mafft.get_guide_tree(newick_names)
                newick_names_dict = {name: id for id, name in zip(ids, newick_names)}


            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts] # - removed text from mafft alignment
            chants = []

            if concatenated:
                aligned_melodies = [mel for _, mel in sorted({id: aligned_melodies[i] for i, id in enumerate(melody_order)}.items())]
                alignment = [mel.split("#") for mel in aligned_melodies]
                
                alignment_with_text_boundaries = [Mafft.add_text_boundaries(cantus_id_group, cls._group_volpianos(volpianos, volpiano_map, subseq_id), list(range(len(cantus_id_group)))) 
                                                  for subseq_id, cantus_id_group in enumerate([list(x) for x in zip(*alignment)])]
                melody_order = []
                aligned_melodies_with_text_boundaries = []
                for cantus_id_id in range(len(alignment_with_text_boundaries)):
                    for siglum_id in range(len(alignment_with_text_boundaries[cantus_id_id])):
                        melody_order.append(volpiano_map[siglum_id][cantus_id_id])
                        aligned_melodies_with_text_boundaries.append(alignment_with_text_boundaries[cantus_id_id][siglum_id])
            else:
                aligned_melodies_with_text_boundaries = Mafft.add_text_boundaries(aligned_melodies, volpianos, melody_order)

            for i, id in enumerate(melody_order):
                try:
                    aligned_chant_with_text, is_text_compatible = cls._get_volpiano_text_JSON(aligned_melodies_with_text_boundaries[i], text_syllabified[id] if id != -1 else [])
                    chants.append(aligned_chant_with_text)
                    if not concatenated:
                        success_volpianos.append(aligned_melodies[i])
                    if id != -1:
                        success_sources.append(sources[id])
                        success_ids.append(ids[id])
                        success_urls.append(urls[id])
                    if not is_text_compatible:
                        raise RuntimeError("Unequal text and alpiano word/syllable counts")
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    # finished = False
                    logging.error(str(e))
                    error_sources.append(sources[id])
                    error_ids.append(id)

            cls._cleanup(mafft_inputs_path)   # Comment out this cleanup to retain MAFFT output files
        if concatenated:
            success_volpianos = aligned_melodies
            success_sources = ordered_siglums
            success_ids = [[ids[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            success_urls = [[urls[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            grouped_chants = list(map(list, zip(*[chants[i:i + len(ordered_siglums)] for i in range(0, len(chants), len(ordered_siglums))])))
            chants = [[item for sublist in group for item in sublist] for group in grouped_chants]
        else:
            # remove unused newick names
            used_ids = set(success_ids)
            newick_names_dict = {name: id for name, id in newick_names_dict.items() if id in used_ids}

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
                'urls': success_urls,
            },
            'guideTree': guide_tree,
            'newickNamesDict': newick_names_dict,
            'alignmentMode': 'full'
        }

        return result


    @classmethod
    def alignment_intervals(cls, ids, concatenated = False):
        '''
        Align chants using MSA on interval values
        '''
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

            success_sources = []
            success_ids = []
            success_volpianos = []
            success_urls = []

            for i, (volpiano, cantus_id, siglum) in enumerate(zip(volpianos, cantus_ids, siglums)):
                interval_repr = IntervalProcessor.transform_volpiano_to_intervals(
                    ChantProcessor.process_volpiano_flats(volpiano))
                mafft.add_volpiano(interval_repr, i, cantus_id, siglum)

            # align the melodies
            try:
                volpiano_map, ordered_siglums = mafft.run(concatenate=concatenated)
            except RuntimeError as e:
                cls._cleanup(mafft_inputs_path)
                return JsonResponse({'message': 'There was a problem with MAFFT'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # retrieve alignments
            aligned_melodies_intervals = mafft.get_aligned_sequences()
            if concatenated:
                aligned_melodies_volpianos = ["#".join([IntervalProcessor.transform_intervals_to_volpiano(intervals) 
                                                        for intervals in intervals_group.split("#")]) 
                                                        for intervals_group in aligned_melodies_intervals]
            else:
                aligned_melodies_volpianos = [IntervalProcessor.transform_intervals_to_volpiano(intervals)
                    for intervals in aligned_melodies_intervals
                ]
            sequence_order = mafft.get_sequence_order()

            logging.info('DEBUG: Aligned melodies volpianos:')
            logging.info(aligned_melodies_volpianos)


            if concatenated:
                guide_tree = mafft.get_guide_tree(ordered_siglums)
                newick_names_dict = {name: [ids[j] for j in volpiano_map[i] if j != -1] for i, name in enumerate(ordered_siglums)}
            else:
                guide_tree = mafft.get_guide_tree(newick_names)
                newick_names_dict = {name: id for id, name in zip(ids, newick_names)}


            # try aligning melody and text
            text_syllabified = [ChantProcessor.get_syllables_from_text(text) for text in texts]
            chants = []
            if concatenated:
                aligned_melodies_volpianos = [mel for _, mel in sorted({id: aligned_melodies_volpianos[i] for i, id in enumerate(sequence_order)}.items())]
                alignment = [mel.split("#") for mel in aligned_melodies_volpianos]
                
                alignment_with_text_boundaries = [Mafft.add_text_boundaries(cantus_id_group, cls._group_volpianos(volpianos, volpiano_map, subseq_id), list(range(len(cantus_id_group))), keep_liquescents=False) 
                                                  for subseq_id, cantus_id_group in enumerate([list(x) for x in zip(*alignment)])]
                sequence_order = []
                aligned_melodies_with_text_boundaries = []
                for cantus_id_id in range(len(alignment_with_text_boundaries)):
                    for siglum_id in range(len(alignment_with_text_boundaries[cantus_id_id])):
                        sequence_order.append(volpiano_map[siglum_id][cantus_id_id])
                        aligned_melodies_with_text_boundaries.append(alignment_with_text_boundaries[cantus_id_id][siglum_id])
            else:
                aligned_melodies_with_text_boundaries = Mafft.add_text_boundaries(aligned_melodies_volpianos, volpianos, sequence_order, keep_liquescents=False)
           
            for i, id in enumerate(sequence_order):
                try:
                    aligned_chant_with_text, is_text_compatible = cls._get_volpiano_text_JSON(aligned_melodies_with_text_boundaries[i], text_syllabified[id] if id != -1 else [])
                    chants.append(aligned_chant_with_text)
                    if not concatenated:
                        success_volpianos.append(aligned_melodies_intervals[i])
                    if id != -1:
                        success_sources.append(sources[id])
                        success_ids.append(ids[id])
                        success_urls.append(urls[id])
                    if not is_text_compatible:
                        raise RuntimeError("Unequal text and alpiano word/syllable counts")
                except RuntimeError as e:
                    # found an error, the alignment will be run again
                    # finished = False
                    logging.error(str(e))
                    error_sources.append(sources[id])
                    error_ids.append(id)

            cls._cleanup(mafft_inputs_path)

        cls._cleanup(mafft_inputs_path)
        if concatenated:
            success_volpianos = aligned_melodies_intervals
            success_sources = ordered_siglums
            success_ids = [[ids[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            success_urls = [[urls[j] for j in volpiano_map[i] if j != -1] for i, _ in enumerate(ordered_siglums)]
            grouped_chants = list(map(list, zip(*[chants[i:i + len(ordered_siglums)] for i in range(0, len(chants), len(ordered_siglums))])))
            chants = [[item for sublist in group for item in sublist] for group in grouped_chants]
        else:
            # remove unused newick names
            used_ids = set(success_ids)
            newick_names_dict = {name: id for name, id in newick_names_dict.items() if id in used_ids}

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
                'urls': success_urls,
            },
            'guideTree': guide_tree,
            'newickNamesDict': newick_names_dict,
            'alignmentMode': 'intervals'
        }

        return result

    @classmethod
    def _group_volpianos(cls, volpianos, map, subseq_id):
        grouped_volpianos = []
        for i in range(len(map)):
            if map[i][subseq_id] != -1:
                grouped_volpianos.append(volpianos[map[i][subseq_id]])
            else:
                grouped_volpianos.append('')
        return grouped_volpianos

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
                    logging.error("Incorrect volpiano format - no syllable")
                    continue
                
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
            'volpiano': [*volpiano[-1][0]] + ['-'] + ['4'],
            'text': ''
        }])

        return combined


    @classmethod
    def _get_volpiano_text_JSON(cls, alpiano, text_words):
        is_combatible_text = True
        if all(char == '-' for char in alpiano): # alpiano is empty
            return [[{
                'type': 'clef',
                'volpiano': ['1'],
                'text': ''
            }, {
                'type': 'word-space',
                'volpiano': [*alpiano],
                'text': ''
            }],
            [{
                'type': 'end-sequence',
                'volpiano': ['4'],
                'text': ''
            }]], is_combatible_text
        alpiano_words = ChantProcessor.get_syllables_from_alpiano(alpiano)

        if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words[1:-1], text_words):
            # This is a problem. Often a melody has a doxology without text at the end,
            # and therefore we get a failure unnecessarily. There should be a solution
            # for this that pads the fulltext with extra empty syllables (or just a
            # character such as "#"). Therefore, we attempt to try fixing this issue with dummy
            # syllables.
            is_combatible_text = False
            _, text_words = ChantProcessor.pad_doxology_text(alpiano_words[1:-1], text_words)
            if not ChantProcessor.check_volpiano_text_compatibility(alpiano_words[1:-1], text_words):
                text_words = cls._extend_text_to_volpiano([], alpiano_words[1:-1])

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
        used_newick_names = set()
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
                if newick_name in used_newick_names:
                    counter = 0
                    while newick_name + "_" + str(counter) in used_newick_names:
                        counter += 1
                    newick_name += "_" + str(counter)
                newick_names.append(newick_name)
                used_newick_names.add(newick_name)
                siglums.append(siglum)
                cantus_ids.append(cantus_id)
            except Chant.DoesNotExist:
                return JsonResponse({'message': 'Chant with id ' + str(id) + ' does not exist'},
                    status=status.HTTP_404_NOT_FOUND)

            texts.append(chant.full_text)
            volpianos.append(chant.volpiano)
        


        # replace liquescents by their default alternatives and fix beginnings and ends
        volpianos = [ChantProcessor.fix_volpiano_beginnings_and_ends(pycantus.normalize_liquescents(vol))
                     for vol in volpianos]
        return sources, urls, texts, volpianos, newick_names, siglums, cantus_ids
