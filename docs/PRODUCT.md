# Product overview

Service Desk helps a service team investigate equipment problems and prepare work for review.

## How it works

The demo follows a repeated fault on a PX-400 packaging line at Northstar Foods. A service engineer opens the case and asks for help. The app searches manuals, service history, and parts information that the engineer is allowed to see. It writes a report with links to its sources and may suggest a work order.

A manager must approve the work order. Before saving it, the app checks that the case details have not changed.

## What the models do

Laya checks whether a request looks unsafe. It can also suggest a case type, urgency, or need for an on-site visit. A separate writing model prepares the report.

These model answers are suggestions. They do not grant access, approve work, or save changes.

## Product rules

- Start with a service case, not an empty chat.
- Let people open and check the sources behind a report.
- Search only information the signed-in person can see.
- Keep private information within the model services allowed to handle it.
- Let the model suggest work, but require a person to approve it.
- Show what the app did without showing hidden model reasoning.
- Keep setup small enough for one team to run.
