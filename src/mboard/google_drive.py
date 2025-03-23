from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2.credentials import Credentials
import io
import os

class GoogleDriveClient:
    def __init__(self, credentials: Credentials):
        self.service = build('drive', 'v3', credentials=credentials)

    def list_files_in_folder(self, folder_id: str):
        query = f"'{folder_id}' in parents and trashed=false"
        results = self.service.files().list(q=query, fields="files(id, name)").execute()
        return results.get('files', [])

    def download_file(self, file_id: str, destination: str):
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(destination, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print(f"Download {int(status.progress() * 100)}%.")

# Example usage:
# creds = Credentials.from_authorized_user_file('path/to/credentials.json')
# drive_client = GoogleDriveClient(creds)
# files = drive_client.list_files_in_folder('your-folder-id')
# for file in files:
#     print(f"Downloading {file['name']}...")
#     drive_client.download_file(file['id'], os.path.join('path/to/download', file['name']))