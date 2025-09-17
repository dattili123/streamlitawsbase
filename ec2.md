Perfect. Here’s a clean, copy-pasteable setup you can do entirely in the AWS console. It targets only instances with `AssetId=msr003452` and stops or terminates them after 48 hours of sustained idleness. You choose the action via an environment variable.

# What the function does

* Every hour, it scans EC2 instances with `AssetId=msr003452` that are in `running`.
* Pulls the last 48 hourly datapoints for CPUUtilization, NetworkIn, NetworkOut.
* If averages are below thresholds across the whole 48-hour window, it either **stops** or **terminates** the instance.

Defaults:

* Idle window: 48 hours
* CPU average < 3%
* Network In+Out average < 5 MB/hour

You can tune these without code changes via env vars.

---

# Step 1) Create the IAM role for Lambda

1. Go to IAM → Roles → Create role.
2. Trusted entity: **AWS service** → **Lambda**.
3. Attach a new inline policy (after creating the role) with this JSON:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ], "Resource": "*" },
    { "Effect": "Allow", "Action": [
        "ec2:DescribeInstances",
        "ec2:DescribeInstanceAttribute",
        "ec2:StopInstances",
        "ec2:TerminateInstances"
      ], "Resource": "*" },
    { "Effect": "Allow", "Action": [
        "cloudwatch:GetMetricStatistics"
      ], "Resource": "*" }
  ]
}
```

No VPC needed unless your org requires it for outbound egress.

---

# Step 2) Create the Lambda function

1. Lambda → Create function.
2. Author from scratch:

   * Name: `ec2-idle-reaper`
   * Runtime: **Python 3.11**
   * Architecture: x86\_64 is fine
   * Execution role: the role you just created
3. Basic settings:

   * Timeout: **2 minutes**
   * Memory: **256–512 MB** (256 is typically plenty)

### Environment variables

Add these so you can change behavior without redeploying:

| Key             | Value                 | Notes                              |
| --------------- | --------------------- | ---------------------------------- |
| ACTION          | `stop` or `terminate` | What to do when idle               |
| WINDOW\_HOURS   | `48`                  | Idle window length                 |
| CPU\_MAX        | `3`                   | Percent                            |
| NET\_MAX\_BYTES | `5242880`             | 5 MB/hour                          |
| DRY\_RUN        | `false`               | Set `true` to test without actions |

Optional guards (set only if you want them):

* `BLOCK_TERMINATE_ON_PROD=true` and add a tag `Environment=prod` to prevent termination in prod environments.
* `REQUIRE_FULL_WINDOW=true` to insist on exactly 48 datapoints (skips very new instances until enough data accrues).

### Paste this handler (index.py)

```python
import os
import boto3
import datetime
from datetime import timezone, timedelta

ec2 = boto3.client("ec2")
cw  = boto3.client("cloudwatch")

# Env vars
ACTION = os.getenv("ACTION", "stop").lower()  # "stop" or "terminate"
WINDOW_HOURS = int(os.getenv("WINDOW_HOURS", "48"))
CPU_MAX = float(os.getenv("CPU_MAX", "3"))
NET_MAX_BYTES = int(os.getenv("NET_MAX_BYTES", str(5 * 1024 * 1024)))  # 5 MB
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
REQUIRE_FULL_WINDOW = os.getenv("REQUIRE_FULL_WINDOW", "false").lower() == "true"
BLOCK_TERMINATE_ON_PROD = os.getenv("BLOCK_TERMINATE_ON_PROD", "false").lower() == "true"

PERIOD = 3600  # 1 hour

def get_metric_avg(metric_name, instance_id, stat="Average"):
    end = datetime.datetime.now(tz=timezone.utc)
    start = end - timedelta(hours=WINDOW_HOURS)
    resp = cw.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName=metric_name,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=start,
        EndTime=end,
        Period=PERIOD,
        Statistics=[stat]
    )
    dps = resp.get("Datapoints", [])
    if not dps:
        return None, 0
    # Average of hourly averages
    avg = sum(dp.get(stat, 0.0) for dp in dps) / len(dps)
    return avg, len(dps)

def is_prod_instance(tags):
    return tags.get("Environment", "").lower() == "prod"

def termination_protected(instance_id):
    attr = ec2.describe_instance_attribute(
        InstanceId=instance_id,
        Attribute="disableApiTermination"
    )
    return bool(attr.get("DisableApiTermination", {}).get("Value"))

def handler(event, context):
    # Only target instances with AssetId=msr003452 and state=running
    filters = [
        {"Name": "instance-state-name", "Values": ["running"]},
        {"Name": "tag:AssetId", "Values": ["msr003452"]}
    ]
    reservations = ec2.describe_instances(Filters=filters).get("Reservations", [])

    to_stop, to_terminate = [], []

    for r in reservations:
        for inst in r.get("Instances", []):
            iid = inst["InstanceId"]
            tags = {t["Key"]: t["Value"] for t in inst.get("Tags", [])}

            # Skip autoscaling-managed instances
            if "aws:autoscaling:groupName" in tags:
                print(f"{iid}: in ASG, skipping")
                continue

            # Get metrics
            cpu_avg, cpu_pts = get_metric_avg("CPUUtilization", iid)
            net_in_avg, ni_pts = get_metric_avg("NetworkIn", iid)
            net_out_avg, no_pts = get_metric_avg("NetworkOut", iid)

            # If we have no data, skip
            if cpu_avg is None or net_in_avg is None or net_out_avg is None:
                print(f"{iid}: insufficient metrics, skipping")
                continue

            # Require full window if requested
            if REQUIRE_FULL_WINDOW:
                min_pts = min(cpu_pts, ni_pts, no_pts)
                if min_pts < WINDOW_HOURS:  # expecting one hourly dp per hour
                    print(f"{iid}: only {min_pts} datapoints (<{WINDOW_HOURS}), skipping")
                    continue

            net_avg = net_in_avg + net_out_avg

            print(f"{iid}: cpu_avg={cpu_avg:.3f}%, net_avg={int(net_avg)} bytes/hr "
                  f"(pts cpu/ni/no={cpu_pts}/{ni_pts}/{no_pts})")

            idle = cpu_avg < CPU_MAX and net_avg < NET_MAX_BYTES

            if not idle:
                continue

            # Guardrails
            if ACTION == "terminate":
                if termination_protected(iid):
                    print(f"{iid}: termination-protected, skipping terminate")
                    continue
                if BLOCK_TERMINATE_ON_PROD and is_prod_instance(tags):
                    print(f"{iid}: prod instance and BLOCK_TERMINATE_ON_PROD=true, skipping terminate")
                    continue

            # Queue action
            if ACTION == "stop":
                to_stop.append(iid)
            elif ACTION == "terminate":
                to_terminate.append(iid)
            else:
                print(f"Unknown ACTION={ACTION}, doing nothing")

    # Execute actions
    result = {"stopped": [], "terminated": [], "dry_run": DRY_RUN}
    if DRY_RUN:
        print(f"DRY_RUN: would stop {to_stop} and terminate {to_terminate}")
    else:
        if to_stop:
            resp = ec2.stop_instances(InstanceIds=to_stop)
            result["stopped"] = [i["InstanceId"] for i in resp.get("StoppingInstances", [])]
        if to_terminate:
            resp = ec2.terminate_instances(InstanceIds=to_terminate)
            result["terminated"] = [i["InstanceId"] for i in resp.get("TerminatingInstances", [])]

    print(result)
    return result
```

Save, then use the **Test** button with an empty event to verify it runs and logs properly. Start with `DRY_RUN=true` so nothing actually happens during validation.

---

# Step 3) Create the EventBridge schedule

1. EventBridge → Rules → Create rule.
2. Name: `ec2-idle-reaper-hourly`
3. Schedule pattern: **Cron expression**

   * `0 * * * ? *`  → runs at the top of every hour.
4. Target: **Lambda function** → select `ec2-idle-reaper`.
5. Create rule.

---

# Step 4) Tag the instances

Ensure only the instances you want touched have this exact tag:

* Key: `AssetId`
* Value: `msr003452`

Nothing else is required. The function ignores everything without that tag.

---

# Step 5) Sanity checks and rollout

1. Set `DRY_RUN=true`, run the Lambda once, and read CloudWatch Logs for:

   * Per-instance CPU and network averages
   * Whether it would stop/terminate
   * Datapoint counts (confirm you’re getting hourly data)
2. If numbers look right, set `DRY_RUN=false`.
3. Choose your action:

   * `ACTION=stop` first for a safer rollout
   * Switch to `ACTION=terminate` later if that’s truly desired

Tip: if instances are very new, you may not yet have 48 datapoints. Either wait, or set `REQUIRE_FULL_WINDOW=false` and accept “average of available data.”

---

## Tweaks you might want later

* Different thresholds per instance: add tags like `IdleCpuMax`, `IdleNetMaxBytes` and read them in the code to override defaults.
* Pre-notification: wire SNS and send a heads-up message one run before action. Easy to add if needed.
* Region coverage: deploy the same Lambda + rule in each region you use.

If you want me to add per-instance overrides or an SNS notification path, I can fold that into the same function without changing the flow.
