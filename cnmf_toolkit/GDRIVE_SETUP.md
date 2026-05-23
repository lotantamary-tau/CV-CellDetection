# Google Drive Upload for CNMF Debug Tracker

## Overview
The debug tracker can automatically upload all saved files (`.npz`, `.png`, `.txt`) directly to Google Drive after each pipeline stage.

## Quick Setup (5 minutes)

### 1. Install the required packages
```bash
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

### 2. Create Google Cloud credentials

**Option A – Service Account (recommended for automated/headless use):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or use an existing one)
3. Enable the **Google Drive API**: APIs & Services → Library → search "Google Drive API" → Enable
4. Create a service account: APIs & Services → Credentials → Create Credentials → Service Account
5. Download the JSON key file

**Option B – OAuth Desktop App (interactive, opens a browser once):**
1. Same steps 1-3 above
2. Create an OAuth 2.0 Client ID: APIs & Services → Credentials → Create Credentials → OAuth Client ID → Desktop App
3. Download the client-secret JSON

### 3. Get your Google Drive folder ID
1. Open Google Drive in your browser
2. Navigate to (or create) the folder where you want debug files saved
3. Copy the folder ID from the URL:
   ```
   https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
                                           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                           This is your folder ID
   ```
4. **If using a service account**, right-click the folder → Share → add the service account email (from the JSON key file, looks like `name@project.iam.gserviceaccount.com`)

### 4. Set environment variables
```bash
# Required
export GDRIVE_FOLDER_ID="1AbCdEfGhIjKlMnOpQrStUvWxYz"

# Option A: service account
export GDRIVE_SERVICE_ACCOUNT_KEY="/path/to/service-account-key.json"

# Option B: OAuth
export GDRIVE_CLIENT_SECRET="/path/to/client-secret.json"
```

## Usage

Once the environment variables are set, the debug tracker will **automatically** upload files:

```python
from cnmf_toolkit.debug_tracker import CNMFDebugTracker

# Files are saved locally AND uploaded to Google Drive
tracker = CNMFDebugTracker(enabled=True)
```

Or pass credentials explicitly:

```python
tracker = CNMFDebugTracker(
    enabled=True,
    gdrive_folder_id="1AbCdEfGhIjKlMnOpQrStUvWxYz",
    gdrive_service_account_key="/path/to/key.json",
    # gdrive_delete_local=True,  # delete local copies after upload
)
```

### Saving disk space
If the debug files are too large to keep locally, set `gdrive_delete_local=True` to delete each file after it's uploaded:

```python
tracker = CNMFDebugTracker(
    enabled=True,
    gdrive_delete_local=True,  # removes local files after successful upload
)
```

## What gets uploaded
Each run creates a timestamped sub-folder in your Google Drive folder, mirroring the local `data/results/debug_outputs/run_<TS>/<phase>/` layout. Stage files use plain names (no `_N` counter) because the per-phase subfolder discriminates between fit and refit:
```
cnmf_debug_20260214_153042/
    init.npz
    metadata_init.txt
    ROI_0_init.png
    ROI_1_init.png
    ...
    YrA_traces_init.png
    spatial_1.npz
    ...
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `No module named 'googleapiclient'` | `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` |
| `Google Drive upload requested but setup failed` | Check that your env vars are set and the JSON key file exists |
| Files don't appear in Drive | If using a service account, make sure the folder is shared with the service account email |
| `HttpError 403` | Enable the Google Drive API in the Cloud Console |
