import os
import subprocess
import sys

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


    def add_volpiano(self, volpiano):
        if not self._input:
            raise RuntimeError("Input file must be defined"
                               "before adding a chant")
                               
        processed = _preprocess_volpiano(volpiano)
        with open(self._input, 'a') as file:
            file.write("> " + str(self._counter) + "\n")
            file.write(processed + "\n")
            self._counter += 1

    
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
            gt_text = ''.join(gt.readline())

        guide_tree = self.parse_guide_tree(gt_text)
        self._guide_tree = guide_tree


    def parse_guide_tree(self, gt_text):
        '''Guide tree data structure:

        Binary tree, every node also remembers its distace to its parent.
        '''
        # Not implemented yet.
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
        command += "mafft "
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


def _preprocess_volpiano(volpiano):
    res = volpiano.replace("---", "~")      # word separator
    res = res.replace("--", "|")            # syllable separator
    res = res.replace("-", "")              # remove all other -s
    return res



