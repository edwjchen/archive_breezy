import json

def format(run_dir):
    f = open(run_dir+"/infer-out/report.json")
    report = json.load(f)

    #dict_keys(['bug_type', 'qualifier', 'severity', 'line', 'column', 'procedure', 'procedure_start_line', 'file', 'bug_trace', 'key', 'hash', 'bug_type_hum', 'access'])
    output_data = []
    for bug in report:
        new_bug = {}
        new_bug['bug_type'] = bug['bug_type']
        new_bug['severity'] = bug['severity']
        new_bug['qualifier'] = bug['qualifier']
        new_bug['line'] = bug['line']
        new_bug['procedure'] = bug['procedure']
        new_bug['file'] = bug['file']
        output_dataa = output_data.append(new_bug)
    f.close()

    f = open(run_dir+"/infer-out/bugs.txt", 'r')
    lines = f.readlines()

    #split list by new lines
    size = len(lines)
    idx_list = [idx for idx, val in enumerate(lines) if val == "\n"]
    bug_report = [lines[i: j] for i, j in
            zip([0] + idx_list, idx_list + 
            ([size] if idx_list[-1] != size else []))] 
    f.close()

    #remove header and footer
    bug_report = bug_report[1:len(bug_report)-2]
    for i, bug_data in enumerate(bug_report):
        #get only lines that start with a number
        #remove header == first 5 characters of string
        data = [d.strip()[6:] for d in bug_data if d.strip() != "" and d.strip()[0].isnumeric()]
        bug_text = '\n'.join(data)

        #add to output_data
        output_data[i]['code'] = bug_text


    # print(output_data[0])
    return output_data