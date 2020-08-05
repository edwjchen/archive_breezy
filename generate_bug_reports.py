from git import Repo
import argparse
import os
from utility.bug_report import Bug, BugReport
from datetime import timedelta
import time

parser = argparse.ArgumentParser(description="This program generates intermediary bug reports to be later analyzed.")
parser.add_argument('-r', required=True, help="Path to repository")
parser.add_argument('-b', default='master', help="Branch to examine")
parser.add_argument('-d', default=5, help="Depth of commits to generate bug reports starting at HEAD")
parser.add_argument('-s', default=None, help="Directory to save intermediary bug reports to")
parser.add_argument('-step', default=1, help="Number of commits to step by")
parser.add_argument('-tool', default='cppcheck', help="Static analysis tool to run")
parser.add_argument('-command', default='make', help="Command to compile build")
parser.add_argument('-clean', default='make clean', help="Command to clean build")

if __name__ == '__main__':
    args = parser.parse_args()
    if not os.path.exists(args.r):
        print("Error: {} is not a path to a valid git repo".format(args.r))
        exit(1)

    save_br = args.s is not None
    save_dir = args.s
    if save_br and not os.path.isdir(os.path.abspath(save_dir)):
        print("Error: {} is not a valid directory".format(save_dir))
        exit(1)
    
    os.chdir(args.r)
    repo = Repo(os.getcwd())
    repo.git.checkout(args.b)

    commits = [repo.head.commit.hexsha]
    for c in repo.head.commit.iter_parents():
        commits.append(c.hexsha)
    # Get the bug report for the starting commit
    start = int(args.d)
    step = min(-1*int(args.step), int(args.step))
    start_time = time.time()
    for i in range(start, 0, step):
        repo.git.checkout(commits[i])
        print("Generating Bug Reports for Commit {} {}/{}".format(commits[i][:5], start - i + 1, start))
        
        br = BugReport(commits[i], tool=args.tool, 
            command=args.command, clean=args.clean, dir=args.r, save_dir=save_dir)
        print("===========")
    print("Done!")
    print("{} bug reports generated for commits {} through {}, saved to {}".format(start, commits[start][:5], commits[0][:5], args.s))
    print("Wall time: {}".format(str(timedelta(seconds=time.time() - start_time)))) 
