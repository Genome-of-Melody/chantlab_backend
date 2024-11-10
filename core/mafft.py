import os
import subprocess
import sys
from core import pycantus # TODO replace by pycantus library once it will be public

MAFFT_PATH = '/Users/hajicj/CES_TF/mafft/mafft-mac/mafftdir/bin/mafft'
if not os.path.isfile(MAFFT_PATH):
    MAFFT_PATH = 'mafft'

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


    def add_volpiano(self, volpiano, name=None):
        if not self._input:
            raise RuntimeError("Input file must be defined"
                               "before adding a chant")

        processed = pycantus.clean_volpiano(volpiano, keep_boundaries=False, keep_bars=False)
        with open(self._input, 'a') as file:

            if name is None:
                name = str(self._counter)

            file.write("> " + name + "\n")
            file.write(processed + "\n")
            self._counter += 1

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


    def decode_process(self):
        if not self._process:
            raise RuntimeError("The process hasn't been run yet")

        if self._process.stderr:
            raise RuntimeError(self._process.stderr)
        
        if not self._process.stdout:
            self._aligned_sequences = []
            self._sequence_idxs = []

        stdout = self._process.stdout.decode('utf-8')
        sequences = []
        sequence_idxs = []
        cur_sequence = ""

        # Iterate over lines of FASTA-formatted MSA output.
        for part_sequence in stdout.split('\n'):
            # we are at the end of the output, only empty string remains
            if cur_sequence and not part_sequence:
                sequences.append(cur_sequence)
                cur_sequence = ""
            # row with the name of the sequence
            elif part_sequence and part_sequence[0] == '>':
                if cur_sequence:
                    sequences.append(cur_sequence)
                cur_sequence = ""

                sequence_idxs.append(int(part_sequence[2:]))
            # parts of the current sequence
            elif part_sequence and part_sequence[0] != '>':
                cur_sequence += part_sequence

        self._aligned_sequences = sequences
        self._sequence_idxs = sequence_idxs


    def load_guide_tree(self):
        if not self._output_guide_tree_file:
            raise RuntimeError('Cannot load guide tree: no guide tree file defined.')
        if not os.path.isfile(self._output_guide_tree_file):
            raise RuntimeError('Cannot load guide tree: guide tree file {} not found.'
                               ''.format(self._output_guide_tree_file))

        with open(self._output_guide_tree_file, 'r') as gt:
            gt_text = ''.join(gt.readlines())

        guide_tree = self.parse_guide_tree(gt_text)
        self._guide_tree = guide_tree


    def parse_guide_tree(self, gt_text):
        '''Guide tree data structure:

        Binary tree, every node also remembers its distace to its parent.
        '''
        # Not implemented yet.
        # Has to happen here, because the labels in the tree are defined w.r.t.
        # the MAFFT input file ordering (I guess).
        return gt_text


    def get_guide_tree(self):
        if not self._guide_tree:
            self.load_guide_tree()
        return self._guide_tree


    def get_aligned_sequences(self):
        if not self._aligned_sequences:
            self.decode_process()

        return self._aligned_sequences

    
    def get_sequence_order(self):
        if not self._sequence_idxs:
            self.decode_process()

        return self._sequence_idxs


    def run(self):
        command = ""
        command += self._prefix + " " if self._prefix else ""
        command += MAFFT_PATH + " "  # Temporary, for testing with local mafft install
        command += " ".join(self._options) + " "
        command += self._input + " " if self._input else ""
        process = subprocess.run(command, capture_output=True, shell=True)

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
