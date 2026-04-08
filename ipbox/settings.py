azure_pat = ""
git_authors = [x.lower() for x in ["dominik.baran@XXX", "Dominik Baran"]]
author = 'dominik.baran@XXX'
excel_path="Ewidencja_projektowa_2023.xlsx"
year = 2023
from_month = 1
to_month = 12

heuristics_pr_filter_enabled = True # True speeds up script but might ommit PR with your commits but created by someone else
projects = ["TTT"]
tasks_only = False # if True, skips PR/commit scanning and only fetches work items assigned to you
org_url = 'https://dev.azure.com/guestlinelabs'
