from constructs import Construct
from aws_cdk import (
    Duration,
    Stack,
    aws_iam as iam,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_lambda as _lambda,
    aws_apigateway as apigw
)


class SyncTogglStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sync_toggl_lambda = _lambda.Function(
            self, 'SyncTogglHandler',
            runtime=_lambda.Runtime.PYTHON_3_8,
            code=_lambda.Code.from_asset('lambdas/sync_toggl'),
            handler='handler.handle',
        )

        api = apigw.LambdaRestApi(
            self, 'Endpoint',
            handler=sync_toggl_lambda
        )

        start = api.root.add_resource("start")
        start.add_method("GET")

        end = api.root.add_resource("end")
        end.add_method("GET")
