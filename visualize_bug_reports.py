from analyze_bug_reports import load_stats
import matplotlib.pyplot as plt 
import numpy as np
import os
from git import Repo
import datetime

def data_to_avg_time(data):
    er= data[2]
    severity = [b.severity for b in er.bug_list]
    commits_taken = er.resolved_vec
    all_bugs = zip(severity, commits_taken)
    severity_time_taken = {}
    for b in all_bugs:
        if b[1] != -1:
            if b[0] not in severity_time_taken:
                severity_time_taken[b[0]] = []
            severity_time_taken[b[0]].append(b[1])

    avg_time_taken = {}
    for sev, l in severity_time_taken.items():
        avg_time_taken[sev] = sum(l)/len(l)
    return avg_time_taken

def save_graph(title, save_to, data):
    plt.clf()
    plt.rcdefaults()

    plt.style.use('ggplot')

    x = data.keys()
    energy = list(data.values())

    x_pos = [i for i, _ in enumerate(x)]

    plt.bar(x_pos, energy, color='green')
    plt.xlabel("Bug Type")
    plt.ylabel("Average Number of Commits to Resolve")
    plt.title(title)
    plt.tight_layout()
    plt.xticks(x_pos, x)
    plt.xticks(rotation=90)
    plt.savefig(save_to,  bbox_inches='tight')


def visualize_bug_types(data, title):
    er = data[2]
    bug_list = er.bug_list
    type_map = {}
    for bug in bug_list:
        if bug.severity not in type_map:
            type_map[bug.severity] = 1
        else:   
            type_map[bug.severity] += 1
    
    labels = []
    bug_type_ratio = []
    for k, v in type_map.items():
        labels.append(k)
        bug_type_ratio.append(v/len(bug_list))

    fig, ax = plt.subplots()
    
    wedges, texts = ax.pie(bug_type_ratio, wedgeprops=dict(width=0.5), startangle=-40)

    bbox_props = dict(boxstyle="square,pad=0.3", fc="w", ec="k", lw=0.72)
    kw = dict(arrowprops=dict(arrowstyle="-"),
            bbox=bbox_props, zorder=0, va="center")

    for i, p in enumerate(wedges):
        ang = (p.theta2 - p.theta1)/2. + p.theta1
        y = np.sin(np.deg2rad(ang))
        x = np.cos(np.deg2rad(ang))
        horizontalalignment = {-1: "right", 1: "left"}[int(np.sign(x))]
        connectionstyle = "angle,angleA=0,angleB={}".format(ang)
        kw["arrowprops"].update({"connectionstyle": connectionstyle})
        ax.annotate(labels[i], xy=(x, y), xytext=(1.35*np.sign(x), 1.4*y),
                    horizontalalignment=horizontalalignment, **kw)
    
    ax.legend(wedges, labels,
        title="Bug Types",
        loc="center left",
        bbox_to_anchor=(1, 0, 0.5, 1))

    ax.set_title(title)
    plt.show()

def visualize_directory_distribution(data, title):
    er = data[2]
    bug_list = er.bug_list
    dirs = {}
    type_count = {}
    for bug in er.bug_list:
        top_dir = bug.fname.split('/')[0]
        bug_type = bug.severity
        key = top_dir
        if key in dirs:
            dirs[key] += 1
        else:
            dirs[key] = 0

        if bug_type in type_count:
            type_count[bug_type] += 1
        else:
            type_count[bug_type] = 0

    keys = []
    values = []
    for k,v in dirs.items():
        keys.append(k)
        values.append(v)
    plt.barh(keys,values)

    plt.xlabel("Number of bugs per directory")

    plt.title(title)
    plt.show()

    keys = []
    values = []
    for k,v in type_count.items():
        keys.append(k)
        values.append(v)
    plt.barh(keys,values)

    plt.xlabel("Number of bugs per directory")
    plt.title("(gecko-dev) Bug Type Distribution from Nov 2019 - May 2020")
    plt.show()

    for bug in er.bug_list:
        if "Use-after-free" in bug.severity:
            print(bug.fname)
            print(bug.code)
            print(bug.locs)
            print(bug.commit)
            print()

def visualize_commit_distribution(data, title):
    er = data[2]
    bug_list = er.bug_list

    res_commits = set()
    for bug in bug_list:
        res_commits.add(bug.commit)

    os.chdir("../gecko-dev")
    repo = Repo(os.getcwd())
    repo.git.checkout('master')

    def get_repo_commits(repo):
        print("...getting commits...")
        commits = []
        for i, c in enumerate(repo.head.commit.iter_parents()):
            if c.hexsha in res_commits:
                commits.append(c)

        #get set of commits in reverse order
        commits.reverse()
        return commits
    commits = get_repo_commits(repo)
    os.chdir("../breezy")

    commits = [[c, int(c.committed_date)] for c in commits]
    commits = sorted(commits, key=lambda x: x[1])
    commits = [[c[0], datetime.datetime.fromtimestamp(c[1]).strftime('%c')] for c in commits]
    print(commits)



def visualize_resolved_time(data, title):
    er = data[2]
    commits = data[3]
    commits.reverse()
    bug_list = er.bug_list
    type_map = {}
    start_index = []
    res_commits = set()
    for bug in bug_list:
        if bug.severity not in type_map:
            type_map[bug.severity] = []
        start_index.append(commits.index(bug.commit))
        res_commits.add(bug.commit)
    print(res_commits)

    for i in range(len(bug_list)):
        if er.resolved_vec[i] == -1:
            continue
        type_map[bug_list[i].severity].append((start_index[i], er.resolved_vec[i]))

    datas = []
    groups = []
    for k,v in type_map.items():
        datas.append(v)
        groups.append(k)

    fig, ax = plt.subplots()

    for data, group in zip(datas,groups):
        x = [d[0] for d in data]
        y = [d[1] for d in data]
        ax.scatter(x, y, alpha=0.8, edgecolors='none', label=group, s=30)
    
    ax.set_ylabel("Bug Commit - Time Taken to Resolve")
    ax.set_xlabel("Bug Commit Birthday")

    plt.title(title)
    plt.legend(loc=2)
    plt.show()

if __name__ == '__main__':    
    # data = load_stats('a966f41d5c34dec55814ef224261b87343281c0d') #firefox
    # xddata = load_stats('977a22a9c2c49a6c2dc48f23ec436bb74db658cc') #firefox
    # data.append(xddata[3])


    data = load_stats('1ba1fb1c93a07997dcef7498f0a077f2b730f938') #firefox

    # visualize_commit_distribution(data, "")

    visualize_directory_distribution(data, "(gecko-dev) Bugs Caught per Directory from Nov 2019 - May 2020")

    # visualize_bug_types(data, "Firefox Clang Bug Distribution")
    # visualize_resolved_time(data, 'Firefox Clang Bug Resolution')

        
    # microsoft_data = load_stats('ac14e2df10de731024e8f4a3c61c73350bdfdfe1')
    # firefox_data = load_stats('a966f41d5c34dec55814ef224261b87343281c0d') 
    # data = load_stats('d98c4efbd73be8dc7022225df8c2ed62ac944662') #react-native-windows

    # firefox_avg_time = data_to_avg_time(firefox_data)
    # save_graph("Average Commits to Resolve - Firefox Clang",'firefox_avg_num_commits.png', firefox_avg_time)

