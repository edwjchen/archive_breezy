from bs4 import BeautifulSoup, Comment, SoupStrainer
import codecs

def parse_index(direct):
    bugs = []
    file = codecs.open(direct+"/index.html", 'r')

    soup = BeautifulSoup(file.read(), 'html5lib')
    for row in soup.findAll('table')[2].tbody.findAll('tr'):
        bug = {}
        bug["group"] = row.findAll('td')[0].contents[0]
        bug["type"] = row.findAll('td')[1].contents[0]
        bug["file"] = row.findAll('td')[2].contents[0]
        bug["function"] = row.findAll('td')[3].contents[0]
        bug["line"] = row.findAll('td')[4].contents[0]
        bug["desc"] = row.findAll('td')[6].contents[0]
        bug["code"] = "ree"
        bugs.append(bug)
    
    idx = 0
    for comments in soup.findAll(string=lambda text: isinstance(text, Comment)):
        if "id" in comments.extract():
            bugs[idx]['bug_report'] = comments.extract().split('"')[1]
            idx += 1
    return bugs

def parse_bug_reports(bugs, direct):
    for bug in bugs:
        report_name = bug['bug_report']
        file = codecs.open(direct+"/"+report_name, 'r')
        try:
            html = file.read()
        except UnicodeDecodeError:
            print(UnicodeDecodeError)
            bug['code'] = "Could not parse from HTML"
            print(bug)
            continue
        except:
            print("something went wrong")
            bug['code'] = "Could not parse from HTML"
            print(bug)
            continue
        file.close()
        html = str(html.replace("</td></td>", "</td>"))
        
        product = SoupStrainer('table',{'class': 'code'})
        soup = BeautifulSoup(html,'html5lib', parse_only=product)
        lines_of_code = ["index0"]
        file_names = []

        print(bug['bug_report'])

        for fn in soup.findAll('h4', {'class':'FileName'}):
            file_names.append("/".join(fn.get_text().split("/")[4:]))
    
        code_blocks = soup.findAll('table', {'class':'code'})
        for i, f in enumerate(code_blocks):
            table_rows = f.findAll('tr')

            for row in range(1, len(table_rows)):
                if 'LN'+bug['line'] in str(table_rows[row-1]) and 'class="msg' in str(table_rows[row]):
                    bug['code'] = " ".join(table_rows[row-1].get_text().split()[1:])
                    if file_names:
                        bug['file'] = file_names[i]

        if 'code' not in bug:
            print(bug['bug_report'])
            print("**************could not parse from HTML******************")
            print()
            bug['code'] = "Could not parse from HTML"

        print(bug['file'])
        print(bug['type'])
        print(bug['code'])
        print()

    return bugs

def format(direct):
    bugs = parse_index(direct)
    return parse_bug_reports(bugs, direct)

if __name__ == '__main__':
    output = format('../clang_output/2020-06-11-045140-5136-1')
    print(output)
