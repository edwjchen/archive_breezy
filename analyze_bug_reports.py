from git import Repo
import argparse
import subprocess
import os
from os import listdir
from os.path import isfile, join
from utility.bug_report import Bug, BugReport
from utility.event_report import EventsReport
import datetime
from datetime import timedelta
import time
import IPython
import pickle

#python3 analyze_bug_reports.py -r ../gecko-dev/ -tool "clang_firefox" -s "/home/edwjchen/breezy/clang_bug_reports_save"

parser = argparse.ArgumentParser(description="This program generates intermediary bug reports to be later analyzed.")
parser.add_argument('-r', help="Path to repository")
parser.add_argument('-b', default='master', help="Branch to examine")
parser.add_argument('-s', default=None, help="Directory to save intermediary bug reports to")
parser.add_argument('-tool', default='cppcheck', help="Static analysis tool to run")
parser.add_argument('-command', default='make', help="Command to compile build")
parser.add_argument('-clean', default='make clean', help="Command to clean build")
parser.add_argument('-load', default='', help="Load saved data")


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

def get_lines_modified(curr_commit, next_commit, fname):
   """
        commit: compares HEAD to commit, where commit is AHEAD of HEAD
        fname : a file which has been changed from HEAD -> commit   
        return: two non-empty lists of tuples indicating start and end of line
        changes in source and dest files respectively
  """
   srcs = []
   dsts = []
   result = subprocess.run(["git", "diff", curr_commit, next_commit, "--", fname], stdout=subprocess.PIPE)
   
   # Get the line change info lines
   lines = result.stdout.decode("utf-8").split("\n")
   # IPython.embed()
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
          elif src.isdigit():
             start = int(src)
             end = start
          else:
              start = 0
              end = 0
          return (start, end)

      src = get_hunk(toks[1][1:])
      dst = get_hunk(toks[2][1:])
 
      srcs.append(src)
      dsts.append(dst)
   
   assert len(srcs) > 0
   assert len(dsts) > 0
   return srcs, dsts

def get_files_changed(curr_commit, next_commit):
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
    result = subprocess.run(["git", "diff", curr_commit, next_commit, "--name-status"], stdout=subprocess.PIPE)
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

def update_unmodified_bug(bug, srcs, dsts):
    """
        Given a bug, the method will find the bug in its specified file
        and update its locs to the nearest found match. If no match,
        throws an assertion error.
    """
    assert srcs[0][0] == dsts[0][0]
    old_loc = bug.locs[0]

    # Find the first source location > bug loc
    # i.e the nearest changed hunk preceding this bug
    end = -1
    for s in srcs:
        if s[0] > old_loc:
            break
        end += 1
    
    # Bug occurred before changes, so it's loc didn't change
    if(end < 0):
        return

    delta = dsts[end][1] - srcs[end][1]
    new_loc = old_loc + delta
    bug.locs = (new_loc, new_loc)


def _update_unmodified_bug(bug):
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
        #list as bug lost for now
        print("bug lost...")
        bug_loc = "lost"
        return
        #IPython.embed()
    assert len(matches) > 0, "error: bug lost"
    bug_loc = matches[0]

    # find the nearest match to the orig line of code
    if len(matches) > 1:
        diffs = (lambda val, l: [abs(e - val) for e in l])(bug.locs[0], matches) 
        bug_loc = matches[diffs.index(min(diffs))]

    # Update bug line of code
    bug.locs = (bug_loc, bug_loc)

def quick_stats(er):
    bug_stats = {}
    for bug in er.bug_list:
        if bug.desc not in bug_stats:
            bug_stats[bug.desc] = {'count': 1, "resolved": 0, "lost": 0}
        else:
            bug_stats[bug.desc]['count'] += 1

    for i in range(len(er.bug_list)):
        bug_desc = er.bug_list[i].desc
        if er.resolved_vec[i] == -1:
            bug_stats[bug_desc]['lost'] += 1
        else:
            bug_stats[bug_desc]['resolved'] += 1

    commit_stats = {}
    for i in range(len(er.resolved_vec)):
        if er.resolved_vec[i] not in commit_stats:
            commit_stats[er.resolved_vec[i]] = 1
        else:
            commit_stats[er.resolved_vec[i]] += 1
    return bug_stats, commit_stats
    
def save_stats(commit, bug_stats, commit_stats, er, commit_list):
    data = [bug_stats, commit_stats, er, commit_list]

    filename = "report_stats_{}.bin".format(commit)
    pickle.dump(data, open("../breezy/bug_report_stats/"+filename, "wb"))
    print("Saved bug report to {}".format(filename))

def load_stats(commit):
    filename = "report_stats_{}.bin".format(commit)
    data = pickle.load(open("bug_report_stats/"+filename, "rb"))
    return data

if __name__ == '__main__':
    args = parser.parse_args()
    if args.load:
        data = load_stats(args.load)
        print(data)
        exit(0)

    if not os.path.exists(args.r):
        print("Error: {} is not a path to a valid git repo".format(args.r))
        exit(1)

    save_br = args.s is not None
    save_dir = args.s
    print(save_dir)
    if save_br and not os.path.isdir(os.path.abspath(save_dir)):
        print("Error: {} is not a valid directory".format(save_dir))
        exit(1)

    saved_bug_reports = [f for f in listdir(save_dir) if isfile(join(save_dir, f)) and ".txt" in f]
    bug_report_hashes = [f.split(".")[0].split("_")[-1] for f in saved_bug_reports]

    print(saved_bug_reports)
    print(bug_report_hashes)
    
    print("...Checking out repository...")
    os.chdir(args.r)
    repo = Repo(os.getcwd())
    repo.git.checkout(args.b)

    print("...Getting full commit hashes...")
    commits = [repo.head.commit.hexsha]
    saved_commits = [] #in order of oldest to newest
    for i, c in enumerate(repo.head.commit.iter_parents()):
        commits.append(c.hexsha)
        if c.hexsha[:5] in bug_report_hashes:
            saved_commits.append((i, c.hexsha, c.committed_date))

    print(saved_commits)

    saved_commits.reverse()
   
    print("number of bug reports", len(saved_commits))

    for i in range(len(saved_commits)):
        curr_br = BugReport(saved_commits[i][1], dir=args.r, save_dir=args.s) 

    curr_br = BugReport(saved_commits[0][1], dir=args.r, save_dir=args.s) 
    new_br = BugReport(saved_commits[1][1], dir=args.r, save_dir=args.s)

    bug_list = []
    bug_list_commit = curr_br.commit
    if "error" in curr_br.type_map:
        bug_list = curr_br.type_map["error"]  #specific to clang_firefox
    er = EventsReport(bug_list)

    start_time = time.time() 

    # print()
    # print("Running static analysis over time on {} starting bugs".format(len(bug_list)))
    # print("===========")
    
    # for i in range(1, len(saved_commits)):
    #     curr_commit = saved_commits[i-1][1]
    #     next_commit = saved_commits[i][1]
    #     print("Commit {} {}/{}".format(curr_commit, i + 1, len(saved_commits)))
        
    #     curr_br = BugReport(curr_commit, tool=args.tool, command=args.command, clean=args.clean, dir=args.r, save_dir=args.s) 
    #     new_br = BugReport(next_commit, tool=args.tool, command=args.command, clean=args.clean, dir=args.r, save_dir=args.s)
      
    #     f_changes = get_files_changed(saved_commits[i-1][1], saved_commits[i][1])
        
    #     ### Find new bugs ###
    #     new_bugs = []
    #     for f_change in f_changes:
    #         change = f_changes[f_change][0]
            
    #         # A file added with bugs in it has new bugs
    #         if change == "A":
    #             if f_change in new_br.file_map:
    #                 new_bugs += new_br.file_map[f_change]

    #         if change == "M":
    #             # A file which previously had no bugs but now has bugs in it has new bugs
    #             if f_change in new_br.file_map:
    #                 if f_change not in curr_br.file_map:
    #                     new_bugs += new_br.file_map[f_change]

    #                 else:
    #                     curr_br_bugs = curr_br.file_map[f_change]
    #                     curr_hashes = [hash(c) for c in curr_br_bugs]
    #                     new_br_bugs = new_br.file_map[f_change]
    #                     next_hashes = [hash(n) for n in new_br_bugs]

    #                     for idx, n in enumerate(next_hashes):
    #                         if n not in curr_hashes:
    #                             new_bugs.append(new_br_bugs[idx])

    #     ### Check for resolved bugs ###
    #     for idx, bug in enumerate(bug_list):
    #         # print("Working on bug:", idx, "/", len(bug_list))
    #         # Ignore bug if it has been resolved
    #         if er.resolved_vec[idx] != -1:
    #             continue

    #         if bug.fname not in f_changes:
    #             continue

    #         change = f_changes[bug.fname][0]
    #         if change == "R":
    #             bug.fname = f_changes[bug.fname][1]

    #         if change == "M":
    #             srcs, dsts = get_lines_modified(saved_commits[i-1][1], saved_commits[i][1], bug.fname)
               
    #             # Check if the bug was changed at all in this file. 
    #             did_bug_ever_change = False
    #             for j in range(len(srcs)):
    #                 s = srcs[j]
    #                 bug_changed = s[0] <= bug.locs[0] <= s[1]
    #                 bug_changed = s[0] <= bug.locs[1] <= s[1] and bug_changed

    #                 if bug_changed:
    #                     # print("Bug changed")
    #                     did_bug_ever_change = True

    #                     # rerun bug checker on specific file and compare 
    #                     # before and after bug reports
    #                     d = dsts[j]
    #                     resolved = check_if_bug_resolved(bug, new_br, d)
    #                     er.update_resolved(idx, saved_commits[i][0], resolved)

    #             # If the bug didn't change, find it in the changed file
    #             # and update its new line number.
    #             if not did_bug_ever_change:
    #                 # print("Bug didn't change")
    #                 # update_unmodified_bug(bug)
    #                 update_unmodified_bug(bug, srcs, dsts)
    #                 # print("-----------")
        
    #     # Add new bugs found in next commit to bug list
    #     print("New bugs: {}".format(len(new_bugs)))
    #     bug_list += new_bugs
    #     er.resolved_vec += [-1 for _ in range(len(new_bugs))]
    #     print("===========") 
    # bug_stats, commit_stats = quick_stats(er)
    # save_stats(bug_list_commit, bug_stats, commit_stats, er, commits)
    
    print("Wall time: {}".format(str(timedelta(seconds=time.time() - start_time)))) 
    
    res_commits = []
    for i,c,d in list(set(saved_commits)):
        curr_br = BugReport(c, tool=args.tool, command=args.command, clean=args.clean, dir=args.r, save_dir=args.s)
        res_commits.append((c, len(curr_br.bugs), d))

    res_commits = sorted(res_commits, key=lambda x: x[2])
    res_commits = [(c,l,datetime.datetime.fromtimestamp(d).strftime('%c')) for c,l,d in res_commits]
    for x in res_commits:
        print(x)
    print("Wall time: {}".format(str(timedelta(seconds=time.time() - start_time)))) 

        

