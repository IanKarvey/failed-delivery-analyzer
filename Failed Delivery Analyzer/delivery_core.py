"""
Core logic for the Failed Delivery and Redelivery Pattern Analyzer.

No screen code lives here. The Tkinter window (delivery_gui.py) and the
console menu (delivery_console.py) both call these functions, so they always
agree on the numbers.

Data model
  * delivery_records.csv has one row per delivery ATTEMPT.
  * The same Delivery ID appears again when a delivery needs a redelivery.
  * A delivery's outcome is the Final Status of its LATEST attempt.
  * A "failed attempt" is an attempt that has a failure reason (or status Failed).
"""

import csv
import os
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta

APP_NAME = "Delivery-Analyzer"


def _program_folder():
    """The folder the program lives in: next to the .exe when packaged, else next to this file."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _bundled_folder():
    """Where files bundled into the .exe (the sample data) are unpacked to."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


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
    """Where the CSV, charts and error log are saved: the program folder, or, if Windows
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
CHARTS_DIR = os.path.join(DATA_DIR, "charts")
LOG_FILE = os.path.join(DATA_DIR, "error_log.txt")
SAMPLE_FILE = os.path.join(_bundled_folder(), "sample_data", "delivery_records.csv")  # first-run data

FIELDS = [
    "Delivery ID", "Delivery Date", "Delivery Area",
    "Attempt Number", "Failure Reason", "Final Status",
]
DATE_FORMAT = "%Y-%m-%d"

SUCCESSFUL, FAILED, PENDING = "Successful", "Failed", "Pending"
STATUSES = [SUCCESSFUL, FAILED, PENDING]

NO_REASON = "None"
NOT_SPECIFIED = "Not specified"
COMMON_REASONS = ["Recipient unavailable", "Incorrect address", "Delivery postponed"]

PERIODS = ["day", "week", "month"]


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
    """Raised with a list of messages that are safe to show to the user.

    `fields` maps a field name ("id", "date", "area", "attempt", "status", "reason")
    to its message, so a form can show each message beside the right box.
    """

    def __init__(self, errors, fields=None):
        super().__init__("; ".join(errors))
        self.errors = list(errors)
        self.fields = dict(fields or {})


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


def match_case(value, options):
    """Return the option equal to value ignoring case, else value unchanged."""
    for option in options:
        if option.lower() == value.lower():
            return option
    return value


def make_attempt(delivery_id, day_text, area, attempt_text, reason, status,
                 areas=(), reasons=(), records=None, editing=None):
    """Turn raw form/console text into an Attempt, or raise ValidationError.

    When `records` is given and the date or attempt number cannot be read, the other
    problems that can still be found (a missing area, a failed attempt without a
    reason...) are reported in the same error, so a form can mark every wrong box at once.
    """
    errors, fields = [], {}
    reason = clean(reason) or NO_REASON
    if reason.lower() == NO_REASON.lower():
        reason = NO_REASON
    try:
        day = datetime.strptime(clean(day_text), DATE_FORMAT).date()
    except ValueError:
        day = None
        errors.append("Date must use the format YYYY-MM-DD (example: 2026-10-01).")
        fields["date"] = errors[-1]
    try:
        number = int(clean(attempt_text))
    except ValueError:
        number = 0
        errors.append("Attempt number must be a whole number.")
        fields["attempt"] = errors[-1]
    if errors:
        if records is not None:
            provisional = Attempt(
                delivery_id=clean(delivery_id).upper(), day=day or date.today(),
                area=match_case(clean(area), areas), attempt=number or 1,
                reason=match_case(reason, list(reasons) + [NO_REASON]),
                status=match_case(clean(status), STATUSES))
            for field, text in _problems(provisional, records, editing):
                if field not in fields and not (field == "attempt" and "attempt" in fields):
                    errors.append(text)
                    fields[field] = text
        raise ValidationError(errors, fields)
    return Attempt(
        delivery_id=clean(delivery_id).upper(),
        day=day,
        area=match_case(clean(area), areas),
        attempt=number,
        reason=match_case(reason, list(reasons) + [NO_REASON]),
        status=match_case(clean(status), STATUSES),
    )


def _problems(record, records, editing=None):
    """[(field, message)] for everything wrong with `record`, in the order a form shows its fields."""
    found = []
    if not record.delivery_id:
        found.append(("id", "Delivery ID is required."))
    if not record.area:
        found.append(("area", "Delivery area is required."))
    if record.attempt < 1:
        found.append(("attempt", "Attempt number must be 1 or more."))
    if record.status not in STATUSES:
        found.append(("status", "Choose a final status: " + ", ".join(STATUSES) + "."))
    elif record.status == SUCCESSFUL and record.reason != NO_REASON:
        found.append(("reason", "A successful attempt cannot have a failure reason (use None)."))
    elif record.status == FAILED and record.reason == NO_REASON:
        found.append(("reason", "A failed attempt needs a failure reason."))

    same = [r for r in records if r is not editing and r.delivery_id == record.delivery_id]
    if any(r.attempt == record.attempt for r in same):
        found.append(("attempt", f"{record.delivery_id} already has an attempt number {record.attempt}."))
    if editing is None:
        done = [r for r in same if r.status == SUCCESSFUL]
        if done:
            found.append(("id", f"{record.delivery_id} was already delivered successfully "
                                f"(attempt {done[0].attempt}), so no more attempts can be added."))
    return found


def validate(record, records, editing=None):
    """Return a list of problems with `record` (empty list = OK).

    `editing` is the existing record being replaced, so it is ignored when
    checking for duplicates. Adding (editing=None) also blocks new attempts
    for a delivery that was already completed.
    """
    return [message for _, message in _problems(record, records, editing)]


def validate_fields(record, records, editing=None):
    """Like validate(), but returns {field: first message} so a form can mark the right boxes."""
    fields = {}
    for field, message in _problems(record, records, editing):
        fields.setdefault(field, message)
    return fields


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


def load_records(path=DATA_FILE):
    """Read every attempt. Returns (records, number_of_unreadable_rows)."""
    create_file_if_missing(path)
    records, skipped = [], 0
    with open(path, newline="", encoding="utf-8-sig") as file:  # -sig: Excel BOM
        for row in csv.DictReader(file):
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
    return records, skipped


def save_records(records, path=DATA_FILE):
    """Rewrite the whole file (after an update or a delete)."""
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
        self.reload()

    def reload(self):
        self.records, self.skipped = load_records(self.path)

    def add(self, record):
        fields = validate_fields(record, self.records)
        if fields:
            raise ValidationError(validate(record, self.records), fields)
        append_record(record, self.path)
        self.records.append(record)

    def update(self, old, new):
        fields = validate_fields(new, self.records, editing=old)
        if fields:
            raise ValidationError(validate(new, self.records, editing=old), fields)
        updated = [new if r is old else r for r in self.records]
        save_records(updated, self.path)  # write first: if the file is locked, memory stays unchanged
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
    first_day: date
    last_day: date
    last_reason: str

    @property
    def redelivered(self):
        return self.attempts > 1


def delivery_infos(records):
    infos = []
    for delivery_id, attempts in sorted(group_deliveries(records).items()):
        last = attempts[-1]
        infos.append(DeliveryInfo(
            delivery_id, last.area, len(attempts), last.status,
            min(a.day for a in attempts), max(a.day for a in attempts), last.reason,
        ))
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
    failed: int
    pending: int
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
        counts = Counter(info.status for info in mine)
        stats.append(AreaStat(
            area, len(mine), counts[SUCCESSFUL], counts[FAILED], counts[PENDING],
            failed_attempts[area], sum(1 for info in mine if info.redelivered),
            percent(counts[SUCCESSFUL], len(mine)),
        ))
    return stats


# ------------------------------------------------------------------ trends --
@dataclass
class TrendPoint:
    start: date
    failed_attempts: int
    redelivery_attempts: int


def bucket_start(day, period):
    if period == "week":
        return day - timedelta(days=day.weekday())  # Monday
    if period == "month":
        return day.replace(day=1)
    return day


def next_bucket(start, period):
    if period == "week":
        return start + timedelta(days=7)
    if period == "month":
        return (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start + timedelta(days=1)


def trend(records, period="day"):
    """Failed attempts and redelivery attempts (attempt 2+) per day/week/month.

    Periods with no activity are included as zeros so the line is continuous.
    """
    if not records:
        return []
    failed, redelivery = Counter(), Counter()
    for record in records:
        key = bucket_start(record.day, period)
        failed[key] += record.is_failed_attempt
        redelivery[key] += record.attempt >= 2
    points = []
    current = min(bucket_start(r.day, period) for r in records)
    last = max(bucket_start(r.day, period) for r in records)
    while current <= last:
        points.append(TrendPoint(current, failed[current], redelivery[current]))
        current = next_bucket(current, period)
    return points


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
