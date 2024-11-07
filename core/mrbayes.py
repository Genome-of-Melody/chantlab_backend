import os
import subprocess
import shutil
import re
import uuid
from django.conf import settings
import random
import string
import logging

def mrbayes_analyzis(ids, alpianos, number_of_generations, sources):
    mrbayes = MrBayesVolpiano(ngen = number_of_generations)
    newick, nexus_con_tre, nexus_alignment, mb_script, error_message = mrbayes.run(alignment_names=sources, alpianos=alpianos)
    
    result = {
        'newick': newick,
        'mbScript': mb_script,
        'nexusAlignment': nexus_alignment,
        'nexusConTre': nexus_con_tre,
        'error': error_message
    }

    return result

class MrBayesVolpiano():

    def __init__(self, mcmc_nruns = 4, ngen = 4000000, nchains=8, samplefreq=1000, printfreq=1000):
        self.mcmc_nruns = mcmc_nruns
        self.ngen = ngen
        self.nchains = nchains
        self.samplefreq = samplefreq
        self.printfreq = printfreq

    def run(self, alignment_names, alpianos):
        # normalize alignment names
        normalized_names = []
        for name in alignment_names:
            normalized_names.append(MrBayesVolpiano.__siglum_to_fasta_header_name(name))
        alignment_names = normalized_names
        melodies = {}
        partitions = []
        init_paritions = True
        for source_name, alpiano in zip(alignment_names, alpianos):
            aligned_sequence = alpiano.replace("|", "-")
            aligned_sequence = aligned_sequence.replace("~", "-")
            aligned_sequence = aligned_sequence.replace("1", "-")
            aligned_sequence = aligned_sequence.replace("4", "-")
            subsequences = aligned_sequence.split("#") # chant splitter
            if init_paritions:
                partitions = [0]
                for subsequence in subsequences:
                    partitions.append(len(subsequence) + partitions[-1])
                del partitions[0]
            else: 
                sequence_length = 0
                for i, subsequence in enumerate(subsequences):
                    if partitions[i] != sequence_length + len(subsequence):
                        logging.error("Different sequences have different partition lengths.")
                        logging.error(partitions)
                        logging.error(alpianos)
                        return "", "", "", "", "Melodies are not aligned! Different sequences have different partition lengths. Partitions: {} Alpianos: {}".format(partitions, alpianos)
                    sequence_length += len(subsequence)
            init_paritions = False
            melodies[source_name] = ''.join(subsequences)

        nexus_content = MrBayesVolpiano.__generate_nexus(sequences=melodies, ntax=len(melodies), nchar=partitions[-1])
        mb_content = self.__generate_mb(partitions=partitions)


        # Create a directory in the 'mrbayes-temp' folder with a randomly generated ID
        mrbayes_job_id = str(uuid.uuid4().hex)
        temp_dir = os.path.join('mrbayes-temp', mrbayes_job_id)
        os.makedirs(temp_dir)

        # Create nexus file and mb script in the created directory
        nexus_file_path = os.path.join(temp_dir, 'chantlab.nexus')
        mb_file_path = os.path.join(temp_dir, 'chantlab.mb')
        with open(nexus_file_path, 'w') as nexus_file:
            nexus_file.write(nexus_content)
        with open(mb_file_path, 'w') as mb_file:
            mb_file.write(mb_content)

        # Run the shell command "mb chantlab.mb" in the created directory
        subprocess.run(['mb', 'chantlab.mb'], cwd=temp_dir)

        try:
            # Load the file 'chantlab.nexus.con.tre'
            con_tre_file_path = os.path.join(temp_dir, 'chantlab.nexus.con.tre')
            with open(con_tre_file_path, 'r') as con_tre_file:
                nexus_con_tre = con_tre_file.read()
            newick = MrBayesVolpiano.__extract_newick(nexus_con_tre)
        except:
            logging.error("Cannot find chantlab.nexus.con.tre file - check the chantlab.log for more information.")
            con_tre_file_path = os.path.join(temp_dir, 'chantlab.log')
            with open(con_tre_file_path, 'r') as con_tre_file:
                log = con_tre_file.read()
            return "", "", nexus_content, mb_content, "Cannot find chantlab.nexus.con.tre file, check the log: {}".format(log)

        # Delete the generated directory and its contents
        shutil.rmtree(temp_dir)


        return MrBayesVolpiano.__rename_tree_nodes(newick, alignment_names), nexus_con_tre, nexus_content, mb_content, ""

    def __extract_newick(nexus_con_tre):
        newick_line = nexus_con_tre.split('\n')[-3]
        offset = len(newick_line.split('(')[0])
        return newick_line[offset:-1]


    def __generate_nexus(sequences, ntax, nchar):
        nexus_content = ""
        nexus_content += "#NEXUS\n"
        nexus_content += "BEGIN DATA;\n"
        nexus_content += "\tDIMENSIONS NTAX={} NCHAR={};\n".format(ntax, nchar)
        nexus_content += "\tFORMAT DATATYPE=STANDARD GAP=- MISSING=?;\n"
        nexus_content += "\tMATRIX\n"
        nexus_content += "\n"
        for source_name in sequences:
            nexus_content += "{}\t{}\n".format(source_name, sequences[source_name])
        nexus_content += ";\n"
        nexus_content += "end;"
        return nexus_content

    def __generate_mb(self, partitions):
        mb_file = ""
        mb_file += "begin mrbayes;\n"
        mb_file += "[Script documentation carried out using comments]\n"
        mb_file += "\n"
        mb_file += "[log the analysis]\n"
        mb_file += "log start filename=chantlab.log;\n"
        mb_file += "[read the matrix chantlab.nexus]\n"
        mb_file += "execute chantlab.nexus;\n"
        mb_file += "\n"
        mb_file += "[close analysis at end]\n"
        mb_file += "set autoclose=yes;\n"
        mb_file += "[This command shows the status of all the taxa, according to the documentation]\n"
        mb_file += "taxastat;\n"
        mb_file += "\n"
        mb_file += "[definition of individual partitions per marker come from partitions.txt]\n"
        partition_codes = set()
        partition_code = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 8))) 
        while len(partition_codes) != len(partitions):
            while partition_code in partition_codes:
                partition_code = ''.join(random.choices(string.ascii_lowercase, k=random.randint(5, 8)))
            partition_codes.add(partition_code)
        partition_codes = list(partition_codes)
        for i, (code, sequence_end) in enumerate(zip(partition_codes, partitions)):
            sequence_start = 1 if i == 0 else partitions[i-1] + 1
            mb_file += "charset {}={}-{};\n".format(code, sequence_start, sequence_end)    
        mb_file += "\n"
        mb_file += "[definition of the single partition]\n"
        mb_file += "partition chants={}:{};\n".format(len(partitions), ','.join(partition_codes))
        mb_file += "\n"
        mb_file += "[specification of substitution models]\n"
        mb_file += "set partition=chants;\n"
        mb_file += "lset applyto=(1) coding=all rates=invgamma; [Mkv+I+G, nstates is automatic for the standard datatype]\n"
        mb_file += "\n"
        mb_file += "[show the model just specified for each partition]\n"
        mb_file += "showmodel;\n"
        mb_file += "[set up the MCMC, with this setting the analysis will need not less than 16 threads]\n"
        mb_file += "mcmcp nruns={} ngen={} nchains={} samplefreq={} printfreq={};\n".format(self.mcmc_nruns, self.ngen, self.nchains, self.samplefreq, self.printfreq)
        mb_file += "[run the MCMC]\n"
        mb_file += "mcmc;\n"
        mb_file += "\n"
        mb_file += "[summarize the posterior trees]\n"
        mb_file += "sumt nruns=4 relburnin=yes burninfrac=0.50;\n"
        mb_file += "plot;\n"
        mb_file += "\n"
        mb_file += "[summarize parameter posteriors]\n"
        mb_file += "sump;\n"
        mb_file += "\n"
        mb_file += "log stop;\n"
        mb_file += "end;\n"

        return mb_file



    def __rename_tree_nodes(tree_string, names):
        def _sub_group(match):
            index = int(match.group(2))-1
            return f"{match.group(1)}{names[index]}{match.group(3)}"

        tree_string = ''.join(tree_string.split('\n'))
        
        named_tree_string = re.sub(r'([\(,])([0-9]+)(\[)', 
                                lambda m: _sub_group(m), 
                                tree_string)
        
        return named_tree_string


    def __siglum_to_fasta_header_name(siglum):
        '''Formats a siglum to a string that can be used as a FASTA header.
        This means discarding all special characters, and changing all whitespace to underscores,
        to make compatibility with any FASTA-reading software more likely.
        '''
        siglum = siglum.replace('.', '_')  # Dots often separate elements of a numbering system
        siglum = siglum.replace(',', '_')  # Dots often separate elements of a numbering system
        siglum = siglum.replace('/', '_')  # Slashes as well.
        siglum = siglum.replace('\\', '_')
        siglum = siglum.replace(':', '')   # Semicolons are usually only separators between RISM ID part and rest of siglum.
        siglum = siglum.replace('(', '')   # Parentheses are not important separators
        siglum = siglum.replace(')', '')
        siglum = siglum.replace('<', '')
        siglum = siglum.replace('>', '')
        siglum = siglum.replace('"', '')
        siglum = siglum.replace('*', '')
        siglum = siglum.replace('#', '')
        siglum = siglum.replace('&', '')
        siglum = siglum.replace('%', '')
        siglum = siglum.replace('@', '')
        siglum = siglum.replace('!', '')
        siglum = siglum.replace('=', '')
        siglum = siglum.replace("'", "")
        siglum = siglum.replace(";", "")
        siglum = siglum.replace('-', '_')  # Unfortunately, dashes from RISM sigla like CZ-Pu can also be risky.

        siglum = siglum.replace(' ', '_')
        return siglum