# Project Setup: Salesforce to GCP Integration

This document provides a step-by-step guide to configure the integration between Salesforce and Google Cloud Platform. The goal is to capture changes in Salesforce records, process them in a Google Cloud Function, store them in BigQuery, and send an email notification.

## Architecture Overview

1.  **Salesforce**: A Record-Triggered Flow detects a record change (create/update).
2.  **Apex Callout**: The Flow calls an Apex class that makes an HTTP POST request.
3.  **Google Cloud Function**: An HTTP-triggered function receives the request from Salesforce.
4.  **Google Secret Manager**: The function securely retrieves credentials for Salesforce and the Gmail API.
5.  **Salesforce API**: The function uses the record ID to fetch the full record details from Salesforce.
6.  **Google BigQuery**: The function inserts the record data into a BigQuery table.
7.  **Gmail API**: Upon successful insertion, the function sends an email notification using a specified Gmail account.

---

## Part 1: Google Cloud Platform (GCP) Setup

### 1.1. Create BigQuery Dataset and Table

1.  In the GCP Console, navigate to **BigQuery**.
2.  Create a new **Dataset** (e.g., `salesforce_data`).
3.  Inside the dataset, create a new **Table** (e.g., `accounts`). Define a schema that matches the data you want to capture from Salesforce. Example schema for an Account:
    *   `Id`: STRING (Required)
    *   `Name`: STRING
    *   `Industry`: STRING
    *   `Phone`: STRING
    *   `CreatedDate`: TIMESTAMP
    
### 1.2. Enable Gmail API and Create Credentials

1.  In the GCP Console, navigate to **"APIs & Services" -> "Library"**.
2.  Search for **"Gmail API"** and click **"Enable"**.
3.  Go to **"APIs & Services" -> "Credentials"**.
4.  Click **"+ CREATE CREDENTIALS"** and select **"OAuth client ID"**.
5.  If prompted, configure the **"OAuth consent screen"**.
    *   **User Type**: Select **"External"**.
    *   Fill in the required app information (app name, user support email, developer contact).
    *   On the "Scopes" page, you don't need to add any scopes.
    *   On the "Test users" page, add the email address of the Gmail account you want to send emails from.
6.  Go back to creating the OAuth client ID.
    *   **Application type**: Select **"Desktop app"**.
    *   Give it a name (e.g., "GCP Salesforce Notifier").
    *   Click **"Create"**.
7.  A window will appear with your "Client ID" and "Client Secret". Click **"DOWNLOAD JSON"** and save this file as `credentials.json` in the root of your project directory.

### 1.3. Generate a Gmail Refresh Token

You need to authorize the application to send emails on your behalf. The provided `get_gmail_token.py` script simplifies this process.

1.  Make sure you have the required Python libraries installed locally:
    ```bash
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
    ```
2.  Run the script from your terminal:
    ```bash
    python get_gmail_token.py
    ```
3.  Your web browser will open, asking you to log in to your Google account and grant permission for the app to "Send email on your behalf". **Grant this permission.**
4.  After you grant permission, the script will print your **Refresh Token** in the terminal. **Copy this value.**

### 1.4. Configure Secret Manager

1.  In the GCP Console, navigate to **Secret Manager**.
2.  Create the following secrets, storing the corresponding values:
    *   `salesforce-username`: Your Salesforce username.
    *   `salesforce-password`: Your Salesforce password concatenated with your security token.
    *   `salesforce-token`: Your Salesforce security token.
    *   `salesforce-instance-url`: Your custom Salesforce domain URL (e.g., `https://orgfarm-6a25093d73-dev-ed.develop.my.salesforce.com`).
    *   `gmail-client-id`: The `client_id` from your `credentials.json` file.
    *   `gmail-client-secret`: The `client_secret` from your `credentials.json` file.
    *   `gmail-refresh-token`: The refresh token you generated in the previous step.

### 1.5. Deploy the Cloud Function

1.  Ensure you have the `gcloud` CLI installed and authenticated.
2.  Navigate to the root directory of this project (`gcp-demo`).
3.  Run the following command, replacing the placeholder values:

```bash
gcloud functions deploy salesforce-trigger \
--runtime python39 \
--trigger-http \
--source cloud_function \
--entry-point salesforce_trigger \
--set-env-vars GCP_PROJECT=<Your GCP Project ID>,BIGQUERY_DATASET=<Your BIGQUERY DATASET ID>,BIGQUERY_TABLE=<Your Table ID>,FROM_EMAIL=<Your email id>,TO_EMAILS=<TO Email id>
```
4. After deployment, **copy the trigger URL**. You will need it for the Salesforce setup.

---

## Part 2: Salesforce Setup

### 2.1. Create a Named Credential

1.  In Salesforce Setup, search for **"Named Credentials"**.
2.  Click **"New Named Credential"**.
3.  **Label**: `GCP Cloud Function`
4.  **Name**: `GCP_Cloud_Function` (This will be the API name).
5.  **URL**: Paste the trigger URL of your deployed Google Cloud Function.
6.  **Generate Authorization Header**: Uncheck this box.
7.  Leave other settings as default and click **"Save"**.

### 2.2. Create the Apex Class (`GCPNotifier.cls`)

1.  In Setup, search for **"Apex Classes"** and click **"New"**.
2.  Paste the following code. **Remember to replace `Your_Named_Credential_API_Name` with the API name from the previous step (e.g., `GCP_Cloud_Function`)**.

```apex
public class GCPNotifier {

    // This is the method that the Flow will call. It must be an InvocableMethod.
    // It cannot do the callout directly because of the "uncommitted work" error.
    // Its only job is to call the future method.
    @InvocableMethod(label='Notify GCP Endpoint' description='Sends a record ID to the GCP function.')
    public static void startCallout(List<String> recordIds) {
        // Call the future method to perform the callout in a separate transaction.
        performCallout(recordIds);
    }

    // This is the future method that performs the actual HTTP callout.
    // It runs asynchronously, which solves the "uncommitted work pending" error.
    // It cannot be called directly by a Flow, which is why we need the method above.
    @future(callout=true)
    public static void performCallout(List<String> recordIds) {
        if (recordIds == null || recordIds.isEmpty()) {
            return;
        }
        String recordId = recordIds[0];
        HttpRequest req = new HttpRequest();
        req.setEndpoint('callout:GCP_Cloud_Function'); // <-- MAKE SURE THIS MATCHES YOUR NAMED CREDENTIAL
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json;charset=UTF-8');
        Map<String, String> bodyMap = new Map<String, String>{'recordId' => recordId};
        String jsonBody = JSON.serialize(bodyMap);
        req.setBody(jsonBody);
        Http http = new Http();
        try {
            HttpResponse res = http.send(req);
            System.debug('GCPNotifier: Callout response status code: ' + res.getStatusCode());
        } catch (System.CalloutException e) {
            System.debug('GCPNotifier: Callout error: ' + e.getMessage());
        }
    }
}
```
3. Click **"Save"**.

### 2.3. Create the Apex Test Class (`GCPNotifierTest.cls`)

1.  From Apex Classes, click **"New"** again.
2.  Paste the following code:

```apex
@isTest
private class GCPNotifierTest {

    // By implementing the HttpCalloutMock interface, we can create a custom mock response.
    // This is more robust than using StaticResourceCalloutMock.
    public class MockHttpResponse implements HttpCalloutMock {
        public HttpResponse respond(HttpRequest req) {
            // Create a fake response
            HttpResponse res = new HttpResponse();
            res.setHeader('Content-Type', 'application/json');
            res.setBody('{"status":"success"}');
            res.setStatusCode(200);
            return res;
        }
    }

    @isTest
    static void testNotifyGCP() {
        // Set the mock callout class
        Test.setMock(HttpCalloutMock.class, new MockHttpResponse());

        // The record ID to be sent in the test
        List<String> recordIds = new List<String>{'001xx000003DUM1AAG'};
        
        // Start the test context
        Test.startTest();
        
        // Call the InvocableMethod, which will in turn call the future method.
        GCPNotifier.startCallout(recordIds);
        
        // Stop the test context
        Test.stopTest();

        // By this point, the test has passed if no exceptions were thrown.
    }
}
```
3. Click **"Save"**.

### 2.4. Create the Record-Triggered Flow

1.  In Setup, search for **"Flows"** and click **"New Flow"**.
2.  Select **"Record-Triggered Flow"**.
3.  **Object**: Choose the object to monitor (e.g., `Account`).
4.  **Trigger**: Select **"A record is created or updated"**.
5.  **Optimize for**: Select **"Actions and Related Records"**.
6.  On the Flow canvas, click **"+"** and select **"Action"**.
7.  Search for your Apex action, which will be labeled **"Notify GCP Endpoint"**.
8.  **Label**: Give it a name like `Call GCP Notifier Apex`.
9.  **Set Input Values**:
    *   Find the **`recordIds`** parameter.
    *   Click the toggle to **"Include"**.
    *   For the value, enter **`{!$Record.Id}`**.
10. Click **"Done"**.
11. **Save** the flow, give it a name, and then **Activate** it.

Your integration is now fully configured.
