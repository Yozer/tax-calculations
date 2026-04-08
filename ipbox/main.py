import os, traceback
from datetime import datetime, tzinfo
from typing import Iterable, List, NamedTuple
from azure.devops.v6_0.git.models import GitPullRequest
from azure.devops.v6_0.work_item_tracking.models import WorkItem
from dateutil.relativedelta import relativedelta
from openpyxl import cell, load_workbook, Workbook
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.styles import Font, Fill
import pytz
from az import get_my_prs_from_repos, get_my_work_items_ids, get_work_items_assigned_to_me
from settings import excel_path, year, from_month, to_month, projects, tasks_only
import re

insensitive = re.compile('fix:?', re.IGNORECASE)

class ExcelRow(NamedTuple):
    merge_id: str
    work_item_title: str
    pr_title: str
    closed_date: datetime
    pr_url: str

def build_excel_models(all_work_items: List[WorkItem], prs: List[GitPullRequest]) -> Iterable[ExcelRow]:

    def obfuscate(title):
        return insensitive.sub('', title).strip().strip(':').strip()

    prs.sort(key=lambda x: x.closed_date)
    for pr in prs:
        work_items = list([w.fields["System.Title"] for w in all_work_items if w.id in pr.work_item_refs])
        if len(work_items) == 0:
            if len(pr.work_item_refs) > 0:
                print(f"Warn: {pr.id} has work items but could find title")
            title = ""
        else:
            title = '; '.join(work_items)

        yield ExcelRow(pr.merge_id, obfuscate(title), obfuscate(pr.title), pr.closed_date, pr.url)

def build_excel_models_from_tasks(work_items: List[WorkItem]) -> Iterable[ExcelRow]:

    def obfuscate(title):
        return insensitive.sub('', title).strip().strip(':').strip()

    work_items.sort(key=lambda w: w.fields.get("Microsoft.VSTS.Common.ClosedDate", datetime.min))
    for wi in work_items:
        closed = wi.fields.get("Microsoft.VSTS.Common.ClosedDate", None)
        yield ExcelRow(
            merge_id=str(wi.id),
            work_item_title=obfuscate(wi.fields.get("System.Title", "")),
            pr_title="",
            closed_date=closed,
            pr_url=""
        )
            
def write_header(ws: Worksheet):
    header = ["PR Id", "Task title", "PR title", "Merged Date", "Time", "Pull Request"]

    for i, h in enumerate(header):
        ws.cell(row=1, column=i + 1).value = h
        ws.cell(row=1, column=i + 1).font = Font(bold=True)

def is_excel_valid(month):
    if not os.path.exists(excel_path):
        return True
    wb = load_workbook(filename = excel_path)
    sheet_name = f'{year}-{month}'
    if sheet_name in wb.sheetnames and wb[sheet_name]["A2"].value is not None:
        return False
    return True

def write_excel(rows: Iterable[ExcelRow], month):
    exists = os.path.exists(excel_path)
    wb = load_workbook(filename = excel_path) if exists else Workbook()
    sheet_name = f'{year}-{month}'
    if not exists:
        wb.active.title = sheet_name
    ws: Worksheet = wb[sheet_name] if sheet_name in wb.sheetnames else wb.create_sheet(sheet_name)
    max_col = 5

    write_header(ws)
    for idx, row in enumerate(rows):
        row_id = idx + 2
        
        ws.cell(row=row_id, column=1).value = row.merge_id
        ws.cell(row=row_id, column=2).value = row.work_item_title
        ws.cell(row=row_id, column=3).value = row.pr_title
        ws.cell(row=row_id, column=4).value = row.closed_date.astimezone(pytz.timezone("Poland")).replace(tzinfo=None) if row.closed_date else None
        ws.cell(row=row_id, column=5).value = 0
        ws.cell(row=row_id, column=6).value = row.pr_url

    for col in range(1, max_col + 1):
         ws.column_dimensions[get_column_letter(col)].bestFit = True

    wb.save(excel_path)


for month in range(from_month, to_month + 1):
    if not is_excel_valid(month):
        print(f"Sheet for month {month} already has values. Skipping")
        continue

    print(f"[{month}/{to_month}] Processing {year}-{month:02d}...")
    start_date = datetime(year, month, 1, tzinfo=pytz.timezone("Poland"))
    end_date = start_date + relativedelta(months=1) - relativedelta(seconds=1)

    try:
        excel_models = []
        for project in projects:
            if tasks_only:
                print(f"  [{month}/{to_month}] Project: {project} - fetching work items (tasks only)...")
                work_items = list(get_work_items_assigned_to_me(start_date, end_date, project))
                print(f"  [{month}/{to_month}] Project: {project} - found {len(work_items)} work items")
                excel_models += build_excel_models_from_tasks(work_items)
            else:
                print(f"  [{month}/{to_month}] Project: {project} - fetching PRs...")
                prs = list(get_my_prs_from_repos(start_date, end_date, project))
                print(f"  [{month}/{to_month}] Project: {project} - found {len(prs)} PRs, fetching work items...")
                work_items = list(get_my_work_items_ids(prs, start_date, end_date, project))
                print(f"  [{month}/{to_month}] Project: {project} - found {len(work_items)} work items")
                excel_models += build_excel_models(work_items, prs)

        write_excel(excel_models, month)
        print(f"[{month}/{to_month}] Done {year}-{month:02d} ({len(excel_models)} rows written)")
    except Exception:
        print(f"[{month}/{to_month}] FAILED on {year}-{month:02d}")
        traceback.print_exc()