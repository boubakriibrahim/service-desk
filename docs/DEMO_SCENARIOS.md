# Demo walkthrough

This walkthrough uses the sample packaging-machine case included with the app. Start the default demo with `make up`, then open <http://localhost:3000>.

## Review the case

1. Sign in as `service@demo.local` with password `demo-password`.
2. Open the sample case and select **Run investigation**.
3. Read the report and open its source links.
4. Open **Approvals**. The engineer can review suggested work but cannot approve it.

## Try a request the app should stop

1. Return to the case and choose **Try blocked request**.
2. The app should stop the request before searching the documents or writing a report.
3. Open **View run** to see where the app stopped.

## Approve suggested work

1. Sign in as `manager@demo.local` with password `demo-password`.
2. Open **Approvals** and review the suggested work and its sources.
3. Select **Approve & execute**.
4. Return to the case. The approved work should now appear there.

Before saving the work, the app checks that the case has not changed.

## Check access by role

- The service engineer can see service and engineering records.
- The manager can see the full sample set, including one restricted manual.
- The finance user can see the finance note but no service cases.

Sign in as `finance@demo.local` with password `demo-password` to see the limited view.

The demo data is for this local example. Do not use these sample accounts for real work.
