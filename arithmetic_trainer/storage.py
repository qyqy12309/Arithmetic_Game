"""CSV persistence for question records."""

import csv
from datetime import datetime
from pathlib import Path
import re


FIELDNAMES = (
    "session_id",
    "question_number",
    "operation",
    "first_number",
    "second_number",
    "correct_answer",
    "response_seconds",
    "outcome",
    "correction_edits",
    "clean_solve",
    "session_duration_seconds",
)

SESSION_FILENAME = re.compile(r"^session_(\d+)\.csv$")
LEGACY_DAILY_FILENAME = re.compile(r"^history_(\d{4}-\d{2}-\d{2})\.csv$")


def _local_date(now=None):
    local_now = now if now is not None else datetime.now().astimezone()
    return local_now.date().isoformat()


def _session_number(path):
    match = SESSION_FILENAME.fullmatch(path.name)
    return int(match.group(1)) if match else None


def create_session_file(directory="history", now=None):
    """Create and return the next numbered session CSV for the local date."""
    date_directory = Path(directory) / _local_date(now)
    date_directory.mkdir(parents=True, exist_ok=True)

    existing_numbers = [
        number
        for path in date_directory.iterdir()
        if path.is_file() and (number := _session_number(path)) is not None
    ]
    next_number = max(existing_numbers, default=0) + 1

    # Exclusive creation prevents an existing session from being overwritten.
    while True:
        path = date_directory / f"session_{next_number}.csv"
        try:
            with path.open("x", newline="", encoding="utf-8") as csv_file:
                csv.DictWriter(csv_file, fieldnames=FIELDNAMES).writeheader()
            return path
        except FileExistsError:
            next_number += 1


def get_latest_session(directory="history"):
    """Return the newest date folder's highest-numbered session, or ``None``."""
    directory = Path(directory)
    if not directory.is_dir():
        return None

    date_directories = []
    for path in directory.iterdir():
        if not path.is_dir():
            continue
        try:
            datetime.strptime(path.name, "%Y-%m-%d")
        except ValueError:
            continue
        date_directories.append(path)

    for date_directory in sorted(date_directories, key=lambda path: path.name, reverse=True):
        numbered_sessions = [
            (number, path)
            for path in date_directory.iterdir()
            if path.is_file() and (number := _session_number(path)) is not None
        ]
        if numbered_sessions:
            return max(numbered_sessions, key=lambda item: item[0])[1]
    return None


def _history_sort_key(path):
    """Sort both current and legacy history layouts chronologically."""
    session_number = _session_number(path)
    if session_number is not None:
        try:
            datetime.strptime(path.parent.name, "%Y-%m-%d")
        except ValueError:
            pass
        else:
            return path.parent.name, session_number, path.name

    legacy_match = LEGACY_DAILY_FILENAME.fullmatch(path.name)
    if legacy_match:
        return legacy_match.group(1), 0, path.name
    return "", 0, str(path)


def append_records(path, records):
    """Append records, adding a header when the file is new or empty."""
    records = list(records)
    if not records:
        return

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not path.exists() or path.stat().st_size == 0

    with path.open("a", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES, extrasaction="ignore")
        if needs_header:
            writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in FIELDNAMES})


def read_records(path):
    path = Path(path)
    if path.is_dir():
        records = []
        for csv_path in sorted(path.rglob("*.csv"), key=_history_sort_key):
            records.extend(read_records(csv_path))
        return records
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))
