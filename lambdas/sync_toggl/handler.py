#! /usr/bin/env python

import logging

import argparse
import sys
import os
from dateutil.relativedelta import relativedelta
from datetime import datetime, date, timedelta

root = os.path.abspath("")
sys.path.append(root)

from lambdas.lib.google_sheets import GoogleDailyTimeSheets
from lambdas.lib.toggl_wrapper import TogglWrapper


logging.basicConfig(level=logging.INFO)


def sync_hours(start, end):
    spreadsheet = os.environ.get("SPREADSHEET_ID")
    logging.info(f"Syncing ours for from {start} till {end}")
    tab_name = start.strftime('%b %y')
    timesheet = GoogleDailyTimeSheets(doc=spreadsheet, sheet=tab_name)
    rows = timesheet.get_days_in_range(start, end)
    # convert to toggl format
    toggl_format_rows = [
        {
            'duration': int(row['duration_minutes']),
            'date': row['date_dt'].date().isoformat(),
            'comment': row['tasks'],
            'project': row.get('project', '').lower(),
        }
        for row
        in rows
    ]
    toggl = TogglWrapper(client_names=['Development', 'Clients'])
    toggl.sync_to_toggl(toggl_format_rows, start, end)


def parse_time_range(args):
    if args.start and args.end:
        start = datetime.strptime(args.start, '%d.%m.%Y')
        end = datetime.strptime(args.end, '%d.%m.%Y')
    else:
        today = datetime.combine(date.today(), datetime.min.time())
        if args.week:
            start = today - timedelta(days=today.weekday())
            if args.past:
                start = start - timedelta(weeks=1)
            end = start + timedelta(weeks=1)
        elif args.month:
            start = today.replace(day=1)
            if args.past:
                start = start - relativedelta(months=1)
            end = start + relativedelta(months=1)
        # end date is included, so go one day before
        end = end - timedelta(days=1)
        # no sense to go in the future
        if end > today:
            end = today
    return start, end


def handle(event, context):
    """
    This code used to be run from command line, therefore we have ArgumentParser.
    For using in the cloud, we only need a sync of one month, triggered by a spreadsheet of the month.
    So we can assume --month is the only argument passed and refactor this interface.
    Make sure correct values are set in environment.env.
    For debug purpose, you can call this script locally with:
    ./run.py lambdas/sync_toggl/ -m
    """
    parser = argparse.ArgumentParser(description='Sync work hours', add_help=False)
    parser.add_argument('-p', '--past', help='sync last one, not current', action='store_true')
    parser.add_argument('-w', '--week', help='sync one week', action='store_true')
    parser.add_argument('-m', '--month', help='sync one month', action='store_true')
    parser.add_argument('-s', '--start', help='first date of range, day.month.year (15.01.2021)', type=str)
    parser.add_argument('-e', '--end', help='last date of range, day.month.year (25.02.2021)', type=str)
    parser.add_argument('--help', action='help', help='show this help message and exit')

    args = parser.parse_args()

    assert not (args.month and args.week), "Month or week can be selected, but not both"
    assert not ((args.month or args.week) and (args.start or args.end)),\
        "Either month/week or explicit start/end should be provided, not both"
    assert (args.start and args.end) or args.week or args.month, "Time range should be provided"
    start, end = parse_time_range(args)
    assert start < end, "Start date should be before end date"
    sync_hours(start, end)
