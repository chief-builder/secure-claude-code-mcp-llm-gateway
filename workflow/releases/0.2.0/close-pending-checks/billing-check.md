# Check 1: billed cost of the live Bedrock run, and budget alert email

Status: cost estimate recorded; alert email not yet deliverable; final invoice due early December

## What is being checked

The live run is recorded in
[the Component 8 verification](../../../../docs/component-08/verification.md). It
used one `t3.small` host in `us-east-1` for under two hours, an 8 GiB disk, one
public address, and a small number of Claude Haiku 4.5 requests. A $5 monthly
budget with alerts at $1 and $4 of actual cost was created, alongside an existing
Route 53 charge of about $0.50 a month.

Three questions:

1. **What did the run cost?** It was approved under a $5 ceiling.
2. **Is anything from it still running and billing?**
3. **Can the budget alert actually deliver an email?**

## What to expect

A rough estimate, to compare the bill against. The model prices are the ones the
owner recorded at the time; the other prices are from memory and should be read off
the bill, not trusted from here.

| Item | Basis | Expected |
|---|---|---|
| Host | under 2 hours of `t3.small` | a few cents |
| Public address | under 2 hours at $0.005 an hour | about $0.01 |
| Disk | 8 GiB for under 2 hours | well under $0.01 |
| Model | $1.10 per million input tokens, $5.50 per million output; a handful of short requests plus Claude Code's own prompts | a few cents at most |
| Total for the run | | roughly $0.05 to $0.20 |

Two consequences. The run should be far below the $5 ceiling. And it should be
below the $1 alert, so **no alert email is expected from the run itself**: an empty
inbox does not show the alert is broken, and a separate test is needed for
question 3.

The November invoice is not final until early December. Figures read before then
are estimates; the reconciliation is complete only when the invoice is issued.

## Steps for the owner

Run these in your own terminal, signed in to the AWS account the run used. The
assistant does not run them. Each Cost Explorer command costs $0.01; the Billing
console shows the same figures free of charge under Cost Explorer and Bills.

**A. Month-to-date cost by service, and whether credits offset any of it**

```sh
aws ce get-cost-and-usage --time-period Start=2026-11-01,End=2026-11-27 \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=SERVICE \
  --query 'ResultsByTime[].Groups[].[Keys[0],Metrics.UnblendedCost.Amount]' --output text
aws ce get-cost-and-usage --time-period Start=2026-11-01,End=2026-11-27 \
  --granularity MONTHLY --metrics UnblendedCost \
  --group-by Type=DIMENSION,Key=RECORD_TYPE \
  --query 'ResultsByTime[].Groups[].[Keys[0],Metrics.UnblendedCost.Amount]' --output text
```

**B. Daily detail around the run**

```sh
aws ce get-cost-and-usage --time-period Start=2026-11-21,End=2026-11-26 \
  --granularity DAILY --metrics UnblendedCost UsageQuantity \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --query 'ResultsByTime[].[TimePeriod.Start,Groups[].[Keys[0],Metrics.UnblendedCost.Amount,Metrics.UsageQuantity.Amount]]' \
  --output json
```

**C. Anything left running in the Region the run used**

```sh
aws ec2 describe-instances --region us-east-1 \
  --filters Name=instance-state-name,Values=pending,running,stopping,stopped \
  --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType]' --output text
aws ec2 describe-volumes --region us-east-1 --query 'Volumes[].[VolumeId,State,Size]' --output text
aws ec2 describe-addresses --region us-east-1 --query 'Addresses[].PublicIp' --output text
aws ec2 describe-snapshots --region us-east-1 --owner-ids self --query 'Snapshots[].SnapshotId' --output text
```

Empty output from all four means nothing from the run is still billing there.

**D. The budget and its alerts**

Set the first line to your budget's name before running.

```sh
budget_name='REPLACE WITH YOUR BUDGET NAME'
acct="$(aws sts get-caller-identity --query Account --output text)"
aws budgets describe-budgets --account-id "$acct" \
  --query 'Budgets[].[BudgetName,BudgetLimit.Amount,CalculatedSpend.ActualSpend.Amount,TimeUnit]' --output text
aws budgets describe-notifications-for-budget --account-id "$acct" --budget-name "$budget_name" \
  --query 'Notifications[].[NotificationType,ComparisonOperator,Threshold,ThresholdType,NotificationState]' --output text
```

**E. Prove the alert email arrives**

Add a temporary alert at one cent, which this month's spend already exceeds, so it
should fire at the budget's next evaluation. AWS evaluates budgets a few times a
day, so allow up to a day. Set both lines to your own values first.

```sh
budget_name='REPLACE WITH YOUR BUDGET NAME'
alert_email='REPLACE WITH YOUR EMAIL ADDRESS'
acct="$(aws sts get-caller-identity --query Account --output text)"
aws budgets create-notification --account-id "$acct" --budget-name "$budget_name" \
  --notification NotificationType=ACTUAL,ComparisonOperator=GREATER_THAN,Threshold=0.01,ThresholdType=ABSOLUTE_VALUE \
  --subscribers SubscriptionType=EMAIL,Address="$alert_email"
```

When the email arrives, note the time it was received, then remove the temporary
alert:

```sh
budget_name='REPLACE WITH YOUR BUDGET NAME'
acct="$(aws sts get-caller-identity --query Account --output text)"
aws budgets delete-notification --account-id "$acct" --budget-name "$budget_name" \
  --notification NotificationType=ACTUAL,ComparisonOperator=GREATER_THAN,Threshold=0.01,ThresholdType=ABSOLUTE_VALUE
```

The same can be done in the console: Billing, Budgets, the budget, Edit, add an
alert threshold of $0.01 actual, and delete it afterwards.

## What to report back

Paste the output of A to D, and say when the test email from E arrived. Leave out
the account number and the email address; neither goes into the repository.

## Results

### 2026-11-26 — first reading, from the Billing console

The owner took the readings in the AWS console and supplied screenshots. The account
number and email address shown in them are deliberately not recorded here.

**1. What the run cost: about $0.04, against a $5 ceiling.**

| Service, November to date | Amount | Note |
|---|---|---|
| Route 53 | $0.50 | The existing monthly charge, unrelated to the run |
| EC2 instances | $0.03 | All on 23 November (UTC), the day of the run |
| VPC | $0.01 | The public address, also on 23 November |
| Claude Haiku 4.5 (Bedrock) | $0.00 | Present on 23 November but under half a cent |
| EC2 other (the disk) | $0.00 | Under half a cent |
| S3, CloudShell, Glue, KMS, CloudWatch, tax | $0.00 | |
| Month-to-date total | $0.53 to $0.54 | Cost Explorer shows $0.53, the Bills page $0.54; the difference is rounding |

The run's own charges appear only on 23 November and come to about $0.04. That is
slightly below the estimate above and less than one percent of the approved ceiling.
The console rounds to the cent, so the model charge is known only to be under half a
cent.

These are estimates. The Bills page shows the November bill as "Pending".

**2. Nothing from the run is still billing.** In `us-east-1` the EC2 dashboard
shows no instances, no volumes, no snapshots and no Elastic IPs. It shows three
security groups and one key pair, neither of which costs anything. The key pair is
worth identifying, because the Component 8 record says the run's key registration
was deleted.

**3. The budget alert cannot deliver an email as configured.** The budget
`llm-gateway-lab-monthly-5usd` is healthy, at $0.54 of $5.00, with its thresholds
not reached. But its one email recipient is shown as "Pending" verification, with
"0/1 email verified", and the console states that recipients added on or after
30 September 2026 must verify their address before they can receive budget alerts.
So an alert at $1 or $4 would not have reached anyone. The Component 8 record's
"alert configuration healthy" was true of the thresholds and not of delivery.

### Still open

- Verify the recipient address (Budgets, the budget, "Resend verification", then the
  link in the email), and confirm the status changes to verified.
- Then run the one-cent test alert in step E, record when the email arrives, and
  remove the test alert.
- Identify the remaining key pair in `us-east-1`, and delete it if it is the run's.
- Read the November bill again once its status is no longer "Pending", in early
  December, and record the final figures.
