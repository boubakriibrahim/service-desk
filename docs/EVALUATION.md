# What the checks cover

The included checks use fixed demo data so the same expected results can be checked again.

They check that:

- the service case includes the expected sources;
- a service user cannot see finance-only information;
- the investigation reaches the report-writing step;
- every source link points to information given to the writing model;
- the app saves a work-order suggestion for approval instead of saving it right away;
- an engineer cannot approve the suggestion;
- a manager can approve a valid suggestion;
- an approved work order and its activity record are saved.

## Checks for Laya

In demo mode, Laya returns fixed answers so the full example is repeatable.

When using the live Laya service, check that it returns answers, that an outage never approves or saves work, and that the activity record shows whether Laya was used. If Laya is marked as required, an outage should stop the investigation. If it is optional, the app should handle the outage using its configured fallback.

Laya's scores are not permission checks or proven measures of risk for every service team.

## Search quality

The current checks focus on finding expected information and keeping restricted information out. If the document collection grows, add a human-reviewed list of relevant documents and measure how often search finds them. Do not judge search quality from the report alone.
