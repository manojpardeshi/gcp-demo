import os.path
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying these SCOPES, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

def main():
    """Shows basic usage of the Gmail API.
    Lists the user's Gmail labels.
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)

    # Print the refresh token
    print("\n--- GMAIL API CREDENTIALS ---")
    print(f"Your Refresh Token is: {creds.refresh_token}")
    print("\nStore this value in Google Secret Manager with the name 'gmail-refresh-token'.")
    print("You should also store your client_id and client_secret from the credentials.json file.")
    print("-----------------------------\n")


if __name__ == '__main__':
    main()
