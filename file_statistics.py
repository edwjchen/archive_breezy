from git import Repo
import argparse
import glob
import shutil
import os
import subprocess
import IPython
import pickle
import copy
import time
import mplcursors
import datetime
from datetime import timedelta
import matplotlib.pyplot as plt

import sys
sys.setrecursionlimit(100000)

parser = argparse.ArgumentParser(description="...")
parser.add_argument('-r', required=True, help="Path to repository")
parser.add_argument('-b', default='master', help="Branch to examine")
parser.add_argument('-get', default='True', help="Get file statistcs")
parser.add_argument('-start', default=0, help="Starting commit")
parser.add_argument('-end', default=10000, help="Starting commit")
parser.add_argument('-step', default=1, help="Step size to iterate through commits")
parser.add_argument('-gran', default='overall', help="Granularity of file statistics to get")


file_stats = []

def get_repo_commits(repo):
    """
        Given a repository, returns a list of commit hashes.

        repo: The path to the target repository
        return: List of commit hashes (strings)
    """
    #commits = [c.hexsha list(repo.iter_commits(reverse=True))]

    commits = [repo.head.commit]
    curr_commit = repo.head.commit
    while len(curr_commit.parents) > 0:
        commits.append(curr_commit.parents[0])
        curr_commit = curr_commit.parents[0]
    commits.reverse()
    return commits

def get_repo_commit_times(repo, commits):
    """
        Given a repository, returns a map of commit hashes to 
        datetime.

        repo: The path to the target repository
        return: Map of commit hashes to datetime (strings)
    """
    mapping = {}
    for i, c in enumerate(commits):
        mapping[c.hexsha] = datetime.datetime.fromtimestamp(c.committed_date).strftime('%c')

    return mapping

def get_repo_commit_messages(repo, commits):
    """
        Given a repository, returns a map of commit hashes to 
        commit messages.

        repo: The path to the target repository
        return: Map of commit hashes to commit messages (strings)
    """
    maessages = {}
    for i, c in enumerate(commits):
        maessages[c.hexsha] = c.message

    return maessages

def get_lines_changed_between_commits(repo, curr_commit, next_commit):
    """
        Given a repository, returns a list of commit hashes.

        repo: The path to the target repository
        return: List of commit hashes (strings)
    """

    global file_stats
    print("commit hash", next_commit)
    result = subprocess.run(["git", "diff", curr_commit, next_commit, "--shortstat"], stdout=subprocess.PIPE)
    line_change_stats = result.stdout.decode("utf-8").split("\n")[:-1]
    if not line_change_stats:
        line_change_stats = ['0 file changed', '0 insertions(+)', '0 deletions(-)']
    file_stats += [(curr_commit, next_commit)] + line_change_stats

def get_per_directory_statistics(repo, curr_commit, next_commit, mapping, messages):
    global file_stats
    print("commit hash", next_commit)
    result = subprocess.run(["git", "diff", "--numstat", curr_commit, next_commit], stdout=subprocess.PIPE)
    dir_change_stats = [x.split("\t") for x in result.stdout.decode("utf-8").split("\n")[:-1]]
    file_stats += [(curr_commit, mapping[curr_commit], messages[curr_commit], next_commit, mapping[next_commit], messages[next_commit])] + [dir_change_stats]

def get_file_statistics():
    global file_stats
    args = parser.parse_args()
    if not os.path.exists(args.r):
        print("Error: {} is not a path to a valid git repo".format(args.r))
        exit(1)

    os.chdir(args.r)
    repo = Repo(os.getcwd())
    print("...checking out repository...")
    repo.git.checkout(args.b)

    commits = get_repo_commits(repo)
    mapping = get_repo_commit_times(repo, commits)
    messages = get_repo_commit_messages(repo, commits)
    commits = [c.hexsha for c in commits]

    inc = int(args.step)
    start = max(0, int(args.start))
    end = int(args.end)
    gran = args.gran

    count = 0 
    for i in range(start+inc, len(commits), inc):
        if count > end:
            break
        count += 1
        if gran == 'overall':
            get_lines_changed_between_commits(repo, commits[i-inc], commits[i])
        else:
            get_per_directory_statistics(repo, commits[i-inc], commits[i], mapping, messages)

    os.chdir("../breezy")

    path = os.path.join("file_stats", "{}_stats_{}_{}_{}_{}.bin".format(gran, start, start+end, inc ,args.r.split("/")[-2]))    
    with open(path, "wb") as f:
        pickle.dump(file_stats, f)
    print("Saved bug report to {}_stats_{}_{}_{}_{}.bin".format(gran, start, start+end, inc ,args.r.split("/")[-2]))

def display_overall_statistics(data):
    # plot number of insertions over time
    all_data = []
    for i in range(0, len(data), 2):
        file_statistics = [d.strip() for d in data[i+1].split(",")]
        num_files_changed = 0
        num_insertions = 0
        num_deletions = 0
        for x in file_statistics:
            if 'changed' in x:
                num_files_changed = int(x.split()[0])
            elif 'insert' in x: 
                num_insertions = int(x.split()[0])
            elif 'del' in x:
                num_deletions = int(x.split()[0])
        all_data.append([data[i]]+[num_files_changed, num_insertions, num_deletions])
    
    file_changed_data = [d[1] for d in all_data]

    f, ax = plt.subplots()
    ax.plot(range(len(file_changed_data)), file_changed_data)
    plt.xlabel('Commit #x 100000')
    plt.ylabel('Number of files changed/renamed')
    plt.show()

    lines_inserted_data = [d[2] for d in all_data]
    f, ax = plt.subplots()
    ax.plot(range(len(lines_inserted_data)), lines_inserted_data)
    plt.xlabel('Commit #x 100000')
    plt.ylabel('Number of lines inserted')
    plt.show()

    lines_deleted_data = [d[3] for d in all_data]
    f, ax = plt.subplots()
    ax.plot(range(len(lines_deleted_data)), lines_deleted_data)
    plt.xlabel('Commit #x 100000')
    plt.ylabel('Number of lines deleted')
    plt.show()


def display_per_file_statistics(data, start, step):
    all_files = {}
    for i in range(1, len(data), 2):
        files = data[i]
        for f in files:
            if f[0] == "-" or f[1] == "-":
                continue

            if f[2] not in all_files and "=>" not in f[2]:
                all_files[f[2]] = [(0,0)] * (len(data)//2)
            
            if f[2] in all_files:
                all_files[f[2]][i//2] = (int(f[0]), int(f[1]))

    #display insertion data over time
    commit_index = range(start, start+(len(data)//2 * step), step)
    commits = [data[i][3] for i in range(0, len(data), 2)]
    date_times = [data[i][4] for i in range(0, len(data), 2)]
    messages = [data[i][5] for i in range(0, len(data), 2)]


    fig, ax = plt.subplots()
    pts = []
    labels = []
    for k, v in all_files.items():
        values = [float('nan') if int(x[0])==0 else int(x[0]) for x in v]
        curr_pts = ax.scatter(commit_index, values)
        pts.append(curr_pts)
        labels.append(["Commit: "+c+"\nLabel: "+k+"\nTime: "+str(d) for c,d in zip(commits,date_times)])

    d = dict(zip(pts, labels))
    
    mplcursors.cursor(ax, hover=True).connect(
        "add", lambda sel: sel.annotation.set_text(d[sel.artist][sel.target.index]))
    plt.grid(True)
    plt.title("File changes over time")
    plt.xlabel("Commit number")
    plt.ylabel("Number of Insertions")
    plt.show()

    #display deletion data over time
    fig, ax = plt.subplots()
    pts = []
    labels = []
    for k, v in all_files.items():
        values = [float('nan') if int(x[1])==0 else int(x[1]) for x in v]
        curr_pts = ax.scatter(commit_index, values)
        pts.append(curr_pts)
        labels.append(["Commit: "+c+"\nLabel: "+k+"\nTime: "+str(d) for c,d in zip(commits,date_times)])

    d = dict(zip(pts, labels))
    
    mplcursors.cursor(ax, hover=True).connect(
        "add", lambda sel: sel.annotation.set_text(d[sel.artist][sel.target.index]))
    plt.grid(True)
    plt.title("File changes over time")
    plt.xlabel("Commit number")
    plt.ylabel("Number of Deletions")
    plt.show()


def display_per_dir_statistics(data, start, step):
    all_files = {}

    for i in range(1, len(data), 2):
        files = data[i]
        for f in files:
            if f[0] == "-" or f[1] == "-":
                continue

            top_level_dir = f[2].split('/')[0]
            if top_level_dir not in all_files and "=>" not in f[2]:
                all_files[top_level_dir] = [[0,0]] * (len(data)//2)
            
            if top_level_dir in all_files:
                commit_data = copy.deepcopy(all_files[top_level_dir][i//2])
                commit_data[0] += int(f[0])
                commit_data[1] += int(f[1])
                all_files[top_level_dir][i//2] = commit_data

    #display insertion data over time
    commit_index = range(start, start+(len(data)//2 * step), step)
    commits = [data[i][3] for i in range(0, len(data), 2)]
    prev_commits = [data[i][0] for i in range(0, len(data), 2)]
    date_times = [data[i][4] for i in range(0, len(data), 2)]
    messages = [data[i][5] for i in range(0, len(data), 2)]

    fig, ax = plt.subplots()
    pts = []
    labels = []
    for k, v in all_files.items():
        values = [float('nan') if int(x[0])==0 else int(x[0]) for x in v]
        curr_pts = ax.scatter(commit_index, values)
        pts.append(curr_pts)
        labels.append(["Commit: "+c+"\nPrev Commit: "+p+"\nLabel: "+k+"\nTime: "+str(d)+"\nMsg: "+str(m) for p,c,d,m in zip(prev_commits,commits,date_times,messages)])

    d = dict(zip(pts, labels))
    
    mplcursors.cursor(ax, hover=True).connect(
        "add", lambda sel: sel.annotation.set_text(d[sel.artist][sel.target.index]))
    plt.grid(True)
    plt.title("Directory changes over time")
    plt.xlabel("Commit number")
    plt.ylabel("Number of Insertions")
    plt.show()

    #display deletion data over time
    fig, ax = plt.subplots()
    pts = []
    labels = []
    for k, v in all_files.items():
        values = [float('nan') if int(x[1])==0 else int(x[1]) for x in v]
        curr_pts = ax.scatter(commit_index, values)
        pts.append(curr_pts)
        labels.append(["Commit: "+c+"\nPrev Commit: "+p+"\nLabel: "+k+"\nTime: "+str(d)+"\nMsg: "+str(m) for p,c,d,m in zip(prev_commits,commits,date_times,messages)])

    d = dict(zip(pts, labels))
    
    mplcursors.cursor(ax, hover=True).connect(
        "add", lambda sel: sel.annotation.set_text(d[sel.artist][sel.target.index]))
    plt.grid(True)
    plt.title("Directory changes over time")
    plt.xlabel("Commit number")
    plt.ylabel("Number of Deletions")
    plt.show()


if __name__ == '__main__':
    args = parser.parse_args()
    if args.get == 'True':
        start_time = time.time()
        get_file_statistics()
        print("Wall time: {}".format(str(timedelta(seconds=time.time() - start_time)))) 

    else:
        inc = int(args.step)
        start = int(args.start)
        end = int(args.end)
        gran = args.gran
        path = os.path.join("file_stats", "{}_stats_{}_{}_{}_{}.bin".format(gran, start, start+end, inc ,args.r.split("/")[-2]))    
        print(path)
        f = open(path, "rb")
        try:
            data = pickle.load(f)
        finally:
            f.close()

        if gran == 'overall':
            display_overall_statistics(data)
        elif gran == 'file':
            display_per_file_statistics(data, start, inc)
        elif gran == 'dir':
            display_per_dir_statistics(data, start, inc)
        else:
            print("-gran not recognized: {}".format(gran))



