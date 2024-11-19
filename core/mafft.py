import os
import subprocess
import sys
from core import pycantus # TODO replace by pycantus library once it will be public
from core.chant_processor import ChantProcessor
import logging
from ete3 import Tree

MAFFT_PATH = '/Users/hajicj/CES_TF/mafft/mafft-mac/mafftdir/bin/mafft'
if not os.path.isfile(MAFFT_PATH):
    MAFFT_PATH = 'mafft'
CONCATENATE_PLACEHOLDER = "concat_placeholder"
class Mafft():
    '''
    The Mafft class is the interface for working with the MAFFT software
    '''

    def __init__(self):
        self._input = None
        self._output = None
        self._output_guide_tree_file = None

        self._options = ['--quiet', '--reorder', '--treeout']
        self._prefix = "wsl" if sys.platform.startswith("win") else ""
        self._counter = 0
        self._process = None

        self._sequences_to_align = []

        self._aligned_sequences = None
        self._sequence_idxs = None
        self._guide_tree = None


    def set_input(self, file):
        self._input = file
        # MAFFT outputs the guide tree to a file called e.g. 'testinput.txt.tree'
        self._output_guide_tree_file = self._input + '.tree'

    
    def set_output(self, file):
        self._output = file


    def add_option(self, flag, value=None):
        self._options.append(flag)
        if value:
            self._options.append(value)


    def set_prefix(self, prefix):
        self._prefix = prefix

    def _align_sequences(self, sequences):
        fasta_content = ""
        for i, seq in enumerate(sequences):
            fasta_content += f"> {i}\n{seq}\n"
        if os.path.exists(self._input):
            os.remove(self._input)
        with open(self._input, 'a') as file:
            file.write(fasta_content) 
        command = ""
        command += self._prefix + " " if self._prefix else ""
        command += MAFFT_PATH + " "  # Temporary, for testing with local mafft install
        options = [op for op in self._options if op != "--treeout"]
        command += " ".join(options) + " "
        command += self._input + " " if self._input else ""
        process = subprocess.run(command, capture_output=True, shell=True)

        if process.stderr:
            logging.error(process.stderr)

        if os.path.exists(self._input):
            os.remove(self._input)

        sequences, sequence_idxs =  Mafft._decode_process_output(process) 
        
        return [mel for _, mel in sorted({id: sequences[i] for i, id in enumerate(sequence_idxs)}.items())]

        
    def _generate_sequence_file(self, concatenate=False):
        sequences = []
        volpiano_map, ordered_siglums = [], []
        if concatenate:
            sequences, volpiano_map, ordered_siglums = ChantProcessor.concatenate_volpianos(self._sequences_to_align)
            subalignments = []
            for cantus_id_sequences in list(map(list, zip(*[seq.split("#") for seq in sequences]))):
                subalignments.append(self._align_sequences(cantus_id_sequences))
            sequences = list("#".join(seqs) for seqs in map(list, zip(*[alignment for alignment in subalignments])))
        else:
            for seq, volpiano_id, _, siglum in self._sequences_to_align:
                sequences.append(seq)
                volpiano_map.append(volpiano_id)
                ordered_siglums.append(siglum)

        for seq in sequences:
            with open(self._input, 'a') as file:
                name = str(self._counter)

                file.write("> " + name + "\n")
                file.write(seq + "\n")
                self._counter += 1
        return volpiano_map, ordered_siglums

    def add_volpiano(self, volpiano, volpiano_id, cantus_id, siglum):
        if not self._input:
            raise RuntimeError("Input file must be defined"
                               "before adding a chant")

        processed = pycantus.clean_volpiano(volpiano, keep_boundaries=False, keep_bars=False)
        
        self._sequences_to_align.append((processed, volpiano_id, cantus_id, siglum))



    def _special_symbols_need_to_be_added(indices, id, boundaries_index, to_add):
        for pause_index in indices[id]:
            if boundaries_index > pause_index:
                to_add[id] += 1
            else:
                break

    def _add_special_symbols(indices, id, boundaries_index, melody, special_symbol):
        while len(indices[id]) > 0 and boundaries_index > indices[id][0]:
            melody += special_symbol
            indices[id] = indices[id][1:]
        return melody

    def add_text_boundaries(mafft_aligned_melodies, volpianos, melody_order, keep_liquescents = True):
        if len(mafft_aligned_melodies) == 0:
            return []
        if not keep_liquescents:
            mafft_aligned_melodies = [mel.lower().replace("(", "8").replace(")", "9") for mel in mafft_aligned_melodies]
            volpianos = [
                ''.join(
                    (char.lower() if char not in {'Y', 'I', 'Z', 'X'} else char)
                    .replace("(", "8")
                    .replace(")", "9")
                    for char in mel
                )
                for mel in volpianos
            ]
        
        # remove all flats
        mafft_aligned_melodies = [mel.replace("y", "b").replace("Y", "B").replace("i", "j").replace("I", "J").replace("x", "m").replace("X", "M").replace("z", "q").replace("Z", "Q")
                                  for mel in mafft_aligned_melodies]

        melodies_with_boundaries = []
        word_indices = []
        syllable_indices = []
        pause_indices = []
        bb_indices = []
        bb1_indices = []
        eb1_indices = []
        bb2_indices = []
        notbb_indices = []
        notbb1_indices = []
        noteb1_indices = []
        notbb2_indices = []
        special_symbols = ["7", "|", "~", "y", "i", "x", "z", "Y", "I", "X", "Z"]
        indices = {
            "7": pause_indices, "|" : syllable_indices, "~": word_indices, 
            "y": bb_indices, "i": bb1_indices, "x": eb1_indices, "z": bb2_indices, 
            "Y": notbb_indices, "I": notbb1_indices, "X": noteb1_indices, "Z": notbb2_indices
        }
        for volpiano in volpianos:
            boundaries = volpiano.replace("---", "~")
            boundaries = boundaries.replace("--", "|")
            boundaries = boundaries.replace("-", "")
            if len(boundaries) > 0:
                # Make sure the first symbol is a 'new word' symbol
                if not (len(boundaries) >= 1 and boundaries[0] == "1"):
                    boundaries = "1" + boundaries
                if not (len(boundaries) >= 2 and boundaries[1] == "~"):
                    if len(boundaries) >= 2 and boundaries[1] == "|": # two dashes in volpiano instead of three looks more like a mistake
                        boundaries = boundaries[0] + "~" + boundaries[2:]
                    else:
                        boundaries = boundaries[0] + "~" + boundaries[1:]
                # Make sure the last symbol is a 'new word' symbol
                if not (len(boundaries) >= 1 and (boundaries[-1] == "4" or boundaries[-1] == "3")):
                    boundaries = boundaries + "4"
                if not (len(boundaries) >= 2 and boundaries[-2] == "~"):
                    if len(boundaries) >= 2 and boundaries[-2] == "|": # two dashes in volpiano instead of three looks more like a mistake
                        boundaries = boundaries[:-2] + "~" + boundaries[-1]
                    else:
                        boundaries = boundaries[:-1] + "~" + boundaries[1:]

            melodies_with_boundaries.append(boundaries)
        
            word_indices.append([index for index, char in enumerate(boundaries) if char == '~'])
            syllable_indices.append([index for index, char in enumerate(boundaries) if char == '|'])
            pause_indices.append([index for index, char in enumerate(boundaries) if char == '7'])
            bb_indices.append([index for index, char in enumerate(boundaries) if char == 'y'])
            bb1_indices.append([index for index, char in enumerate(boundaries) if char == 'i'])
            eb1_indices.append([index for index, char in enumerate(boundaries) if char == 'x'])
            bb2_indices.append([index for index, char in enumerate(boundaries) if char == 'z'])
            notbb_indices.append([index for index, char in enumerate(boundaries) if char == 'Y'])
            notbb1_indices.append([index for index, char in enumerate(boundaries) if char == 'I'])
            noteb1_indices.append([index for index, char in enumerate(boundaries) if char == 'X'])
            notbb2_indices.append([index for index, char in enumerate(boundaries) if char == 'Z'])

        boundaries_indices = [-1]*len(volpianos)
        aligned_melodies_with_text_boundaries = [""]*len(mafft_aligned_melodies)
        for aligned_melody_index in range(len(mafft_aligned_melodies[0]) + 1):
            to_add = [0]*len(volpianos)
            for i, id in enumerate(melody_order):  
                c = mafft_aligned_melodies[i][aligned_melody_index] if len(mafft_aligned_melodies[i]) > aligned_melody_index else None
                if c != "-":
                    boundaries_index = melodies_with_boundaries[id].find(c, boundaries_indices[id]+1) if not c is None else len(melodies_with_boundaries[id])
                    for special_symbol in special_symbols:
                        Mafft._special_symbols_need_to_be_added(indices[special_symbol], id, boundaries_index, to_add)

            overall_to_add = max(to_add)
            for i, id in enumerate(melody_order):  
                c = mafft_aligned_melodies[i][aligned_melody_index] if len(mafft_aligned_melodies[i]) > aligned_melody_index else None 
                aligned_melodies_with_text_boundaries[i] += "-"*(overall_to_add-to_add[id])
                if c != "-":
                    boundaries_index = melodies_with_boundaries[id].find(c, boundaries_indices[id]+1) if not c is None else len(melodies_with_boundaries[id])
                    for special_symbol in special_symbols:
                        aligned_melodies_with_text_boundaries[i] = Mafft._add_special_symbols(
                            indices[special_symbol], id, boundaries_index, aligned_melodies_with_text_boundaries[i], special_symbol
                        )
                    boundaries_indices[id] = boundaries_index
                aligned_melodies_with_text_boundaries[i] += c if not c is None else ""
        return aligned_melodies_with_text_boundaries


    def add_text(self, text):
        if not self._input:
            raise RuntimeError("Input file must be defined"
                               "before adding a chant")

        text = text.replace(' ', '~')
        with open(self._input, 'a') as file:
            file.write("> sequence " + str(self._counter) + "\n")
            file.write(text + "\n")
            self._counter += 1

    def _decode_process_output(process):
        if not process:
            raise RuntimeError("The process hasn't been run yet")

        if process.stderr:
            raise RuntimeError(process.stderr)
        
        if not process.stdout:
            return [], []

        stdout = process.stdout.decode('utf-8')
        sequences = []
        sequence_idxs = []
        cur_sequence = ""

        # Iterate over lines of FASTA-formatted MSA output.
        skip_next_sequence = False
        for part_sequence in stdout.split('\n'):
            # we are at the end of the output, only empty string remains
            if cur_sequence and not part_sequence:
                sequences.append(cur_sequence)
                cur_sequence = ""
            # row with the name of the sequence
            elif part_sequence and part_sequence[0] == '>':
                if part_sequence == "> " + CONCATENATE_PLACEHOLDER:
                    skip_next_sequence = True
                else:
                    skip_next_sequence = False
                    if cur_sequence:
                        sequences.append(cur_sequence)
                    cur_sequence = ""
                    sequence_idxs.append(int(part_sequence[2:]))
            # parts of the current sequence
            elif part_sequence and part_sequence[0] != '>':
                if not skip_next_sequence:
                    cur_sequence += part_sequence

        return sequences, sequence_idxs

    def decode_process(self):
        sequences, sequence_idxs =  Mafft._decode_process_output(self._process)
        self._aligned_sequences = sequences
        self._sequence_idxs = sequence_idxs



    def load_guide_tree(self, node_names=None):
        if not self._output_guide_tree_file:
            raise RuntimeError('Cannot load guide tree: no guide tree file defined.')
        if not os.path.isfile(self._output_guide_tree_file):
            raise RuntimeError('Cannot load guide tree: guide tree file {} not found.'
                               ''.format(self._output_guide_tree_file))
        self.__preprocess_guide_nodes(node_names=node_names) # remove placeholder node from the tree, used for concatenation workarround
        with open(self._output_guide_tree_file, 'r') as gt:
            gt_text = ''.join(gt.readlines())

        guide_tree = self.parse_guide_tree(gt_text)
        self._guide_tree = guide_tree


    def __preprocess_guide_nodes(self, node_names=None):
        tree = Tree(self._output_guide_tree_file)
        for node in tree.traverse():
            if "__" in node.name:
                if node.name.split("__")[1] == CONCATENATE_PLACEHOLDER.lower():
                    node.delete()
                elif node_names:
                    node.name = node_names[int(node.name.split("__")[1])]

        tree.write(outfile=self._output_guide_tree_file)

    def parse_guide_tree(self, gt_text):
        '''Guide tree data structure:

        Binary tree, every node also remembers its distace to its parent.
        '''
        # Not implemented yet.
        # Has to happen here, because the labels in the tree are defined w.r.t.
        # the MAFFT input file ordering (I guess).
        return gt_text


    def get_guide_tree(self, node_names=None):
        if not self._guide_tree:
            self.load_guide_tree(node_names)
        return self._guide_tree


    def get_aligned_sequences(self):
        if not self._aligned_sequences:
            self.decode_process()

        return self._aligned_sequences

    
    def get_sequence_order(self):
        if not self._sequence_idxs:
            self.decode_process()

        return self._sequence_idxs


    def run(self, concatenate=False):
        volpiano_map, ordered_siglums = self._generate_sequence_file(concatenate=concatenate)
        command = ""
        command += self._prefix + " " if self._prefix else ""
        command += MAFFT_PATH + " "  # Temporary, for testing with local mafft install
        command += " ".join(self._options) + " "
        if concatenate:
            command += "--keeplength --add " + self._input+"."+CONCATENATE_PLACEHOLDER + " " # MAFFT workarround to generate only the tree, but not change the alignment
            with open(self._input+"."+CONCATENATE_PLACEHOLDER, 'a') as file:
                file.write(f"> {CONCATENATE_PLACEHOLDER}\n\n") 
        command += self._input + " " if self._input else ""

        process = subprocess.run(command, capture_output=True, shell=True)

        if concatenate:
            if os.path.exists(self._input+"."+CONCATENATE_PLACEHOLDER):
                os.remove(self._input+"."+CONCATENATE_PLACEHOLDER)
        if process.stderr:
            print(process.stderr)
        elif process.stdout:
            if self._output:
                with open(self._output, 'w') as out:
                    out.write(process.stdout)

        self._process = process

        # reset run-specific values
        self._counter = 0
        self._aligned_sequences = None
        self._sequence_idxs = None
        return volpiano_map, ordered_siglums
