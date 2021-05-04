import subprocess

class Mafft():

    def __init__(self):
        self._input = None
        self._output = None
        self._options = ['--quiet']
        # this should eventually be removed
        self._prefix = "wsl"
        self._counter = 0
        self._process = None


    def set_input(self, file):
        # add check if the file exists?
        self._input = file

    
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
            file.write("> sequence " + str(self._counter) + "\n")
            file.write(processed + "\n")
            self._counter += 1

    
    def get_aligned_sequences(self):
        if not self._process:
            raise RuntimeError("The process hasn't been run yet")

        if self._process.stderr:
            raise RuntimeError(self._process.stderr)
        
        if not self._process.stdout:
            raise RuntimeError("No aligned sequences found")

        stdout = self._process.stdout.decode('utf-8')
        sequences = []
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
            # parts of the current sequence
            elif part_sequence and part_sequence[0] != '>':
                cur_sequence += part_sequence

        return sequences


    def run(self):
        command = ""
        command += self._prefix + " " if self._prefix else ""
        command += "mafft "
        command += " ".join(self._options) + " "
        command += self._input + " " if self._input else ""
        # the --out option doesn't seem to be working?
        # command += "--out " + self._output if self._output else ""
        process = subprocess.run(command, capture_output=True)
        if process.stderr:
            print(process.stderr)
        elif process.stdout:
            if self._output:
                with open(self._output, 'w') as out:
                    out.write(process.stdout)

        self._process = process


def _preprocess_volpiano(volpiano):
    res = volpiano.replace("---", "~")      # word separator
    res = res.replace("--", "|")            # syllable separator
    res = res.replace("-", "")              # remove all other -s
    return res



