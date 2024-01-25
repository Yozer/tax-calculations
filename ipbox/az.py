from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication
from azure.devops.v6_0.work_item_tracking.models import TeamContext, Wiql, WorkItem, WorkItemBatchGetRequest
from azure.devops.v6_0.work_item_tracking.work_item_tracking_client import WorkItemTrackingClient
from azure.devops.v6_0.git.models import GitPullRequest, GitPullRequestSearchCriteria, GitRepository, ResourceRef
from azure.devops.v6_0.git.git_client import GitClient
from azure.devops.v6_0.core.core_client import CoreClient
from azure.devops.exceptions import AzureDevOpsServiceError
from typing import Iterator, List
import dateutil.parser
from settings import azure_pat, git_authors, org_url, heuristics_pr_filter_enabled, author

limit = 100
closed_date_field = "Microsoft.VSTS.Common.ClosedDate"
credentials = BasicAuthentication('', azure_pat)
connection = Connection(base_url=org_url, creds=credentials)
core_client: CoreClient = connection.clients_v6_0.get_core_client()
git_client: GitClient = connection.clients_v6_0.get_git_client()
work_client: WorkItemTrackingClient = connection.clients_v6_0.get_work_item_tracking_client()

def get_my_prs_from_repos(start_date, end_date, project):
    for repo in git_client.get_repositories(project):
        yield from get_my_prs_from_repo(repo, start_date, end_date)


def get_my_prs_from_repo(repo: GitRepository, start_date, end_date):
    params = GitPullRequestSearchCriteria(status="Completed", target_ref_name=repo.default_branch, include_links=True)
    skip = 0
    # print(f"Scanning repository: {repo.name}")
    if 'isDisabled' in repo.additional_properties and repo.additional_properties['isDisabled'] == True:
        return 

    try:
        while True:
            
            prs: List[GitPullRequest] = git_client.get_pull_requests(repo.id, params, top=limit, skip=skip)
            if len(prs) == 0:
                break

            if heuristics_pr_filter_enabled:
                probably_my_prs = [pr for pr in prs if any(reviewer.unique_name.lower() in git_authors for reviewer in pr.reviewers) or pr.created_by.unique_name.lower() in git_authors]
            else:
                probably_my_prs = prs
            probably_my_prs = [pr for pr in prs if pr.closed_date >= start_date and pr.closed_date <= end_date]
            for pr in probably_my_prs:
                pr.commits = [c for c in git_client.get_pull_request_commits(repo.id, pr.pull_request_id) if c.committer.email.lower() in git_authors or c.author.email.lower() in git_authors or c.committer.name.lower() in git_authors or c.author.name.lower() in git_authors]
                if len(pr.commits) > 0:
                    pr.work_item_refs = [int(w.id) for w in git_client.get_pull_request_work_item_refs(repo.id, pr.pull_request_id)]
                    pr.repo = repo.name
                    yield pr
                    # break #tmp

            if len(prs) < limit:
                break
            skip += len(prs)
    except AzureDevOpsServiceError as x:
        print(f"failed to process repo {x.message}")
        raise

def get_work_items_batch(ids: List[str], end_date) -> Iterator[WorkItem]:
    def chunks(lst, n=200):
        for i in range(0, len(lst), n):
            yield lst[i:i + n]

    missing_parents = []
    def cleanup_work(work):
        if closed_date_field in work.fields:
            work.fields[closed_date_field] = dateutil.parser.isoparse(work.fields[closed_date_field])
        if "System.Description" not in work.fields:
            work.fields["System.Description"] = work.fields["Microsoft.VSTS.TCM.ReproSteps"] if "Microsoft.VSTS.TCM.ReproSteps" in work.fields else ""
        if closed_date_field not in work.fields:
            work.fields[closed_date_field] = end_date

    for chunk in chunks(ids):
        request = WorkItemBatchGetRequest(error_policy="fail", ids=chunk, fields=["System.Id", "System.Title", "System.WorkItemType", "System.Description", "Microsoft.VSTS.TCM.ReproSteps", "System.Parent", "System.State", closed_date_field])
        for work in work_client.get_work_items_batch(request):
            if work.fields["System.WorkItemType"] == "Task" and work.fields["System.Parent"] not in ids:
                missing_parents.append(work.fields["System.Parent"])
            cleanup_work(work)
            yield work

    for chunk in chunks(missing_parents):
        request = WorkItemBatchGetRequest(error_policy="fail", ids=chunk, fields=["System.Id", "System.Title", "System.WorkItemType", "System.Description", "System.State", closed_date_field, "Microsoft.VSTS.TCM.ReproSteps"])
        for work in work_client.get_work_items_batch(request):
            cleanup_work(work)
            if work.fields["System.WorkItemType"] == "Task":
                print(f"WARN: {work.id} task has another task as child. Not supported scenario.")
            yield work

def get_work_items_ids_assigned_to_me(start_date, end_date, project) -> Iterator[str]:
    ctx = TeamContext(project=project)
    wiql = Wiql('SELECT [System.Id], [System.Title], [System.WorkItemType], [System.Description], [System.Parent] FROM WorkItems ' 
                f'WHERE [System.AssignedTo] = "{author}" and [{closed_date_field}] >= "{start_date}" and [{closed_date_field}] <= "{end_date}"  ORDER BY [{closed_date_field}] Desc')
    items = work_client.query_by_wiql(wiql, team_context=ctx, time_precision=True)
    return [w.id for w in items.work_items]

def get_my_work_items_ids(prs: List[GitPullRequest], start_date, end_date, project) -> Iterator[WorkItem]:
    ids = set([work_id for pr in prs for work_id in pr.work_item_refs])
    ids = ids.union(get_work_items_ids_assigned_to_me(start_date, end_date, project))
    return get_work_items_batch(list(ids), end_date)