import os
import xml.etree.ElementTree as ET
from google.cloud import bigquery, secretmanager
from salesforce_api import Salesforce
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

def salesforce_trigger(request):
    """
    Cloud Function triggered by a Salesforce Outbound Message.
    """
    # 1. Parse the Salesforce Outbound Message
    # -----------------------------------------
    # The request body is a SOAP XML message. We need to parse it to get the
    # record ID of the object that was changed in Salesforce.

    # Placeholder for parsing logic
    record_id = parse_salesforce_notification(request)
    if not record_id:
        return 'Error: Could not parse record ID from notification.', 400

    # 2. Fetch credentials from Secret Manager
    # ----------------------------------------
    # Securely retrieve Salesforce and SendGrid credentials.

    # Placeholder for secret fetching logic
    secrets = get_secrets()
    sf_credentials = secrets['salesforce']
    sendgrid_api_key = secrets['sendgrid_api_key']

    # 3. Fetch detailed record data from Salesforce
    # ---------------------------------------------
    # Use the record ID to query the Salesforce API for the full record.

    # Placeholder for Salesforce API call
    sf = Salesforce(username=sf_credentials['username'], password=sf_credentials['password'], security_token=sf_credentials['token'])
    salesforce_data = sf.Account.get(record_id) # Example for 'Account' object

    if not salesforce_data:
        return f'Error: Could not retrieve data for record {record_id} from Salesforce.', 500

    # 4. Insert data into Google BigQuery
    # -----------------------------------
    # Transform the data and insert it into our BigQuery table.

    # Placeholder for BigQuery insertion logic
    insert_into_bigquery(salesforce_data)

    # 5. Send an email notification via SendGrid
    # ------------------------------------------
    # After a successful insertion, send a confirmation email.

    # Placeholder for email sending logic
    send_email_notification(sendgrid_api_key, salesforce_data)

    return 'Successfully processed Salesforce notification.', 200


def parse_salesforce_notification(request_data):
    """
    Parses the JSON payload from a Salesforce Flow HTTP Callout to extract the record ID.
    """
    try:
        # The request data from a Flow callout will be JSON.
        # We assume the Flow is configured to send a JSON body like: {"recordId": "001xx000003DHPGAA4"}
        notification_data = request_data.get_json()
        
        record_id = notification_data.get('recordId')

        if record_id:
            print(f"Successfully parsed record ID: {record_id}")
            return record_id
        else:
            print("Error: 'recordId' not found in the JSON payload.")
            return None
    except Exception as e:
        print(f"Error parsing JSON payload: {e}")
        return None

def get_secrets():
    """
    Retrieves secrets from Google Secret Manager.
    """
    # Initialize the Secret Manager client.
    client = secretmanager.SecretManagerServiceClient()

    # Your GCP project ID.
    project_id = os.environ.get("GCP_PROJECT")

    # Names of the secrets to fetch.
    # These should be created in Secret Manager beforehand.
    secret_names = {
        "salesforce_username": "salesforce-username",
        "salesforce_password": "salesforce-password",
        "salesforce_token": "salesforce-token",
        "sendgrid_api_key": "sendgrid-api-key"
    }

    secrets = {}
    try:
        for key, secret_id in secret_names.items():
            # Construct the full secret resource name.
            resource_name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
            
            # Access the secret version.
            response = client.access_secret_version(request={"name": resource_name})
            
            # Decode the secret payload.
            secrets[key] = response.payload.data.decode("UTF-8")

        print("Successfully fetched all secrets.")
        return {
            "salesforce": {
                "username": secrets["salesforce_username"],
                "password": secrets["salesforce_password"],
                "token": secrets["salesforce_token"]
            },
            "sendgrid_api_key": secrets["sendgrid_api_key"]
        }
    except Exception as e:
        print(f"Error fetching secrets: {e}")
        return None

def insert_into_bigquery(data):
    """
    Inserts a row into the specified BigQuery table.
    """
    # Initialize the BigQuery client.
    client = bigquery.Client()

    # Get project, dataset, and table from environment variables.
    project_id = os.environ.get("GCP_PROJECT")
    dataset_id = os.environ.get("BIGQUERY_DATASET")
    table_id = os.environ.get("BIGQUERY_TABLE")

    # Construct the full table reference.
    table_ref = client.dataset(dataset_id, project=project_id).table(table_id)
    table = client.get_table(table_ref)

    # The data should be a list of dictionaries (or a single dictionary).
    # Here, we assume 'data' is a dictionary representing a single row.
    rows_to_insert = [data]

    try:
        # Make an API request to insert the rows.
        errors = client.insert_rows_json(table, rows_to_insert)
        
        if errors == []:
            print("New rows have been added to BigQuery.")
        else:
            print(f"Encountered errors while inserting rows: {errors}")
            
    except Exception as e:
        print(f"Error inserting data into BigQuery: {e}")

def send_email_notification(api_key, data):
    """
    Sends an email using the SendGrid API.
    """
    # Initialize the SendGrid client.
    sg = SendGridAPIClient(api_key)

    # Get email details from environment variables.
    from_email = os.environ.get("FROM_EMAIL")
    to_emails = os.environ.get("TO_EMAILS", "").split(",")

    # Construct the email message.
    subject = f"New Salesforce Record Created/Updated: {data.get('Name', 'N/A')}"
    html_content = f"""
    <h3>A Salesforce record has been processed and added to BigQuery.</h3>
    <p><strong>Record Name:</strong> {data.get('Name', 'N/A')}</p>
    <p><strong>Record ID:</strong> {data.get('Id', 'N/A')}</p>
    <p><strong>Industry:</strong> {data.get('Industry', 'N/A')}</p>
    <p><strong>Phone:</strong> {data.get('Phone', 'N/A')}</p>
    """

    message = Mail(
        from_email=from_email,
        to_emails=to_emails,
        subject=subject,
        html_content=html_content
    )

    try:
        # Send the email.
        response = sg.send(message)
        print(f"Email sent with status code: {response.status_code}")
    except Exception as e:
        print(f"Error sending email: {e}")
