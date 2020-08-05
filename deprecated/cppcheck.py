import subprocess
import os
import xml.etree.ElementTree as ET
from git import Repo

class CPPCheck:
    def __init__(self, dir_name):
        self.dir_name = dir_name
        os.chdir(dir_name)
        # Check for the existance of a <dir_name>-cppcheck-build-dir
        build_dir = os.path.basename(dir_name) + "-cppcheck-build-dir"
        # Create one if does not already exist
        if not os.path.exists(build_dir):
            os.mkdir(build_dir)
        self.options = {'--cppcheck-build-dir=': build_dir,
                        '--enable=': 'all',
                        '--xml' : ''}
    def add_option(self, option, argument):
        self.options[option] = argument
    
    def run(self, file_name):
        with open("cppcheck_output.xml", "w") as f:
            option_list = [key + value for key, value in self.options.items()]
            print(option_list)
            result = subprocess.run(["cppcheck"] + option_list + [file_name], stderr=f)
            # This means cppcheck failed
            if result.returncode == 1:
                return False
        return True

    def find_start(self, repo, error_id, file_name, commits):
        """
            error_id: CPPCheck error ID 
            fname: File name of bug where it was found
            Return the commit hash where the bug is thought to have started
        """
        start = 0
        end = len(commits)
        mid = start
        while start <= end:
            mid = (start + end) // 2
            print(mid)
            # Check the middle commit for the bug
            repo.git.checkout(commits[mid])

            # If cannot find the file in question, go an more recent time (lower index)
            if not os.path.exists(file_name):
                end = mid - 1
                continue

            # Compare the file at the current commit with master
            # TODO Change from master to HEAD of whatever branch we are comparing with
            result = subprocess.run(["git", "diff", "master", commits[mid], "--name-status", "--", file_name], stdout=subprocess.PIPE)
            # Go to later time if no change was made
            if not result.stdout:
                start = mid + 1
                continue

            # TODO Need to handle renaming cases

            # Run the checker on this commit
            self.run(file_name)
            root = ET.parse("cppcheck_output.xml").getroot()
            errors = root.findall(f"./errors/*[@id='{error_id}']")
            # If bug still found, jump backwards
            if errors:
                start = mid + 1
            # If bug not found, jump forwards
            else:
                end = mid - 1
        return commits[mid]