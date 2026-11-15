"""Populate the technical QuixBugs snapshot using its recorded file hashes."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile


DATA = Path(__file__).resolve().parents[1] / "data"


def snapshot_bytes(raw, expected, name):
    if hashlib.sha256(raw).hexdigest() == expected:
        return raw

    # The original Windows checkout used Git's CRLF conversion.
    windows = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    if hashlib.sha256(windows).hexdigest() == expected:
        return windows

    raise ValueError(f"QuixBugs checksum mismatch: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Read a ZIP archive of the pinned commit")
    args = parser.parse_args()
    provenance = json.loads((DATA / "provenance.json").read_text(encoding="utf-8"))
    inventory = provenance["files_sha256"]
    destination = DATA / "QuixBugs"

    missing = {}
    for name, expected in inventory.items():
        target = destination / name
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise SystemExit(f"Existing snapshot file differs from its manifest: {name}")
        else:
            missing[name] = expected

    if missing:
        commit = provenance["commit"]
        if args.archive:
            payload = args.archive.read_bytes()
        else:
            url = f"https://codeload.github.com/jkoppel/QuixBugs/zip/{commit}"
            with urllib.request.urlopen(url, timeout=60) as response:
                payload = response.read()

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = {
                name: snapshot_bytes(archive.read(f"QuixBugs-{commit}/{name}"), expected, name)
                for name, expected in missing.items()
            }

        for name, content in files.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(content)

    print(f"QuixBugs: verified {len(inventory)} files; fetched {len(missing)}.")


if __name__ == "__main__":
    main()
