# How the app is built

Service Desk has four main parts:

- **Web app:** the pages people use to open cases, read sources, and approve work.
- **API:** checks access, searches information, prepares reports, and handles approvals.
- **Database:** stores accounts, cases, documents, reports, and work orders.
- **Laya service:** checks requests and returns simple case signals.

The main writing model can run locally or at a configured service. The app also includes a demo mode.

## What happens during an investigation

1. The app checks who signed in and which case they may open.
2. Laya checks the request for unsafe instructions.
3. If the request passes, the app searches only documents the person may read and loads related service records.
4. Laya can label the case type or urgency.
5. The writing model prepares a report with links to the sources it used.
6. If useful, the app saves a work-order suggestion for review.
7. A manager approves the suggestion.
8. The API checks the latest case information before saving the work order.

If Laya blocks a request, the app does not search for information or prepare a report.

## Where information lives

- Uploaded manuals and other files are split into searchable pieces and tagged with who may read them.
- Case, customer, equipment, parts, and work-order details are stored as database records.
- Reports and activity records show what happened during each investigation.
- Only the API can save an approved work order. The model cannot write to the database directly.
