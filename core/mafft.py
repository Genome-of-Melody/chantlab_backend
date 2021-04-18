import subprocess

class Mafft():

    def __init__(self):
        self._input = None
        self._output = None
        self._options = ['--quiet']
        # this should eventually be removed
        self._prefix = "wsl"


    def set_input(self, file):
        # add check if the file exists?
        self._input = file

    
    def set_output(self, file):
        self._output = file

    
    def add_option(flag, value=None):
        self._options.append(flag)
        if value:
            self._options.append(value)


    def set_prefix(prefix):
        self._prefix = prefix


    def add_volpiano(volpiano):
        if not self._input:
            raise RuntimeError("Input file must be defined"
                               "before adding a chant")
                               
        processed = _preprocess_volpiano(volpiano)
        with open(self._input, 'a') as file:
            file.write(processed)


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
            else:
                print(process.stdout)


def _preprocess_volpiano(volpiano):
    res = volpiano.replace("---", "~")      # word separator
    res = res.replace("--", "|")            # syllable separator
    res = res.replace("-", "")              # remove all other -s
    return res



