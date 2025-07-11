# Project Setup: Salesforce to GCP Integration

This document provides a step-by-step guide to configure the integration between Salesforce and Google Cloud Platform. The goal is to capture changes in Salesforce records, process them in a Google Cloud Function, store them in BigQuery, and send an email notification.

## Architecture Overview

1.  **Salesforce**: A Record-Triggered Flow detects a record change (create/update).
2.  **Apex Callout**: The Flow calls an Apex class that makes an HTTP POST request.
3.  **Google Cloud Function**: An HTTP-triggered function receives the request from Salesforce.
4.  **Google Secret Manager**: The function securely retrieves credentials for Salesforce and SendGrid.
5.  **Salesforce API**: The function uses the record ID to fetch the full record details from Salesforce.
6.  **Google BigQuery**: The function inserts the record data into a BigQuery table.
7.  **SendGrid**: Upon successful insertion, the function sends an email notification.

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

### 1.2. Configure Secret Manager

1.  In the GCP Console, navigate to **Secret Manager**.
2.  Enable the API if it's not already enabled.
3.  Create the following secrets, storing the corresponding values:
    *   `salesforce-username`: Your Salesforce username.
    *   `salesforce-password`: Your Salesforce password concatenated with your security token.
    *   `salesforce-token`: Your Salesforce security token.
    *   `sendgrid-api-key`: Your SendGrid API key.

### 1.3. Deploy the Cloud Function

1.  Ensure you have the `gcloud` CLI installed and authenticated.
2.  Navigate to the root directory of this project (`gcp-demo`).
3.  Run the following command, replacing the placeholder values:

```bash
gcloud functions deploy salesforce-trigger \
--runtime python39 \
--trigger-http \
--source cloud_function \
--entry-point salesforce_trigger \
--set-env-vars GCP_PROJECT=your-gcp-project-id,BIGQUERY_DATASET=your-dataset-id,BIGQUERY_TABLE=your-table-id,FROM_EMAIL=sender@example.com,TO_EMAILS=recipient1@example.com
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
    @InvocableMethod(label='Notify GCP Endpoint' description='Sends a record ID to the GCP function.')
    public static void notifyGCP(List<String> recordIds) {
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
    @isTest
    static void testNotifyGCP() {
        StaticResourceCalloutMock mock = new StaticResourceCalloutMock();
        mock.setStatusCode(200);
        mock.setHeader('Content-Type', 'application/json');
        mock.setBody('{"status":"success"}');
        Test.setMock(HttpCalloutMock.class, mock);
        List<String> recordIds = new List<String>{'001xx000003DUM1AAG'};
        Test.startTest();
        GCPNotifier.notifyGCP(recordIds);
        Test.stopTest();
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
