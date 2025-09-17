Got it. We’ll just **identify** under-utilized EMR instances, nothing else.

Here’s a simple Lambda that:

* Filters EC2 to only EMR nodes using EMR’s **system tags**
  `aws:elasticmapreduce:job-flow-id` and `aws:elasticmapreduce:instance-group-role` (MASTER/CORE/TASK). ([AWS Documentation][1])
* Pulls recent EC2 metrics from CloudWatch per instance.
* Flags instances below your thresholds and reports them (logs + optional SNS).
  No tagging, no stopping.

### Thresholds (tune to taste)

* Average **CPUUtilization < 5%**
* Average **NetworkIn + NetworkOut < 5 MB/hour**
* Lookback window: **14 days** at 1-hour periods to reduce noise.

### Minimal IAM for the Lambda

* `ec2:DescribeInstances`
* `cloudwatch:GetMetricData`
* `sns:Publish` (only if you wire up SNS)

### Python 3.11 Lambda

Env vars:

* `LOOKBACK_DAYS=14`
* `CPU_THRESHOLD=5`
* `NET_BYTES_PER_HOUR_THRESHOLD=5000000`
* `SNS_TOPIC_ARN` optional

```python
import os
from datetime import datetime, timedelta, timezone
import boto3

ec2 = boto3.client("ec2")
cw = boto3.client("cloudwatch")
sns = boto3.client("sns")

LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "14"))
CPU_THRESHOLD = float(os.getenv("CPU_THRESHOLD", "5"))
NET_BYTES_PER_HOUR_THRESHOLD = int(os.getenv("NET_BYTES_PER_HOUR_THRESHOLD", "5000000"))
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")

EMR_TAG_JOBFLOW = "aws:elasticmapreduce:job-flow-id"         # EMR cluster id like j-XXXX
EMR_TAG_ROLE = "aws:elasticmapreduce:instance-group-role"    # MASTER | CORE | TASK

def list_emr_instances():
    """Return running EC2 instances that belong to EMR (by EMR system tags)."""
    instances = []
    paginator = ec2.get_paginator("describe_instances")
    filters = [
        {"Name": "instance-state-name", "Values": ["running"]},
        {"Name": f"tag-key", "Values": [EMR_TAG_JOBFLOW]},
        {"Name": f"tag-key", "Values": [EMR_TAG_ROLE]},
    ]
    for page in paginator.paginate(Filters=filters):
        for res in page.get("Reservations", []):
            for inst in res.get("Instances", []):
                instances.append(inst)
    return instances

def get_avg_metrics(instance_id, start, end, period=3600):
    """Fetch hourly avg CPU, NetIn, NetOut and compute simple averages."""
    q = [
        {
            "Id": "cpu",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "CPUUtilization",
                    "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                },
                "Period": period,
                "Stat": "Average",
            },
            "ReturnData": True,
        },
        {
            "Id": "nin",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "NetworkIn",
                    "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                },
                "Period": period,
                "Stat": "Average",
            },
            "ReturnData": True,
        },
        {
            "Id": "nout",
            "MetricStat": {
                "Metric": {
                    "Namespace": "AWS/EC2",
                    "MetricName": "NetworkOut",
                    "Dimensions": [{"Name": "InstanceId", "Value": instance_id}],
                },
                "Period": period,
                "Stat": "Average",
            },
            "ReturnData": True,
        },
    ]
    resp = cw.get_metric_data(StartTime=start, EndTime=end, MetricDataQueries=q, ScanBy="TimestampDescending")
    vals = {r["Id"]: r.get("Values", []) for r in resp["MetricDataResults"]}
    def avg(v): return (sum(v) / len(v)) if v else 0.0
    cpu = avg(vals.get("cpu", []))
    net = avg(vals.get("nin", [])) + avg(vals.get("nout", []))  # bytes per hour (period=3600)
    return cpu, net

def handler(event, context):
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=LOOKBACK_DAYS)
    emr_nodes = list_emr_instances()

    underutilized = []
    for inst in emr_nodes:
        iid = inst["InstanceId"]
        cpu, net = get_avg_metrics(iid, start, now, period=3600)
        if cpu < CPU_THRESHOLD and net < NET_BYTES_PER_HOUR_THRESHOLD:
            # Pull a few handy tags for the report
            tags = {t["Key"]: t.get("Value", "") for t in inst.get("Tags", [])}
            underutilized.append({
                "InstanceId": iid,
                "Role": tags.get(EMR_TAG_ROLE, "UNKNOWN"),
                "ClusterId": tags.get(EMR_TAG_JOBFLOW, "UNKNOWN"),
                "CpuAvgPct": round(cpu, 2),
                "NetBytesPerHourAvg": int(net),
            })

    # Log a clean summary
    print(f"Checked EMR instances: {len(emr_nodes)}; Under-utilized: {len(underutilized)}")
    for r in underutilized:
        print(f"[UNDERUTILIZED] {r['InstanceId']} | {r['Role']} | {r['ClusterId']} "
              f"| CPU {r['CpuAvgPct']}% | Net/hr {r['NetBytesPerHourAvg']}")

    # Optional: push to SNS
    if SNS_TOPIC_ARN and underutilized:
        lines = ["Under-utilized EMR EC2 instances:"]
        for r in underutilized:
            lines.append(f"- {r['InstanceId']} ({r['Role']}) in {r['ClusterId']}: "
                         f"CPU {r['CpuAvgPct']}%, Net/hr {r['NetBytesPerHourAvg']}")
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject="EMR under-utilized instances", Message="\n".join(lines))

    return {"underutilized": underutilized}
```

### Why this works

* EMR auto-tags every node, so you can reliably scope to EMR-only EC2 and even slice by MASTER/CORE/TASK or cluster id. ([AWS Documentation][1])
* EC2 emits CPU/Network metrics to CloudWatch and `GetMetricData` lets you batch query efficiently over a long window. ([AWS Documentation][2])

### Optional refinements

* Split results by **role**. Masters often look “idle” while still needed; treat them separately.
* Add CloudWatch’s EMR **IsIdle** at the **cluster** level for context in the SNS message, but don’t act on it. ([AWS Documentation][3])
* If you use EMR managed scaling, you can also surface **YARNMemoryAvailablePercentage** to show cluster headroom alongside instance under-utilization. ([AWS Documentation][4])

If you want me to adapt the thresholds to, say, p90 CPU and p90 network over the window, I’ll swap the averaging logic to percentile math and keep everything else the same.

[1]: https://docs.aws.amazon.com/emr/latest/ManagementGuide/emr-plan-tags.html?utm_source=chatgpt.com "Tag and categorize Amazon EMR cluster resources"
[2]: https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/viewing_metrics_with_cloudwatch.html?utm_source=chatgpt.com "CloudWatch metrics that are available for your instances"
[3]: https://docs.aws.amazon.com/emr/latest/ManagementGuide/UsingEMR_ViewingMetrics.html?utm_source=chatgpt.com "Monitoring Amazon EMR metrics with CloudWatch"
[4]: https://docs.aws.amazon.com/emr/latest/ManagementGuide/managed-scaling-metrics.html?utm_source=chatgpt.com "Understanding managed scaling metrics in Amazon EMR"
