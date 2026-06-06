#!/usr/bin/env python3
"""
datastore_sync.py
-----------------
Incremental sync of London Datastore (DataPress) files into a local
enrichment store for the smart ticketing system.

Strategy (matches the "nightly sync" pattern in the data inventory):
  1. Pull the catalogue's resources table (one CSV listing every file).
  2. Keep only files belonging to the datasets we care about.
  3. Diff each file against a local manifest by content hash
     (falling back to timestamp+size). Download ONLY what changed.
  4. Re-write the manifest.

No API key is required for public data. Do not scrape pages — this uses
the sanctioned export endpoint.

DataPress API v4.0. Endpoint shapes:
  catalogue (files) : {BASE}/api/v3/datasets/export.resources.csv
  one dataset (JSON): {BASE}/api/v3/dataset/{id}

NOTE ON COLUMNS: the exact CSV header is resolved at runtime and printed on
the first run. The expected DataPress resource fields are url, filename,
hash, size, timestamp and dataset; the resolver below maps common aliases.
Verify the printed mapping once against the live file, then trust it.

Usage:
  python datastore_sync.py                      # sync the default target IDs
  python datastore_sync.py --all                # sync every file in the catalogue
  python datastore_sync.py --ids 2n8zy exy3m    # sync specific dataset IDs
  python datastore_sync.py --store ./enrichment --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE = "https://data.london.gov.uk"
RESOURCES_CSV = f"{BASE}/api/v3/datasets/export.resources.csv"

# Dataset IDs from the build-ready inventory (the 5-char code at the end of
# each dataset page URL). Trim or extend as the system's needs change.
DEFAULT_TARGET_IDS = [
    "24rz6",  # Public Transport Accessibility Levels (PTAL)
    "2l15g",  # Indices of Deprivation 2019
    "2n8zy",  # LSOA Atlas
    "exprl",  # Ward Profiles and Atlas
    "2yjnq",  # Pedal Cyclist Casualties, KSI
    "exy3m",  # MPS Recorded Crime: Geographic Breakdown
    "e5n6w",  # MPS Monthly Crime Dashboard Data
    "2kdpj",  # LAEI 2022 Borough Air Quality (LLAQM)
    "e758q",  # LAEI 2019
    "vd67o",  # Household Waste Recycling Rates, Borough
]

# Map normalised CSV header names -> the field we need. First match wins.
COLUMN_ALIASES = {
    "dataset": ["dataset", "dataset_id", "datasetid", "package", "parent"],
    "url": ["url", "permalink", "download", "download_url", "downloadurl", "link", "web_page"],
    "filename": ["filename", "file_name", "name", "title"],
    "hash": ["hash", "md5", "checksum", "etag"],
    "size": ["size_(bytes)", "size", "bytes", "filesize", "content_length"],
    "timestamp": ["timestamp", "uploaded_at", "updated", "updatedat", "modified", "uploaded"],
    "resource_id": ["id", "resource_id", "resourceid", "rid"],
}

USER_AGENT = "ticketing-enrichment-sync/1.0 (+council data pipeline)"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def http_get(url: str, timeout: int = 60) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_resources_csv() -> list[dict]:
    log(f"Fetching catalogue file list: {RESOURCES_CSV}")
    raw = http_get(RESOURCES_CSV).decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    log(f"Catalogue lists {len(rows)} files.")
    return rows


def resolve_columns(sample_row: dict) -> dict:
    """Return {logical_field: actual_header} using the alias table."""
    norm = {h.lower().strip().replace(" ", "_"): h for h in sample_row.keys()}
    mapping: dict[str, str | None] = {}
    for field, aliases in COLUMN_ALIASES.items():
        mapping[field] = next((norm[a] for a in aliases if a in norm), None)
    log("Resolved CSV columns (verify once against the live file):")
    for field, header in mapping.items():
        log(f"    {field:<12} -> {header}")
    missing = [f for f in ("dataset", "url") if not mapping[f]]
    if missing:
        raise SystemExit(
            f"ERROR: could not find required column(s) {missing}. "
            f"Headers seen: {list(sample_row.keys())}"
        )
    return mapping


def get(row: dict, mapping: dict, field: str, default: str = "") -> str:
    header = mapping.get(field)
    return (row.get(header) or default).strip() if header else default


def file_signature(row: dict, mapping: dict) -> str:
    """A change-detection key: prefer hash, else timestamp+size."""
    h = get(row, mapping, "hash")
    if h:
        return f"hash:{h}"
    return f"ts:{get(row, mapping, 'timestamp')}|size:{get(row, mapping, 'size')}"


def safe_name(dataset_id: str, filename: str, resource_id: str) -> str:
    keep = "-_.() "
    clean = "".join(c if c.isalnum() or c in keep else "_" for c in filename).strip()
    clean = clean or f"{resource_id or 'file'}.dat"
    return f"{dataset_id}__{clean}"


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def download(url: str, dest: Path, dry_run: bool) -> int:
    if dry_run:
        return 0
    data = http_get(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def sync(target_ids: set[str] | None, store: Path, dry_run: bool) -> None:
    store.mkdir(parents=True, exist_ok=True)
    manifest_path = store / "_manifest.json"
    manifest = load_manifest(manifest_path)

    rows = fetch_resources_csv()
    if not rows:
        log("Nothing in catalogue. Exiting.")
        return
    mapping = resolve_columns(rows[0])

    changed = downloaded_bytes = skipped = 0
    new_manifest: dict[str, dict] = {}

    for row in rows:
        ds = get(row, mapping, "dataset")
        if target_ids is not None and ds not in target_ids:
            continue
        url = get(row, mapping, "url")
        if not url:
            continue
        rid = get(row, mapping, "resource_id")
        fname = get(row, mapping, "filename") or f"{rid}.dat"
        key = f"{ds}/{rid or fname}"
        sig = file_signature(row, mapping)
        local_name = safe_name(ds, fname, rid)
        dest = store / ds / local_name

        prev = manifest.get(key)
        if prev and prev.get("sig") == sig and dest.exists():
            skipped += 1
            new_manifest[key] = prev
            continue

        try:
            n = download(url, dest, dry_run)
            changed += 1
            downloaded_bytes += n
            log(f"{'WOULD GET' if dry_run else 'GET'} {key}  ({fname})")
        except (HTTPError, URLError) as e:
            log(f"  ! failed {key}: {e}")
            if prev:
                new_manifest[key] = prev
            continue

        new_manifest[key] = {
            "sig": sig,
            "url": url,
            "filename": fname,
            "path": str(dest.relative_to(store)),
            "size": get(row, mapping, "size"),
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        time.sleep(0.2)  # be polite to the server

    # Preserve manifest entries for non-targeted datasets so a scoped run
    # does not wipe the record of files synced in a previous broader run.
    for key, meta in manifest.items():
        new_manifest.setdefault(key, meta)

    if not dry_run:
        manifest_path.write_text(json.dumps(new_manifest, indent=2, sort_keys=True))

    log("-" * 48)
    log(f"Changed/new : {changed}")
    log(f"Unchanged   : {skipped}")
    log(f"Downloaded  : {downloaded_bytes/1_048_576:.2f} MB"
        + ("  (dry run, nothing written)" if dry_run else ""))
    log(f"Store       : {store.resolve()}")


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description="Incremental London Datastore sync.")
    p.add_argument("--store", default="./enrichment_store", type=Path,
                   help="Local directory for downloaded files (default ./enrichment_store)")
    p.add_argument("--ids", nargs="*", default=None,
                   help="Dataset IDs to sync (default: built-in target list)")
    p.add_argument("--all", action="store_true",
                   help="Sync every file in the catalogue (ignores --ids)")
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would change without downloading")
    args = p.parse_args(argv)

    if args.all:
        targets = None
    elif args.ids:
        targets = set(args.ids)
    else:
        targets = set(DEFAULT_TARGET_IDS)

    log("DataPress enrichment sync starting"
        + (" (DRY RUN)" if args.dry_run else ""))
    log(f"Targets: {'ALL' if targets is None else ', '.join(sorted(targets))}")
    try:
        sync(targets, args.store, args.dry_run)
    except KeyboardInterrupt:
        log("Interrupted.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
