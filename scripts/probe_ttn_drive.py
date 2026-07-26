"""Probe Google Drive access for TTN folder."""
from __future__ import annotations

import os
import sys

from google.auth.transport.requests import AuthorizedSession

from bot.google_creds import load_google_credentials, service_account_email
from bot.ttn_drive import DRIVE_FILES, DRIVE_UPLOAD, day_folder_name, root_folder_id

os.environ.setdefault(
    "TTN_DRIVE_ROOT_FOLDER_ID", "1JKjgmAK_R6KHSH4GaMc6flwfP8MlGZg0"
)


def main() -> int:
    print("email:", service_account_email())
    print("root:", root_folder_id())
    session = AuthorizedSession(load_google_credentials())
    fid = root_folder_id()

    r = session.get(
        f"{DRIVE_FILES}/{fid}",
        params={
            "fields": "id,name,mimeType,capabilities,shared",
            "supportsAllDrives": "true",
        },
        timeout=30,
    )
    print("GET folder:", r.status_code, r.text[:1000])

    r2 = session.get(
        DRIVE_FILES,
        params={
            "q": f"'{fid}' in parents and trashed = false",
            "fields": "files(id,name,mimeType)",
            "pageSize": 10,
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        },
        timeout=30,
    )
    print("LIST children:", r2.status_code, r2.text[:1000])

    if r.status_code != 200:
        return 1

    # create day folder
    name = day_folder_name()
    meta = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [fid],
    }
    import json

    create = session.post(
        DRIVE_FILES,
        params={"fields": "id,name", "supportsAllDrives": "true"},
        headers={"Content-Type": "application/json; charset=UTF-8"},
        data=json.dumps(meta),
        timeout=30,
    )
    print("CREATE day folder:", create.status_code, create.text[:800])
    if create.status_code not in (200, 201):
        return 1
    day_id = create.json()["id"]

    from pathlib import Path

    from bot.ttn_drive import upload_pdf_bytes

    for p in [
        Path(r"c:\Users\brett\Downloads\1.pdf"),
        Path(r"c:\Users\brett\Downloads\2.pdf"),
        Path(r"c:\Users\brett\Downloads\3.pdf"),
    ]:
        data = p.read_bytes()
        print(p.name, "bytes", len(data), "pdf", data[:4])
        # upload into the created day folder explicitly
        up = upload_pdf_bytes(data, filename=f"test_{p.name}", folder_id=day_id)
        print("UP", up)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
