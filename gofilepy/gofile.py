#!/usr/bin/env python3
# coding: utf-8

import argparse
import json
import mimetypes
import os
import sys
import time
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Optional

import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder, MultipartEncoderMonitor
from tqdm import tqdm
from rich import print as rprint
from rich.panel import Panel


def upload(file: str, best_server: str, folder_id: Optional[str] = None):
    f_obj = Path(file)
    file_size = f_obj.stat().st_size  # Taille du fichier
    upload_url = f"https://{best_server}.gofile.io/uploadFile"
    
    print(f"Upload de {f_obj.name} :")
    with open(f_obj, "rb") as f:
        with tqdm(
            total=file_size,
            unit="B",
            unit_scale=True,
            desc=f"Progression...",
        ) as progress:
            # Fonction de callback pour suivre la progression
            def progress_callback(monitor):
                progress.update(monitor.bytes_read - progress.n)

            # Préparation du téléversement avec suivi
            content_type = mimetypes.guess_type(f_obj)[0] or "application/octet-stream"
            encoder = MultipartEncoder(
                fields={
                    "file": (f_obj.name, f, content_type),
                    "token": os.getenv("GOFILE_TOKEN"),
                    "folderId": folder_id,
                }
            )
            monitor = MultipartEncoderMonitor(encoder, progress_callback)
            headers = {"Content-Type": monitor.content_type}

            # Envoi de la requête
            try:
                response = requests.post(upload_url, data=monitor, headers=headers)
                response.raise_for_status() 
                print(f"Upload terminé : {f_obj.name}")
            except requests.exceptions.RequestException as e:
                rprint(f"[red]Erreur de connexion :[/red] {e}")
                sys.exit(1)

    return response


def gofile_upload(
    path: list,
    to_single_folder: bool = False,
    verbose: bool = False,
    export: bool = False,
    open_urls: bool = False,
    existing_folder_id: Optional[str] = None
):
    get_server = requests.get("https://api.gofile.io/servers")
    servers = get_server.json()
    best_server = servers["data"]["servers"][0]["name"]

    files = []
    for _path in path:
        if not Path(_path).exists():
            rprint(
                f'[red]ERROR: [dim blue]"{Path(_path).absolute()}"[/dim blue] '
                "does not exist! [/red]"
            )
            continue
        if Path(_path).is_dir():
            dir_items = glob(str(Path(f"{_path}/**/*")), recursive=True)
            local_files = [x for x in dir_items if not Path(x).is_dir()]
            files.append(local_files)
        else:
            files.append([_path])

    files = sum(files, [])
    export_data = []
    urls = []
    folder_id = existing_folder_id

    if to_single_folder:
        if not os.getenv("GOFILE_TOKEN"):
            rprint(
                "[red]ERROR: Gofile token is required when passing "
                "`--to-single-folder`![/red]\n[dim red]You can find your "
                "account token on this page: "
                "[u][blue]https://gofile.io/myProfile[/blue][/u]\nCopy it "
                "then export it as `GOFILE_TOKEN`. For example:\n"
                "export GOFILE_TOKEN='xxxxxxxxxxxxxxxxx'[/dim red]"
            )
            sys.exit(1)

    for file in files:
        upload_resp = upload(file, best_server, folder_id).json()
        if to_single_folder and os.getenv("GOFILE_TOKEN") and folder_id is None:
            folder_id = upload_resp["data"]["parentFolder"]

        ts = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        file_abs = str(Path(file).absolute())
        record = {"file": file_abs, "timestamp": ts, "response": upload_resp}
        url = upload_resp["data"]["downloadPage"]
        urls.append(url)

        if verbose:
            rprint(Panel(json.dumps(record, indent=2)))
        elif not to_single_folder:
            rprint(
                Panel.fit(
                    f"[yellow]File:[/yellow] [blue]{file}[/blue]\n"
                    f"[yellow]Download page:[/yellow] [u][blue]{url}[/blue][/u]"
                )
            )

        if export:
            export_data.append(record)

    if not urls:
        sys.exit()

    if to_single_folder:
        files = "\n".join([str(Path(x).absolute()) for x in files])
        rprint(
            Panel.fit(
                f"[yellow]Files:[/yellow]\n[blue]{files}[/blue]\n"
                "[yellow]Download page:[/yellow] "
                f"[u][blue]{urls[0]}[/blue][/u]"
            )
        )

    if export:
        export_fname = f"gofile_export_{int(time.time())}.json"
        with open(export_fname, "w") as j:
            json.dump(export_data, j, indent=4)
        rprint("[green]Exported data to:[/green] " f"[magenta]{export_fname}[/magenta]")

    return urls


def opts():
    parser = argparse.ArgumentParser(
        description="Example: gofile <file/folder_path>"
    )
    parser.add_argument(
        "-s",
        "--to-single-folder",
        help=(
            "Upload multiple files to the same folder. All files will share the "
            "same URL. This option requires a valid token exported as: "
            "`GOFILE_TOKEN`"
        ),
        action="store_true",
    )
    parser.add_argument(
        "-f",
        "--folder-id",
        help="ID of an existing Gofile folder into which to upload files",
        type=str,
        default=None,
    )
    parser.add_argument(
        "-o",
        "--open-urls",
        help="Open the URL(s) in the browser when the upload is complete (macOS-only)",
        action="store_true",
    )
    parser.add_argument(
        "-e",
        "--export",
        help="Export upload response(s) to a JSON file",
        action="store_true",
    )
    parser.add_argument(
        "-vv", "--verbose", help="Show more information", action="store_true"
    )
    parser.add_argument(
        "path", nargs="+", help="Path to the file(s) and/or folder(s)"
    )
    return parser.parse_args()


def main():
    args = opts()
    gofile_upload(
        path=args.path,
        to_single_folder=args.to_single_folder,
        verbose=args.verbose,
        export=args.export,
        open_urls=args.open_urls,
        existing_folder_id=args.folder_id
    )


if __name__ == "__main__":
    main()

