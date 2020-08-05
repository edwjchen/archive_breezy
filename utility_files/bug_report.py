import subprocess
import os
import pickle 
from utility import format_infer
from utility import format_clang
import IPython
import ast


class Bug:
    """
        A bug is defined by the file it lives in, the commit that it is in,
        it's description and lines of code
    """
    def __init__(self, fname, desc, code, bug_type, severity, locs, commit):
        self.fname = fname
        self.desc = desc
        self.code = code
        self.bug_type = bug_type
        self.severity = severity
        self.locs = locs
        self.commit = commit

    def __hash__(self):
        """
            Note: this hash function explicitly does NOT take into account bug location.
            It's purpose is to identify bugs that have moved around in code by modification
            of other pieces of code, not the bug itself. Therefore, a bug's identity is somewhat
            location independent.
        """
        to_return = 0
        to_return ^= hash(self.fname)
        to_return ^= hash(self.desc)
        to_return ^= hash(self.code)
        to_return ^= hash(self.bug_type)
        to_return ^= hash(self.severity)
        return to_return

    def __repr__(self):
        return str(self.__dict__)

class BugReport:
    """
        A bug report stores a list of bugs for a given commit of a repo, or
        for a specified filename
    """
    def __init__(self, commit, dir, tool="cppcheck", command="cppcheck", clean="make clean", fname=None, save_dir=None, compile_bugs=False):
        self.commit = commit
        self.bugs = []
        self.type_map = {}
        self.file_map = {}
        self.tool = tool
        self.command = command
        self.clean = clean
        self.dir = dir
        self.fname = fname
        self.save_dir = save_dir
        self.br_file = "bug_report_{}.bin".format(self.commit[:5])
        self.br_txtfile = "bug_report_{}.txt".format(self.commit[:5])
        if not compile_bugs:
            self.get_bugs()

    def __repr__(self):
        return str(self.__dict__)

    def cppcheck(self, run_dir):
        result = subprocess.run(["cppcheck", "--enable=all", "--inconclusive",
            "--quiet", run_dir], stderr=subprocess.PIPE)
        
        t = {} 
        # Parse bugs
        to_parse = result.stderr.decode("utf-8").split("\n")

        i = 0
        while i < len(to_parse):
            if '^' in to_parse[i]:
                i += 1
                continue
            err = to_parse[i].split(':')
            code = ""
            fname = err[0]
            line_no = int(err[1])
            pos = int(err[2])
            bug_type = err[3][1:]
            desc = err[4][1:]

            next_carat = 0
            carat_found = False
            while not carat_found:
                next_carat += 1
                carat_found = '^' in to_parse[next_carat]
                if not carat_found:
                    code += to_parse[next_carat]
       
            i += next_carat + 1
            
            bug = Bug(fname, desc, code, bug_type, bug_type, (line_no, line_no), self.commit)
            self.bugs.append(bug)

            if bug_type not in self.type_map:
                self.type_map[bug_type] = []
            self.type_map[bug_type].append(bug)

            if fname not in self.file_map:
                self.file_map[fname] = []
            self.file_map[fname].append(bug)
           
    def infer(self):
        #remove previous instance of infer output if there is 
        # if os.path.isdir("./infer-out"):
        #     for i in glob.glob(os.path.join("./infer-out", '*')):
        #         shutil.rmtree("./infer-out")

        #clean build before running infer
        result = subprocess.run(self.clean.split())
        #run infer 
        result = subprocess.run(self.command.split())

        #format infer_out file
        list_of_bugs = format_infer.format(self.dir)
        for caught_bug in list_of_bugs:
            lineno = caught_bug['line']
            bug = Bug(caught_bug['file'], 
                    caught_bug['qualifier'], 
                    caught_bug['code'], 
                    caught_bug['bug_type'], 
                    caught_bug['severity'],
                    (int(lineno), int(lineno)), 
                    self.commit)
            self.bugs.append(bug)
            
            bug_severity = caught_bug['severity']
            if bug_severity not in self.type_map:
               self.type_map[bug_severity] = []
            self.type_map[bug_severity].append(bug)

            fname = caught_bug['file']
            if fname not in self.file_map:
                self.file_map[fname] = []
            self.file_map[fname].append(bug)

    def clang_firefox(self):
        #command to build browser subrepo == ./mach build browser
        print("------------------Creating .mozconfig------------------")
        f = open(".mozconfig", "w")
        f.write('mk_add_options MOZ_OBJDIR=@TOPSRCDIR@/obj-ff-dbg\nmk_add_options MOZ_BUILD_PROJECTS="browser"\nmk_add_options AUTOCLOBBER=1\nac_add_options --disable-optimize --enable-debug')
        f.close()

        subprocess.run("rm -rf obj-ff-dbg/".split())
        print("------------------Scanning build------------------")
        
        proc = subprocess.Popen(["scan-build","--show-description", "-o", "../breezy/clang_output/"+self.commit] + self.command.split(), stdout=subprocess.PIPE)
        out, err = proc.communicate()
        out = str(out).split("\\n")
        print(out)
        return

        if "No bugs found." in out[-2] or "No bugs found." in out[-3]:
            print("No bugs were found. Exiting early.")
            exit(-1)
        
        #directory should be in here
        # print(out)
        direct = out[-2].replace("\\", "").split("'")[1].split()[1]
        print("direct", direct)
        
        list_of_bugs = format_clang.format(direct)
        print("Number of bugs found: ", len(list_of_bugs))
        for caught_bug in list_of_bugs:
            lineno = caught_bug['line']
            bug = Bug(caught_bug['file'], 
                    caught_bug['desc'], 
                    caught_bug['code'], 
                    caught_bug['group'], 
                    caught_bug['type'],
                    (int(lineno), int(lineno)), 
                    self.commit)
            self.bugs.append(bug)
            
            if caught_bug['group'] not in self.type_map:
               self.type_map[caught_bug['group']] = []
            self.type_map[caught_bug['group']].append(bug)

            fname = caught_bug['file']
            if fname not in self.file_map:
                self.file_map[fname] = []
            self.file_map[fname].append(bug)

    def get_bugs(self):
        # Instantiate bug report from file if it exists
        if self.save_dir is not None and self.br_file in os.listdir(self.save_dir):
            # path = os.path.join(self.save_dir, self.br_file)
            # with open(path, "rb") as f:
            #     d = pickle.load(f)
            #     for attr in d:
            #         setattr(self, attr, d[attr])
            # print("Loaded bug report from {}".format(self.br_file))

            self.load()
            return 

        run_dir = self.fname if self.fname is not None else "."
        print("Running bug checker on commit {}, {}...".format(self.commit[:5], run_dir))
        if self.tool == "cppcheck":
            self.cppcheck(run_dir)
        elif self.tool == "infer":
            self.infer()
        elif self.tool == "clang_firefox":
            self.clang_firefox()
        else:
            assert False

        # Save the bug report to a file since it hasn't been saved before.
        if self.save_dir is not None:
            self.save()

    def load(self):
        # try:
        #     print(self.br_file)
        #     path = os.path.join(self.save_dir, self.br_file)
        #     with open(path, "rb") as f:
        #         br_str = pickle.load(f)
        #         print(br_str)
        #     print("Loaded bug report from {}".format(self.br_file))
        # except Exception as e:
        #     print('load exception thrown')
        #     print(e)

        path = os.path.join(self.save_dir, self.br_txtfile)
        with open(path, "r") as f:
            br_str = f.read()
            self._load_parser(br_str)
        f.close()
        print("Loaded bug report from {}".format(self.br_txtfile))

    def _load_parser(self, input):
        output = ast.literal_eval(input)
        self.commit = output['commit']
        self.dir = output['dir']
        self.tool = output['tool']
        self.command = output['command']
        self.clean = output['clean']
        self.fname = output['fname']
        self.save_dir = output['save_dir']
        self.br_file = output['br_file']
        self.br_txtfile = output['br_txtfile']

        serialized_bug_list = output['bugs']
        deserialized_bug_list = self.bugs
        for serialized_bug in serialized_bug_list:
            deserialized_bug = Bug(
                serialized_bug['fname'], 
                serialized_bug['desc'], 
                serialized_bug['code'], 
                serialized_bug['bug_type'], 
                serialized_bug['severity'], 
                serialized_bug['locs'], 
                serialized_bug['commit'])

            deserialized_bug_list.append(deserialized_bug)

            bug_type = serialized_bug['bug_type']
            fname = serialized_bug['fname']

            if bug_type not in self.type_map:
                self.type_map[bug_type] = []
            self.type_map[bug_type].append(deserialized_bug)

            if fname not in self.file_map:
                self.file_map[fname] = []
            self.file_map[fname].append(deserialized_bug)

    def save(self):
        # IPython.embed()
        # try:
        #     path = os.path.join(self.save_dir, self.br_file)
        #     print(path)
        #     with open(path, "wb") as f:
        #         pickle.dump((repr(self), f))
        #     print("Saved bug report to {}".format(self.br_file))
        #     f.close()
        #     return
        # except Exception as e:
        #     print('save exception thrown')
        #     print(e)

        path = os.path.join(self.save_dir, self.br_txtfile)
        with open(path, "w") as f:
            f.write(repr(self))
        f.close()
        print("Saved bug report to {}".format(self.br_txtfile))
        
