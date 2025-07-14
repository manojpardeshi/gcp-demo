# Project Progress: Salesforce to GCP Integration

This document summarizes the development and troubleshooting process for the Salesforce to GCP integration project.

## 1. Initial Requirement & Plan

The initial request was to build a system where a change in a Salesforce record would trigger a Google Cloud Function. This function would then fetch the full record details, insert them into a BigQuery table, and send an email notification using SendGrid.

A high-level plan was established:
1.  **Salesforce**: Use Workflow Rules and Outbound Messages to trigger the process.
2.  **GCP**: Set up a Cloud Function, BigQuery table, and Secret Manager.
3.  **Implementation**: Write a Python Cloud Function to handle the logic.

## 2. Initial Implementation

*   A `cloud_function` directory was created.
*   `requirements.txt` was created with initial dependencies (`google-cloud-bigquery`, `google-cloud-secret-manager`, `simple-salesforce`, `sendgrid`, `lxml`).
*   A `main.py` file was created with placeholder functions for each logical step.
*   The placeholder functions were implemented one by one:
    *   Parsing the Salesforce notification.
    *   Fetching secrets from Secret Manager.
    *   Inserting data into BigQuery.
    *   Sending an email with SendGrid.

## 3. Iteration and Troubleshooting

The initial plan and implementation faced several real-world challenges that required iterative debugging and refinement.

### 3.1. Salesforce: Flow Control vs. Process Automation

*   **Problem**: The user's Salesforce Developer Org did not allow the use of Process Automation (Workflow Rules). The only available tool was Flow Builder.
*   **Solution**: The plan was adapted to use a Salesforce Flow. This meant changing the Cloud Function's parsing logic from expecting a SOAP XML message to expecting a JSON payload from a Flow's HTTP callout. The `parse_salesforce_notification` function was rewritten accordingly.

### 3.2. Salesforce: Missing "Create HTTP Callout" Action

*   **Problem**: The user's Flow Builder did not show the declarative "Create HTTP Callout" action, even with a Named Credential configured.
*   **Solution**: A more robust, programmatic approach was adopted. An Apex class (`GCPNotifier.cls`) with an `@InvocableMethod` was created to handle the callout. This Apex class could then be called as an Action from the Flow, bypassing the need for the declarative callout feature. A corresponding test class (`GCPNotifierTest.cls`) was also created.

### 3.3. Email Service: SendGrid vs. Gmail API (Free Alternative)

*   **Problem**: The user noted that SendGrid was not a free service and requested a free alternative.
*   **Solution**: The project was refactored to use the **Gmail API**.
    *   `requirements.txt` was updated to remove `sendgrid` and add Google's API client libraries (`google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`).
    *   The `send_email_notification` and `get_secrets` functions in `main.py` were rewritten to handle OAuth 2.0 authentication and email sending via the Gmail API.
    *   A helper script, `get_gmail_token.py`, was created to simplify the process of generating the required OAuth refresh token.
    *   The `setup.md` documentation was updated with detailed instructions for this new process.

### 3.4. Local Environment: Python Dependency Installation

*   **Problem**: Running `pip install` failed due to `command not found`. Subsequently, `pip3 install` failed due to an `externally-managed-environment` error, a protection mechanism on modern macOS Python installations.
*   **Solution**: A Python virtual environment (`venv`) was created to isolate project dependencies. The required libraries were successfully installed within this virtual environment.

### 3.5. GCP: Cloud Function Deployment Failures

*   **Problem 1**: The initial `gcloud functions deploy` command failed with a `Container Healthcheck failed` error. This was initially diagnosed as a missing web server framework.
*   **Solution 1 (Incorrect)**: `Flask` and `gunicorn` were added to `requirements.txt`. The deployment failed again with the same error.
*   **Problem 2 (Root Cause)**: The user provided GCP logs, which revealed the true error: `ModuleNotFoundError: No module named 'salesforce_api'`. The Python code was using an incorrect import statement.
*   **Solution 2 (Correct)**: The import statement in `main.py` was corrected from `from salesforce_api import Salesforce` to `from simple_salesforce import Salesforce`. The subsequent deployment was successful.

### 3.6. Salesforce: Apex and Callout Errors

*   **Problem 1**: The user reported a compilation error in the `GCPNotifierTest.cls` test class because the `setBody` method does not exist on `StaticResourceCalloutMock`.
*   **Solution 1**: The code was corrected to use `setBodyAsBlob`. This also failed with a similar error, suggesting an API version incompatibility in the user's org.
*   **Solution 2**: The test class was rewritten to implement the `HttpCalloutMock` interface directly, a more robust and version-agnostic approach.
*   **Problem 2**: After fixing the test class, the user provided Salesforce logs showing the error: `System.CalloutException: You have uncommitted work pending`.
*   **Solution 3**: This was diagnosed as a governor limit issue. The `GCPNotifier.cls` was refactored to use the standard two-method pattern for asynchronous callouts: an `@InvocableMethod` that calls a separate `@future(callout=true)` method, decoupling the callout from the database transaction.

### 3.7. GCP: IAM and Authentication Errors

*   **Problem 1**: After fixing the Apex code, Salesforce was able to call the function, but GCP returned a `403 Forbidden` error.
*   **Solution 1**: The function, being 2nd gen, required the `roles/run.invoker` permission for public access. This was granted to `allUsers` using the `gcloud functions add-invoker-policy-binding` command.
*   **Problem 2**: The function then executed but failed with a `403 Permission 'secretmanager.versions.access' denied` error.
*   **Solution 2**: The function's service account was missing permissions to read secrets. The `roles/secretmanager.secretAccessor` role was granted to the function's service account.
*   **Problem 3**: The function still failed with a `SalesforceAuthenticationFailed: INVALID_LOGIN` error.
*   **Solution 3**: After adding logging to the function, it was confirmed the credentials were being fetched correctly. The final issue was a data entry problem: the user had mistakenly combined the Salesforce password and security token in the `salesforce-password` secret. The solution was to store the password and token in their respective separate secrets, as the Python code handles combining them correctly.

## 4. Final Outcome

After a thorough, iterative process of implementation and debugging across both Salesforce and GCP platforms, all issues were resolved. The final solution is a robust, event-driven integration that meets all the initial requirements, using the free Gmail API for notifications and correctly handling all necessary security and platform constraints. The entire process and final setup instructions are documented in `setup.md`. The project is now fully functional.
