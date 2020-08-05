from git import Repo
import os
import format_clang
from bug_report import Bug, BugReport
import sys
sys.setrecursionlimit(100000)


def get_repo_commits(repo):
    print("...getting commits...")
    commits = [repo.head.commit.hexsha]
    for i, c in enumerate(repo.head.commit.iter_parents()):
        commits.append(c.hexsha)

    #get set of commits in reverse order
    commits.reverse()
    return commits

if __name__ == '__main__':
    os.chdir("../../gecko-dev")
    repo = Repo(os.getcwd())
    repo.git.checkout('master')

    commits = get_repo_commits(repo)
    os.chdir("../breezy")

    commits = commits[650000:]

    for commit_hash in os.listdir("clang_output"):
        if "2020" in commit_hash or commit_hash not in commits:
            print("not in commits:", commit_hash)
            continue
        print(commit_hash)

    for commit_hash in os.listdir("clang_output"):
        print(commit_hash)
        if "2020" in commit_hash or commit_hash not in commits:
            print("not in commits:", commit_hash)
            continue
        br = BugReport(commit_hash, tool="clang_firefox", save_dir="clang_save", command=None, clean=None, dir="gecko-dev", compile_bugs=True)
        list_of_bugs = format_clang.format("clang_output/"+commit_hash+"/"+os.listdir("clang_output/"+commit_hash)[0])
        print("Number of bugs found: ", len(list_of_bugs))
        for caught_bug in list_of_bugs:
            lineno = caught_bug['line']
            bug = Bug(caught_bug['file'], 
                    caught_bug['desc'], 
                    caught_bug['code'], 
                    caught_bug['group'], 
                    caught_bug['type'],
                    (int(lineno), int(lineno)), 
                    commit_hash)
            br.bugs.append(bug)
            
            if caught_bug['group'] not in br.type_map:
               br.type_map[caught_bug['group']] = []
            br.type_map[caught_bug['group']].append(bug)

            fname = caught_bug['file']
            if fname not in br.file_map:
                br.file_map[fname] = []
            br.file_map[fname].append(bug)
        
        #pickle bug report 
        print("saving pickle")
        br.save()


