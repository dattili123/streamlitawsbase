To ensure that the blackout steps were successful, I would follow these verification steps:

Step 1: Verify Service Bus Entities Deletion

Check in Azure Portal: Navigate to Azure Service Bus and check if the specified entities (sbq-hcb-asgwy-prod-use2-missinginfo, sbq-hcb-asgwy-prod-use2-quotedocumentinfo, sbq-hcb-asgwy-prod-use2-quotenotification) are no longer present.

Azure CLI Check:

az servicebus queue list --resource-group org-hcb-asgwy-prod-use2-sb --namespace-name <namespace-name> --output table

Expectation: The queues related to the deleted service bus entities should not appear in the output.


PowerShell Check:

Get-AzServiceBusQueue -ResourceGroupName "org-hcb-asgwy-prod-use2-sb" -Namespace "your-namespace-name"

Expectation: The listed queues should not include the deleted ones.


Log Analysis: Review Azure Activity Logs for any failed deletion attempts.



---

Step 2: Verify PSQL Extension Removal

Connect to PSQL Database:

psql -h <database-host> -U <user> -d <database>

Check Installed Extensions:

SELECT * FROM pg_extension;

Expectation: The PG_STAT_STATEMENTS extension should not be listed.


Check PostgreSQL Logs for Errors:

sudo tail -100 /var/log/postgresql/postgresql.log

Expectation: No errors related to extension removal should appear.


Azure CLI Check for PSQL Extension:

az postgres flexible-server parameter list --resource-group rg-hcb-asgwy-prod-use2-db --server-name psql-flex-hcb-asgwy-prod-use2-asgwy --query "[?name=='pg_stat_statements']"

Expectation: pg_stat_statements should not be found in the output.




---

Final Verification

1. Application Logs – Ensure applications dependent on these services do not report errors.


2. Monitoring Alerts – No critical alerts related to service bus or database functionality should be triggered.


3. Test Queries – Run test queries on dependent systems to confirm no unintended impact.



Would you like me to automate any of these checks using scripts?

