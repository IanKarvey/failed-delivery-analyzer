"""
Core logic for the Failed Delivery and Redelivery Pattern Analyzer (terminal version).

File handling (the csv module), validation and all the analysis live here. The menu in
delivery_console.py and the charts in delivery_charts.py only call these functions.

Data model
  * delivery_records.csv has one row per delivery ATTEMPT.
  * The same Delivery ID appears again when a delivery needs a redelivery.
  * A delivery's outcome is the Final Status of its LATEST attempt.
  * A "failed attempt" is an attempt that has a failure reason (or status Failed).
"""

import csv
import os
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

APP_NAME = "Delivery-Analyzer-Terminal"


def _program_folder():
    """The folder the program lives in."""
    return os.path.dirname(os.path.abspath(__file__))


def _is_writable(folder):
    try:
        probe = os.path.join(folder, ".write_test")
        with open(probe, "w"):
            pass
        os.remove(probe)
        return True
    except OSError:
        return False


def _data_folder():
    """Where the CSV and the error log are saved: the program folder, or, if Windows
    does not allow writing there (e.g. Program Files), a folder in the user's AppData."""
    folder = _program_folder()
    if _is_writable(folder):
        return folder
    fallback = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), APP_NAME)
    os.makedirs(fallback, exist_ok=True)
    return fallback


BASE_DIR = _program_folder()
DATA_DIR = _data_folder()
DATA_FILE = os.path.join(DATA_DIR, "delivery_records.csv")
LOG_FILE = os.path.join(DATA_DIR, "error_log.txt")
SAMPLE_FILE = os.path.join(BASE_DIR, "sample_data", "delivery_records.csv")  # first-run data

FIELDS = [
    "Delivery ID", "Delivery Date", "Delivery Area",
    "Attempt Number", "Failure Reason", "Final Status",
]
DATE_FORMAT = "%Y-%m-%d"
MIN_DATE, MAX_DATE = date(2000, 1, 1), date(2100, 12, 31)  # anything else is a typo
MAX_FILLED_DAYS = 400  # the trend lists empty days as zeros up to this many days apart

SUCCESSFUL, FAILED, PENDING = "Successful", "Failed", "Pending"
STATUSES = [SUCCESSFUL, FAILED, PENDING]

NO_REASON = "None"
NOT_SPECIFIED = "Not specified"
COMMON_REASONS = ["Recipient unavailable", "Incorrect address", "Delivery postponed"]


# ------------------------------------------------------------------ records --
@dataclass
class Attempt:
    """One row of the CSV file: a single delivery attempt."""
    delivery_id: str
    day: date
    area: str
    attempt: int
    reason: str
    status: str

    @property
    def is_failed_attempt(self):
        return self.status == FAILED or self.reason != NO_REASON

    @property
    def reason_label(self):
        return self.reason if self.reason != NO_REASON else NOT_SPECIFIED

    def to_row(self):
        return [self.delivery_id, self.day.strftime(DATE_FORMAT), self.area,
                self.attempt, self.reason, self.status]


class ValidationError(Exception):
    """Raised with a list of messages that are safe to show to the user."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


def clean(text):
    return " ".join(str(text).split())


def plural(count, word):
    """plural(2, "delivery") -> "2 deliveries"; plural(1, "attempt") -> "1 attempt"."""
    if count == 1:
        return f"{count} {word}"
    return f"{count} {word[:-1] + 'ies' if word.endswith('y') else word + 's'}"


def format_percent(value):
    """60.0 -> '60%', 66.666 -> '66.7%'"""
    return f"{value:.1f}".rstrip("0").rstrip(".") + "%"


def parse_date(text):
    """'2026-10-01' -> date. Raises ValueError with a message that can be shown to the user."""
    try:
        day = datetime.strptime(clean(text), DATE_FORMAT).date()
    except ValueError:
        raise ValueError("Date must use the format YYYY-MM-DD (example: 2026-10-01).") from None
    if not MIN_DATE <= day <= MAX_DATE:
        raise ValueError(f"Date must be between {MIN_DATE} and {MAX_DATE}.")
    return day


def match_case(value, options):
    """Return the option equal to value ignoring case, else value unchanged."""
    for option in options:
        if option.lower() == value.lower():
            return option
    return value


def make_attempt(delivery_id, day_text, area, attempt_text, reason, status, areas=(), reasons=()):
    """Turn typed text into an Attempt (tidying spaces and capital letters), or raise ValidationError."""
    errors = []
    reason = clean(reason) or NO_REASON
    if reason.lower() == NO_REASON.lower():
        reason = NO_REASON
    try:
        day = parse_date(day_text)
    except ValueError as error:
        errors.append(str(error))
    try:
        number = int(clean(attempt_text))
    except ValueError:
        errors.append("Attempt number must be a whole number.")
    if errors:
        raise ValidationError(errors)
    return Attempt(
        delivery_id=clean(delivery_id).upper(),
        day=day,
        area=match_case(clean(area), areas),
        attempt=number,
        reason=match_case(reason, list(reasons) + [NO_REASON]),
        status=match_case(clean(status), STATUSES),
    )


def successful_attempt(records, delivery_id):
    """The attempt that delivered `delivery_id` successfully, or None."""
    wanted = clean(delivery_id).upper()
    return next((r for r in records if r.delivery_id == wanted and r.status == SUCCESSFUL), None)


def validate(record, records, editing=None):
    """Return a list of problems with `record` (empty list = OK).

    `editing` is the existing record being replaced, so it is ignored when
    checking for duplicates. Adding (editing=None) also blocks new attempts
    for a delivery that was already completed.
    """
    found = []
    if not record.delivery_id:
        found.append("Delivery ID is required.")
    if not record.area:
        found.append("Delivery area is required.")
    if record.attempt < 1:
        found.append("Attempt number must be 1 or more.")
    if record.status not in STATUSES:
        found.append("Choose a final status: " + ", ".join(STATUSES) + ".")
    elif record.status == SUCCESSFUL and record.reason != NO_REASON:
        found.append("A successful attempt cannot have a failure reason (use None).")
    elif record.status == FAILED and record.reason == NO_REASON:
        found.append("A failed attempt needs a failure reason.")

    same = [r for r in records if r is not editing and r.delivery_id == record.delivery_id]
    if any(r.attempt == record.attempt for r in same):
        found.append(f"{record.delivery_id} already has an attempt number {record.attempt}.")
    if editing is None:
        done = successful_attempt(same, record.delivery_id)
        if done:
            found.append(f"{record.delivery_id} was already delivered successfully "
                         f"(attempt {done.attempt}), so no more attempts can be added.")
    else:  # an edit must not leave an attempt behind a successful one
        every = same + [record]
        won = [r.attempt for r in every if r.status == SUCCESSFUL]
        if won and max(r.attempt for r in every) > min(won):
            found.append(f"Attempt {min(won)} of {record.delivery_id} succeeded, so it must be the last "
                         "attempt of that delivery.")
    return found


# ------------------------------------------------------------ file handling --
def create_file_if_missing(path=DATA_FILE, seed=None):
    """Create the CSV if it is missing or empty: a copy of the `seed` file (the sample
    records) when one is given, otherwise just the header row."""
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    if seed and os.path.exists(seed):
        shutil.copyfile(seed, path)
        return True
    with open(path, "w", newline="", encoding="utf-8") as file:
        csv.writer(file).writerow(FIELDS)
    return True


def log_error(text):
    """Append an error report to error_log.txt and return the file's path."""
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as file:
            file.write(f"--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n{text}\n")
    except OSError:
        pass
    return LOG_FILE


def _read_rows(path):
    """The rows of the CSV file, and whether it was in the older Windows-1252 text format
    (Excel's plain "CSV (Comma delimited)" saves accented letters that way)."""
    try:
        with open(path, newline="", encoding="utf-8-sig") as file:  # -sig: Excel BOM
            return list(csv.DictReader(file)), False
    except UnicodeDecodeError:
        with open(path, newline="", encoding="cp1252", errors="replace") as file:
            return list(csv.DictReader(file)), True


def _load(path):
    create_file_if_missing(path)
    rows, legacy = _read_rows(path)
    records, skipped = [], 0
    for row in rows:
        try:
            reason = clean(row["Failure Reason"]) or NO_REASON
            record = Attempt(
                delivery_id=clean(row["Delivery ID"]).upper(),
                day=datetime.strptime(row["Delivery Date"].strip(), DATE_FORMAT).date(),
                area=clean(row["Delivery Area"]),
                attempt=int(row["Attempt Number"]),
                reason=NO_REASON if reason.lower() == "none" else reason,
                status=match_case(clean(row["Final Status"]), STATUSES),
            )
            if (not record.delivery_id or not record.area or record.attempt < 1
                    or record.status not in STATUSES):
                raise ValueError("incomplete row")
            records.append(record)
        except (KeyError, ValueError, AttributeError, TypeError):
            skipped += 1
    return records, skipped, legacy


def load_records(path=DATA_FILE):
    """Read every attempt. Returns (records, number_of_unreadable_rows)."""
    records, skipped, _ = _load(path)
    return records, skipped


def save_records(records, path=DATA_FILE):
    """Rewrite the whole file (after an update, or when the user chooses Save)."""
    with open(path, "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(FIELDS)
        for record in records:
            writer.writerow(record.to_row())


def append_record(record, path=DATA_FILE):
    """Add one row to the end of the file (when a record is added)."""
    create_file_if_missing(path)
    with open(path, "rb") as file:  # a hand-edited file may lack a final line break
        file.seek(-1, os.SEEK_END)
        needs_newline = file.read(1) not in (b"\n", b"\r")
    with open(path, "a", newline="", encoding="utf-8") as file:
        if needs_newline:
            file.write("\r\n")
        csv.writer(file).writerow(record.to_row())


class DeliveryStore:
    """The records in memory, always kept in step with the CSV file."""

    def __init__(self, path=None):
        self.path = path or DATA_FILE
        if path is None:  # the real data file: the very first run starts with the sample records
            create_file_if_missing(self.path, seed=SAMPLE_FILE)
        self.records = []
        self.skipped = 0
        self.legacy = False   # the file is in the older Windows-1252 format
        self.backup = None    # where the original file was kept when unreadable rows would have been lost
        self.reload()

    def reload(self):
        """Load Records: read the whole CSV file again."""
        self.records, self.skipped, self.legacy = _load(self.path)

    def _rewrite(self, records):
        """Write the whole file. Rows that could not be read exist only in the old file, so
        a copy of it is kept first (delivery_records_backup.csv) instead of silently losing them."""
        if self.skipped and os.path.exists(self.path):
            backup = os.path.splitext(self.path)[0] + "_backup.csv"
            shutil.copyfile(self.path, backup)
            self.backup = backup
        save_records(records, self.path)
        self.skipped, self.legacy = 0, False

    def save(self):
        """Save Records: write every record to the CSV file."""
        self._rewrite(self.records)

    def add(self, record):
        problems = validate(record, self.records)
        if problems:
            raise ValidationError(problems)
        if self.legacy or not os.path.exists(self.path) or os.path.getsize(self.path) == 0:
            # Appending would mix two text formats (a Windows-1252 file), or leave a file that holds only
            # the new row (the file was deleted while the program was open): write every record instead.
            self._rewrite(self.records + [record])
        else:
            append_record(record, self.path)
        self.records.append(record)

    def update(self, old, new):
        problems = validate(new, self.records, editing=old)
        if problems:
            raise ValidationError(problems)
        updated = [new if r is old else r for r in self.records]
        self._rewrite(updated)  # write first: if the file is locked, memory stays unchanged
        self.records[:] = updated

    def attempts_of(self, delivery_id):
        found = [r for r in self.records if r.delivery_id == delivery_id.strip().upper()]
        return sorted(found, key=lambda r: (r.attempt, r.day))

    def next_attempt(self, delivery_id):
        found = self.attempts_of(delivery_id)
        return max((r.attempt for r in found), default=0) + 1

    def known_areas(self):
        return sorted({r.area for r in self.records})

    def known_reasons(self):
        extra = {r.reason for r in self.records if r.reason != NO_REASON}
        return COMMON_REASONS + sorted(extra - set(COMMON_REASONS))


# ---------------------------------------------------------------- analysis --
def sort_records(records):
    return sorted(records, key=lambda r: (r.day, r.delivery_id, r.attempt))


def group_deliveries(records):
    """{delivery_id: [attempts in attempt order]}"""
    groups = defaultdict(list)
    for record in records:
        groups[record.delivery_id].append(record)
    for attempts in groups.values():
        attempts.sort(key=lambda r: (r.attempt, r.day))
    return dict(groups)


@dataclass
class DeliveryInfo:
    """One unique delivery, summarised from all of its attempts."""
    delivery_id: str
    area: str
    attempts: int
    status: str
    last_reason: str

    @property
    def redelivered(self):
        return self.attempts > 1


def delivery_infos(records):
    infos = []
    for delivery_id, attempts in sorted(group_deliveries(records).items()):
        last = attempts[-1]
        infos.append(DeliveryInfo(delivery_id, last.area, len(attempts), last.status, last.reason))
    return infos


@dataclass
class Summary:
    total_attempts: int
    deliveries: int
    successful: int
    failed: int
    pending: int
    redeliveries: int
    failed_attempts: int
    success_rate: float  # percent, 0 when there are no deliveries
    top_reason: str      # e.g. "Recipient unavailable (2)" or "-"


def percent(part, whole):
    return 100.0 * part / whole if whole else 0.0


def failed_by_reason(records):
    """[(reason, count)] for failed attempts, most common first."""
    counts = Counter(r.reason_label for r in records if r.is_failed_attempt)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def summarize(records):
    infos = delivery_infos(records)
    status = Counter(info.status for info in infos)
    reasons = failed_by_reason(records)
    if reasons:
        top = reasons[0][1]
        names = [name for name, count in reasons if count == top]
        top_reason = f"{' / '.join(names)} ({top})"
    else:
        top_reason = "-"
    return Summary(
        total_attempts=len(records),
        deliveries=len(infos),
        successful=status[SUCCESSFUL],
        failed=status[FAILED],
        pending=status[PENDING],
        redeliveries=sum(1 for info in infos if info.redelivered),
        failed_attempts=sum(count for _, count in reasons),
        success_rate=percent(status[SUCCESSFUL], len(infos)),
        top_reason=top_reason,
    )


def status_counts(records):
    """{status: unique deliveries} for every status, zero included."""
    counts = Counter(info.status for info in delivery_infos(records))
    return {status: counts[status] for status in STATUSES}


@dataclass
class AreaStat:
    area: str
    deliveries: int
    successful: int
    failed_attempts: int
    redeliveries: int
    rate: float  # percent of unique deliveries completed successfully


def success_by_area(records):
    """Per-area statistics, sorted by area name."""
    infos = delivery_infos(records)
    area_of = {info.delivery_id: info.area for info in infos}  # a delivery counts in its latest area
    failed_attempts = Counter(area_of[r.delivery_id] for r in records if r.is_failed_attempt)
    stats = []
    for area in sorted(set(area_of.values())):
        mine = [info for info in infos if info.area == area]
        successful = sum(1 for info in mine if info.status == SUCCESSFUL)
        stats.append(AreaStat(
            area, len(mine), successful, failed_attempts[area],
            sum(1 for info in mine if info.redelivered), percent(successful, len(mine)),
        ))
    return stats


# ------------------------------------------------------------------ trends --
@dataclass
class TrendPoint:
    day: date
    failed_attempts: int
    redelivery_attempts: int


def trend(records):
    """Failed attempts and redelivery attempts (attempt 2+) for each day.

    Days with no activity are included as zeros so the line is continuous, as long as the records
    cover at most MAX_FILLED_DAYS; over a longer span only the days that have records are listed
    (a mistyped year in a hand-edited file must not make the program crawl).
    """
    if not records:
        return []
    failed, redelivery = Counter(), Counter()
    for record in records:
        failed[record.day] += record.is_failed_attempt
        redelivery[record.day] += record.attempt >= 2
    first, last = min(failed), max(failed)
    if (last - first).days <= MAX_FILLED_DAYS:
        days = [first + timedelta(days=n) for n in range((last - first).days + 1)]
    else:
        days = sorted(failed)
    return [TrendPoint(day, failed[day], redelivery[day]) for day in days]


# --------------------------------------------------------------- filtering --
def filter_records(records, text="", area=None, status=None, reason=None, attempts=None):
    """Filter attempts. Any argument left as None/"" is ignored.

    text     : part of a Delivery ID
    attempts : "1", "2" or "3+", the delivery's TOTAL number of attempts
    """
    totals = Counter(r.delivery_id for r in records)
    text = clean(text).lower()
    result = []
    for r in records:
        if text and text not in r.delivery_id.lower():
            continue
        if area and r.area != area:
            continue
        if status and r.status != status:
            continue
        if reason and r.reason != reason:
            continue
        if attempts:
            total = totals[r.delivery_id]
            if (attempts == "3+" and total < 3) or (attempts in ("1", "2") and total != int(attempts)):
                continue
        result.append(r)
    return result
