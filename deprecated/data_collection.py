from git import Repo
# from cppcheck import CPPCheck
import argparse
import glob
import shutil
import os
from os import path
import subprocess
import pickle
import format_infer
from bug_report import Bug, BugReport
import format_clang
import time
import IPython

import sys
sys.setrecursionlimit(100000)

parser = argparse.ArgumentParser(description="...")
parser.add_argument('-r', required=True, help="Path to repository")
parser.add_argument('-b', default='master', help="Branch to examine")
parser.add_argument('-s', default=None, help="Directory to save intermediary bug reports to")
parser.add_argument('-f', action='store_true', 
                     help="Record new bugs that appear, not just those at the starting commit")
parser.add_argument('-tool', default='cppcheck', help="Static analysis tool to run")
parser.add_argument('-command', default='make', help="Command to compile build")
parser.add_argument('-clean', default='make clean', help="Command to clean build")
parser.add_argument('-reverse', default=False, help="Start from very first commit")
parser.add_argument('-end', default=200, help="Number of commits to iterate")
parser.add_argument('-start', default=0, help="Starting commit to iterate")
parser.add_argument('-inc', default=1, help="Increment number of commits to iterate by")
parser.add_argument('-data_only', default=False, help="Just collect bug reports")



class EventsReport:
    """
        An EventsReport is supplementary to a BugReport and logs how bugs
        and their files have changed over time.
    """
    def __init__(self, bug_list, debug=True):
        self.bug_list = bug_list
        self.debug = debug
        self.resolved_vec = [-1 for _ in self.bug_list]
        self.block_changed = [[] for _ in self.bug_list] 
    
    def update_resolved(self, idx, depth, resolved):
        if self.debug: print("Bug #{}:".format(idx + 1))
        if self.debug: print("M: {}".format(self.bug_list[idx].fname))

        self.block_changed.append(depth)
        if resolved:
            if self.debug: print("Bug fixed!")
            self.resolved_vec[idx] = depth
        else:
            if self.debug: print("Bug block changed, but not resolved")
        if self.debug: print("-----------")

    def resolved_distribution(self):
        resolved_types = {}
        for i, r in enumerate(self.resolved_vec):
            if r >= 0:
                t = self.bug_list[i].bug_type
                if t not in resolved_types:
                    resolved_types[t] = 0
                resolved_types[t] += 1
        for t in resolved_types:
            print(t, resolved_types[t])
    
    def get_bugs(self):
        to_return = []
        for i, r in enumerate(self.resolved_vec):
            if r >= 0:
                to_return.append(self.bug_list[i])
        return to_return

class BugReport:
    """
        A bug report stores a list of bugs for a given commit of a repo, or
        for a specified filename
    """
    def __init__(self, commit, tool, command, clean, dir, fname=None, save_dir=None):
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
        self.get_bugs()

    def cppcheck(self, run_dir):
        result = subprocess.run(["cppcheck", "--enable=all", "--inconclusive",
            "--quiet", run_dir], stderr=subprocess.PIPE)
        
        t = {} 
        # Parse bugs
        to_parse = result.stderr.decode("utf-8").split("\n")
        for i in range(0, len(to_parse), 3):
           if i + 3 > len(to_parse):
               break

           err = to_parse[i].split(":")
           print(err)
                    
           code = to_parse[i+1]
           fname = err[0]
           line_no = int(err[1])
           pos = int(err[2])
           bug_type = err[3][1:]
           desc = err[4][1:]

           bug = Bug(fname, desc, code, bug_type, bug_type, (line_no, line_no), self.commit)
           self.bugs.append(bug)

           if bug_type not in self.type_map:
               self.type_map[bug_type] = []
           self.type_map[bug_type].append(bug)

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

        if "No bugs found." in out[-2] or "No bugs found." in out[-3]:
            print("No bugs were found. Exiting early.")
            exit(-1)
        
        #directory should be in here
        # print(out)
        direct = out[-2].replace("\\", "").split("'")[1].split()[1]
        # print("direct", direct)
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
            
            if caught_bug['type'] not in self.type_map:
               self.type_map[caught_bug['type']] = []
            self.type_map[caught_bug['type']].append(bug)

            fname = caught_bug['file']
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

    def get_bugs(self):
        # Instantiate bug report from file if it exists
        if self.save_dir is not None and self.br_file in os.listdir(self.save_dir):
            path = os.path.join(self.save_dir, self.br_file)
            with open(path, "rb") as f:
                d = pickle.load(f)
                for attr in d:
                    setattr(self, attr, d[attr])
            print("Loaded bug report from {}".format(self.br_file))
            return 

        run_dir = self.fname if self.fname is not None else "."
        print("Running bug checker on commit {}, {}...".format(self.commit, run_dir))
        if self.tool == "cppcheck":
            self.cppcheck(run_dir)
        elif self.tool == "infer":
            self.infer()
        elif self.tool == "clang_firefox":
            self.clang_firefox()

        # Save the bug report to a file since it hasn't been saved before.
        if self.save_dir is not None:
            self.save()

    def save(self):
        path = os.path.join(self.save_dir, self.br_file)
        with open(path, "wb") as f:
            pickle.dump(self.__dict__, f)
        print("Saved bug report to {}".format(self.br_file))


def get_files_changed(commit):
    """
        commit: compares HEAD to commit, where commit is AHEAD of HEAD
        return: a dictionary from filename to list. List contains the type of
                change as the first element and additional arguments following
                it optionally. For example a rename will have an array
                containing "R" as the first element and the destination filename
                as the second element, i.e, what the file was renamed to.
    """
    # Check if file was modified
    # Note: HEAD precedes commit because t(HEAD) < t(commit)
    result = subprocess.run(["git", "diff", "HEAD", commit, "--name-status"], stdout=subprocess.PIPE)
    files_changed = result.stdout.decode("utf-8").split("\n")[:-1]
   
    to_return = {}

    # Can't simply check if only the file was changed, because then it will
    # show a rename as a delete. So, we go through all changes and renames 
    # appear. 
    for line in files_changed:
        out = line.split("\t")
        status = out[0]
        f = out[1]

        to_return[f] = []
        to_return[f].append(status[0])
        if status[0] == 'R':
            to_return[f].append(out[2])

    return to_return

def get_lines_modified(commit, fname):
   """
        commit: compares HEAD to commit, where commit is AHEAD of HEAD
        fname : a file which has been changed from HEAD -> commit   
        return: two non-empty lists of tuples indicating start and end of line
        changes in source and dest files respectively
  """
   srcs = []
   dsts = []
   result = subprocess.run(["git", "diff", "HEAD", commit, "--", fname], stdout=subprocess.PIPE)
   
   # Get the line change info lines
   lines = result.stdout.decode("utf-8").split("\n")
   lines = filter(lambda x: x.count("@@") == 2, lines)
   
   for line in lines:
      toks = line.split(' ')
      if len(toks) < 4:
          continue
     
      def get_hunk(src):
          start = None
          end = None   
          if ',' in src:
             (start, d) = src.split(',')
             start = int(start)
             end = start + int(d)
          else:
             start = int(src)
             end = start
          return (start, end)

      src = get_hunk(toks[1][1:])
      dst = get_hunk(toks[2][1:])
 
      srcs.append(src)
      dsts.append(dst)
   
   assert len(srcs) > 0
   assert len(dsts) > 0
   return srcs, dsts
   
def update_unmodified_bug(bug):
    """
        Given a bug, the method will find the bug in its specified file
        and update its locs to the nearest found match. If no match,
        throws an assertion error.
    """
    f = open(bug.fname)
    file_lines = f.read().split('\n')
    f.close()
    
    # Get all matches for bug code
    matches = []
    for j in range(len(file_lines)):
        line = file_lines[j]
        if bug.code in line:
            matches.append(j)

    if len(matches) == 0:
        IPython.embed()
    assert len(matches) > 0, "error: bug lost"
    bug_loc = matches[0]

    # find the nearest match to the orig line of code
    if len(matches) > 1:
        diffs = (lambda val, l: [abs(e - val) for e in l])(bug.locs[0], matches) 
        bug_loc = matches[diffs.index(min(diffs))]

    # Update bug line of code
    bug.locs = (bug_loc, bug_loc)


def check_if_bug_resolved(bug, new_br, d):
    """
        Given a bug and a bug report, tries to find a matching
        bug in the new bug report for this bug. If a match is found,
        then the bug is updated to the matched bug. Otherwise, the
        bug is considered resolved.

        d: The destination locs of the bug
        return: Whether or not the bug was resolved.
    """
    any_same_bug = False
    
    # We know that filename exists in new_br's commit because the
    # file was modified, not renamed. So the bug must have been 
    # resolved and there are no bugs in the file in this case. 
    if bug.fname not in new_br.file_map:
        return True


    for bug_in_fname in new_br.file_map[bug.fname]:
        same_bug = d[0] <= bug_in_fname.locs[0] <= d[1]
        same_bug = d[0] <= bug_in_fname.locs[1] <= d[1] and same_bug
        same_bug = bug_in_fname.desc == bug.desc and same_bug
        same_bug = bug_in_fname.code == bug.code and same_bug

        # Update the bug 
        if same_bug:
            any_same_bug = True
            bug = bug_in_fname
            print("Bug match found and updated")
            break

    resolved = not any_same_bug
    return resolved


def br_distribution(br):
    for t in br.type_map:
        print(t, len(br.type_map[t]))
    print()


    
if __name__ == '__main__':
    print("------------------Starting to run-----------------")

    args = parser.parse_args()
    if not os.path.exists(args.r):
        print("Error: {} is not a path to a valid git repo".format(args.r))
        exit(1)

    save_br = args.s is not None
    save_dir = args.s
    if save_br and not os.path.isdir(os.path.abspath(save_dir)):
        print("Error: {} is not a valid directory".format(save_dir))
        exit(1)
    
    print("------------------Checking out repository-----------------")

    os.chdir(args.r)
    repo = Repo(os.getcwd())
    repo.git.checkout(args.b)

    print("------------------Checked out repository-----------------")

    commits = [repo.head.commit.hexsha]
    for c in repo.head.commit.iter_parents():
        if bool(args.reverse):
            commits.insert(0, c.hexsha)
        else:
            commits.append(c.hexsha)

    # yuzu_checker = CPPCheck(args.r)
    # start_of_bug = yuzu_checker.find_start(repo, "nullPointer",
    #                                           "./src/common/file_util.cpp", commits)

    # Get the bug report for the starting commit
    start = int(args.end)
    end = int(args.start)
    inc = -int(args.inc)
    if bool(args.reverse):
        start = int(args.start)
        end = int(args.start) + int(args.end)
        inc = int(args.inc)

    print("------------------Checking out starting commit-----------------")
    repo.git.checkout(commits[start])
    start_time = time.time()
    br = BugReport(commits[start], tool=args.tool, 
        command=args.command, clean=args.clean, dir=args.r, save_dir=save_dir)
    end_time = time.time()
    print("Bug report took: {} seconds".format(end_time-start_time))
    bug_list = None
    if args.tool == "cppcheck":
        bug_list = br.type_map["error"]
    elif args.tool == "infer":
        bug_list = br.type_map["ERROR"]
    elif args.tool == "clang_firefox":
        bug_list = br.type_map["error"]   
    # bug_list = br.bugs
    er = EventsReport(bug_list)

    br_distribution(br)
    print(br.commit)
    print("Running static analysis over time on {} bugs".format(len(bug_list)))
    print("===========")

    if bool(args.data_only):
        start += inc
        for i in range(start, end, inc): 
            print("------------------Checking out commit {}-----------------".format(i/inc))
            repo.git.checkout(commits[i])
            if not bool(args.reverse):
                print("Commit {} {}/{}".format(commits[i][:5], start - i + 1, start))
            else:
                print("Commit {} {}/{}".format(commits[i][:5], i, end))
            start_time = time.time()
            new_br = BugReport(commits[i], tool=args.tool, 
                command=args.command, clean=args.clean, dir=args.r, save_dir=save_dir)
            end_time = time.time()
            print("Bug report took: {} seconds".format(end_time-start_time))
        exit(0)

     
    # Look through all commits pairwise for changes starting at the bug 
    for i in range(start, end, inc): 
        repo.git.checkout(commits[i])
        if not bool(args.reverse):
            print("Commit {} {}/{}".format(commits[i][:5], start - i + 1, start))
        else:
            print("Commit {} {}/{}".format(commits[i][:5], start + i, end))
        
        f_changes = get_files_changed(commits[i-inc])

        # Looking for new bugs in next commit.
        if i != start: 
            curr_br = BugReport(commits[i], tool=args.tool, command=args.command, clean=args.clean, dir=args.r) 
            next_br = BugReport(commits[i-1], tool=args.tool, command=args.command, clean=args.clean, dir=args.r)
            
            
            for f_change in f_changes:
                change = f_changes[bug.fname][0]
                if change == "M":

                    new_bugs = []
                    if f_change not in curr_br.file_map:
                        new_bugs = next_br.file_map[f_change]

                    else:
                        existing_bugs = curr_br.file_map[f_change]
                        existing_bugs_resolved = [False for _ in existing_bugs]
                        
                        srcs, dsts = get_lines_modified(commits[i-1], bug.fname)
                        for bug_idx, bug in enumerate(existing_bugs):

                            # Find whether bug was resolved or not
                            did_bug_ever_change = False
                            for j in range(len(srcs)):
                                s = srcs[j]
                                bug_changed = s[0] <= bug.locs[0] <= s[1]
                                bug_changed = s[0] <= bug.locs[1] <= s[1] and bug_changed

                                if bug_changed:
                                    did_bug_ever_change = True

                                repo.git.checkout(commits[i-1])
                                d = dsts[j]
                                existing_bugs_resolved[bug_idx] = check_if_bug_resolved(bug, next_br, d)

                            # If the bug didn't change, find it in the changed file
                            # and update its new line number.
                            if not did_bug_ever_change:
                                # print("Bug didn't change")
                                repo.git.checkout(commits[i-1])
                                update_unmodified_bug(bug)

                            # reset repo to head for next bug.
                            repo.git.checkout(commits[i])

                        # TODO: bug hashing and check for new bug hashes in next_br



        for idx, bug in enumerate(bug_list):
            # Ignore bug if it has been resolved
            if er.resolved_vec[idx] != -1:
                continue

            if bug.fname not in f_changes:
                continue

            change = f_changes[bug.fname][0]
            if change == "R":
                bug.fname = f_changes[bug.fname][1]

            if change == "M":
                srcs, dsts = get_lines_modified(commits[i-inc], bug.fname)
               
                # Check if the bug was changed at all in this file. 
                did_bug_ever_change = False
                for j in range(len(srcs)):
                    s = srcs[j]
                    bug_changed = s[0] <= bug.locs[0] <= s[1]
                    bug_changed = s[0] <= bug.locs[1] <= s[1] and bug_changed

                    if bug_changed:
                        did_bug_ever_change = True

                        # rerun bug checker on specific file and compare 
                        # before and after bug reports

                        repo.git.checkout(commits[i-inc]) 
                        new_br = BugReport(commits[i-inc], tool=args.tool, 
                            command=args.command, clean=args.clean, dir=args.r, fname=bug.fname)
                        d = dsts[j]
                        resolved = check_if_bug_resolved(bug, new_br, d)
                        er.update_resolved(idx, start - i, resolved)

                # If the bug didn't change, find it in the changed file
                # and update its new line number.
                if not did_bug_ever_change:
                    # print("Bug didn't change")
                    repo.git.checkout(commits[i-inc])
                    update_unmodified_bug(bug)
                    # print("-----------")

            # reset repo to head for next bug.
            repo.git.checkout(commits[i])
        print("===========")
    #IPython.embed()

