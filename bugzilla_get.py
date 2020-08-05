import requests
import json
import os
import pprint

r = requests.get('https://bugzilla.mozilla.org/rest/bug', params={'id': '712350', 'api_key': os.environ['BUGZILLA_API_KEY']})
list_of_bugs = r.json()['bugs']
bug_ids_clang = list_of_bugs[0]['depends_on']

clang_bugs = {}

for bug_id in bug_ids_clang:
    print(bug_id)
    r = requests.get('https://bugzilla.mozilla.org/rest/bug', params={'id': bug_id, 'api_key': os.environ['BUGZILLA_API_KEY']})
    if r.json()['bugs']:
        bug = r.json()['bugs'][0]
        bug_info = {}
        bug_info['product'] = bug['product']
        bug_info['summary'] = bug['summary']
        bug_info['severity'] = bug['severity']
        bug_info['status'] = bug['status']
        bug_info['type'] = bug['type']
        bug_info['priority'] = bug['priority']
        bug_info['component'] = bug['component']
        clang_bugs[bug_id] = bug_info
    else:
        print("====================================\nNo Bug Found, id: {}\n====================================".format(bug_id))
    
print(clang_bugs)

exit(0)




start = 1638675
pp = pprint.PrettyPrinter(indent=4)
for i in range(5):
    bug_id = str(start - i)
    r = requests.get('https://bugzilla.mozilla.org/rest/bug', params={'id': bug_id, 'api_key': os.environ['BUGZILLA_API_KEY']})
    list_of_bugs = r.json()['bugs']
    if list_of_bugs:
        pp.pprint(list_of_bugs[0])
    print()

