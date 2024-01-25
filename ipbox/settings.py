azure_pat = ""
git_authors = [x.lower() for x in ["dominik.baran@guestline.com", "domino.baran@gmail.com", "dominik.baran7@gmail.com", "Dominik Baran"]]
author = 'dominik.baran@guestline.com'
excel_path="Ewidencja_projektowa_2023.xlsx"
year = 2023
from_month = 1
to_month = 12

heuristics_pr_filter_enabled = True # True speeds up script but might ommit PR with your commits but created by someone else
projects = ["Rezlynx", "Search", "Sugoi", "Mandalore"]
org_url = 'https://dev.azure.com/guestlinelabs'