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