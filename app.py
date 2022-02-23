#!/usr/bin/env python3

import aws_cdk as cdk

from sync_toggl.sync_toggl_stack import SyncTogglStack


app = cdk.App()
SyncTogglStack(app, "sync-toggl")

app.synth()
