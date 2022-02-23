import logging
import os
from datetime import datetime, timezone
from lambdas.lib.toggl.TogglPy import Toggl


API_KEY = os.environ.get('TOGGL_API_KEY')


class TogglWrapper:
    def __init__(self, client_names=None):
        assert API_KEY, "TOGGL_API_KEY env variable is not set"
        self.toggl = Toggl()
        self.toggl.setAPIKey(API_KEY)
        self.clients = {}
        self.projects = {}
        self.project_ids = {}
        self.client_names = None
        if client_names:
            assert isinstance(client_names, list), "client_names argument should be a list of string client names"
            self.client_names = client_names

    def load_clients(self):
        clients = self.toggl.getClients()
        for client in clients:
            if self.client_names and client['name'] not in self.client_names:
                continue
            self.clients[client['name']] = client['id']

    def load_projects(self):
        if not self.clients:
            self.load_clients()
        for client_name, client_id in self.clients.items():
            projects = self.toggl.getClientProjects(client_id)
            for project in projects:
                self.projects[project['name'].lower()] = project['id']
                self.project_ids[project['id']] = project['name'].lower()

    def get_annotated_time_entries(self, start, end):
        if not self.project_ids:
            self.load_projects()
        entries = self.toggl.getTimeEntries(start, end)
        for entry in entries:
            entry['project_name'] = self.project_ids[entry['pid']]
        return entries

    def sync_to_toggl(self, sheet_entries, start, end):
        dt_start = datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc)
        dt_end = datetime.combine(end, datetime.min.time()).replace(tzinfo=timezone.utc)
        toggl_entries = self.get_annotated_time_entries(dt_start, dt_end)
        existing_entries = [
            {
                'duration': int(row['duration'] / 60),
                'date': datetime.fromisoformat(row['start']).date().isoformat(),
                'comment': row['description'],
                'project': row['project_name'],
            }
            for row
            in toggl_entries
        ]
        # check items in toggle missing from google sheet
        for toggl_entry in existing_entries:
            if toggl_entry not in sheet_entries:
                logging.error('Entry exists in Toggl, but is missing from Google Timesheet: %s', toggl_entry)
                raise ValueError("Toggl has data missing in google sheets")
        # check for items in google sheet missing from toggl and add it
        for entry in sheet_entries:
            assert entry.get('project'), 'project should be set in order to sync with Toggl'
            if entry not in existing_entries:
                print("Will create: %s" % entry)
                dt = datetime.fromisoformat(entry['date'])
                start_hour = 10
                res = self.toggl.createTimeEntry(description=entry['comment'],
                                                 minuteduration=entry['duration'],
                                                 projectid=self.projects[entry['project']],
                                                 month=dt.month, day=dt.day, hour=start_hour)

    def track(comment, date, duration, start_hour=9, project=None):
        toggl = Toggl()
        toggl.setAPIKey(API_KEY)
        all_clients = toggl.getClients()

        client = 'Development' if project == 'Ingest Framework' else 'Clients'
        res = toggl.createTimeEntry(description=comment,
                              hourduration=duration,
                              projectname=project,
                              clientname=client, month=date.month, day=date.day, hour=start_hour)
