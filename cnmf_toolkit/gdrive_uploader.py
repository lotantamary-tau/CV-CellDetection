"""
Google Drive uploader for CNMFDebugTracker.

Uploads debug output files directly to a Google Drive folder using the
Google Drive REST API.  Works with either a **service-account** JSON key
file or an **OAuth 2.0 desktop** credentials file.

Setup
-----
1. ``pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib``
2. Create credentials at https://console.cloud.google.com/apis/credentials
   * Service account → download JSON key, set env var
     ``GDRIVE_SERVICE_ACCOUNT_KEY`` to its path.
   * *or* OAuth desktop app → download client-secret JSON, set env var
     ``GDRIVE_CLIENT_SECRET`` to its path (a browser window will open
     once for consent).
3. Set ``GDRIVE_FOLDER_ID`` to the target Google Drive folder's ID
   (the last part of the folder URL).
4. If using a service account, share the target folder with the
   service account email.

Environment variables
~~~~~~~~~~~~~~~~~~~~~
``GDRIVE_FOLDER_ID``            – (required) target folder ID on Google Drive
``GDRIVE_SERVICE_ACCOUNT_KEY``  – path to service-account JSON key
``GDRIVE_CLIENT_SECRET``        – path to OAuth client-secret JSON
``GDRIVE_TOKEN_PATH``           – where to cache the OAuth token
                                  (default: ``~/.cnmf_gdrive_token.json``)
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger("caiman")

# Scope: full access to files created/opened by the app
_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _build_service_from_service_account(key_path: str):
    """Authenticate with a service-account JSON key."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=_SCOPES
    )
    return build("drive", "v3", credentials=creds)


def _build_service_from_oauth(client_secret_path: str, token_path: str):
    """Authenticate with an OAuth 2.0 desktop-app flow (interactive)."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_path, _SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as tok:
            tok.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


class GDriveUploader:
    """Uploads local files to a Google Drive folder.

    Parameters
    ----------
    folder_id : str or None
        Google Drive folder ID.  Falls back to env var ``GDRIVE_FOLDER_ID``.
    service_account_key : str or None
        Path to service-account JSON key.  Falls back to
        ``GDRIVE_SERVICE_ACCOUNT_KEY``.
    client_secret : str or None
        Path to OAuth client-secret JSON.  Falls back to
        ``GDRIVE_CLIENT_SECRET``.
    token_path : str or None
        Where to cache the OAuth refresh token.  Falls back to
        ``GDRIVE_TOKEN_PATH`` or ``~/.cnmf_gdrive_token.json``.
    """

    def __init__(
        self,
        folder_id: str = None,
        service_account_key: str = None,
        client_secret: str = None,
        token_path: str = None,
    ):
        self.folder_id = folder_id or os.environ.get("GDRIVE_FOLDER_ID")
        if not self.folder_id:
            raise ValueError(
                "Google Drive folder ID is required.  Pass folder_id= or set "
                "the GDRIVE_FOLDER_ID environment variable."
            )

        sa_key = service_account_key or os.environ.get(
            "GDRIVE_SERVICE_ACCOUNT_KEY"
        )
        cs_path = client_secret or os.environ.get("GDRIVE_CLIENT_SECRET")
        self._token_path = token_path or os.environ.get(
            "GDRIVE_TOKEN_PATH",
            os.path.expanduser("~/.cnmf_gdrive_token.json"),
        )

        if sa_key:
            logger.info("GDriveUploader: using service-account key %s", sa_key)
            self._service = _build_service_from_service_account(sa_key)
        elif cs_path:
            logger.info(
                "GDriveUploader: using OAuth client secret %s", cs_path
            )
            self._service = _build_service_from_oauth(
                cs_path, self._token_path
            )
        else:
            raise ValueError(
                "No Google credentials found.  Set GDRIVE_SERVICE_ACCOUNT_KEY "
                "or GDRIVE_CLIENT_SECRET (see gdrive_uploader.py docstring)."
            )

        # Optional: create a session sub-folder so each run is separated
        self._subfolder_id = None

    # ------------------------------------------------------------------
    # public helpers
    # ------------------------------------------------------------------
    def create_session_folder(self, name: str) -> str:
        """Create a sub-folder inside the target folder for this run.

        Returns the ID of the new sub-folder.
        """
        meta = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [self.folder_id],
        }
        folder = (
            self._service.files()
            .create(body=meta, fields="id")
            .execute()
        )
        self._subfolder_id = folder["id"]
        logger.info(
            "GDriveUploader: created session folder '%s' (id=%s)",
            name,
            self._subfolder_id,
        )
        return self._subfolder_id

    def upload_file(self, local_path: str, remote_name: str = None) -> str:
        """Upload a single file and return its Google Drive file ID.

        Parameters
        ----------
        local_path : str
            Absolute or relative path to the local file.
        remote_name : str, optional
            Name to use on Google Drive.  Defaults to the local filename.

        Returns
        -------
        str
            The Google Drive file ID of the uploaded file.
        """
        from googleapiclient.http import MediaFileUpload

        local_path = str(local_path)
        if remote_name is None:
            remote_name = os.path.basename(local_path)

        parent = self._subfolder_id or self.folder_id

        file_meta = {"name": remote_name, "parents": [parent]}

        # Determine MIME type
        mime = "application/octet-stream"
        ext = os.path.splitext(local_path)[1].lower()
        mime_map = {
            ".npz": "application/x-npz",
            ".npy": "application/x-npy",
            ".png": "image/png",
            ".txt": "text/plain",
            ".json": "application/json",
            ".csv": "text/csv",
        }
        mime = mime_map.get(ext, mime)

        media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

        uploaded = (
            self._service.files()
            .create(body=file_meta, media_body=media, fields="id")
            .execute()
        )
        file_id = uploaded["id"]
        logger.info(
            "GDriveUploader: uploaded %s -> %s (id=%s)",
            local_path,
            remote_name,
            file_id,
        )
        return file_id

    def upload_directory(self, local_dir: str, delete_after: bool = False):
        """Upload every file in *local_dir* (non-recursive).

        Parameters
        ----------
        local_dir : str
            Path to the local directory.
        delete_after : bool
            If True, delete local files after successful upload to save
            disk space.
        """
        uploaded = []
        local_dir = Path(local_dir)
        for fpath in sorted(local_dir.iterdir()):
            if fpath.is_file():
                try:
                    fid = self.upload_file(str(fpath))
                    uploaded.append((str(fpath), fid))
                    if delete_after:
                        fpath.unlink()
                        logger.debug(
                            "GDriveUploader: deleted local file %s", fpath
                        )
                except Exception as e:
                    logger.error(
                        "GDriveUploader: failed to upload %s: %s", fpath, e
                    )
        return uploaded
