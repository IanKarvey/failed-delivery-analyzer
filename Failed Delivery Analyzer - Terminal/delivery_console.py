"""
The menu-driven, console-based program:
"Failed Delivery and Redelivery Pattern Analyzer Using Python".

The menu lists the 12 "Required Features of the Program" (Section III of the requirements) in the
requirements' own order. The records are kept in delivery_records.csv (Section IV), the analysis
uses the numbers of the "Sample Data of Delivery Analysis" table, and the charts are the four
Matplotlib visualizations of Section V.

Run:  python main.py
"""

import os
from datetime import date

import delivery_core as core

WIDTH = 74


# ------------------------------------------------------------------ input --
def ask_text(prompt, optional=False):
    while True:
        text = input(prompt).strip()
        if text or optional:
            return text
        print("  This field cannot be empty.")


def whole_number(text):
    """int(text) for plain digits 0-9 only (so characters like a superscript 2 are just 'not a number')."""
    return int(text) if text.isascii() and text.isdigit() else None


def ask_choice(title, options, optional=False, other=False):
    """Show a numbered list and return the chosen text ('' if skipped)."""
    print(title)
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    if other:
        print(f"  {len(options) + 1}. Other (type your own)")
    hint = " (Enter to skip)" if optional else ""
    while True:
        text = input(f"Choose a number{hint}: ").strip()
        if optional and not text:
            return ""
        number = whole_number(text)
        if number is not None and 1 <= number <= len(options):
            return options[number - 1]
        if other and number == len(options) + 1:
            return ask_text("  Type it: ")
        print("  Please choose one of the numbers shown.")


def ask_date(prompt, default):
    """Ask for a date until it is written as YYYY-MM-DD; Enter keeps `default`."""
    while True:
        text = input(f"{prompt} [Enter for {default}]: ").strip() or str(default)
        try:
            core.parse_date(text)
            return text
        except ValueError as error:
            print(f"  {error}")


def ask_int(prompt, minimum=1):
    while True:
        value = whole_number(input(prompt).strip())
        if value is not None and value >= minimum:
            return value
        print(f"  Please enter a whole number ({minimum} or more).")


def pause():
    input("\nPress Enter to return to the menu...")


# ----------------------------------------------------------------- display --
def table(headers, rows):
    """Print a plain-text table; numbers are right-aligned."""
    if not rows:
        print("  (nothing to show)")
        return
    cells = [[str(v) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(headers)]
    numeric = [all(r[i].replace(".", "").replace("%", "").isdigit() for r in cells)
               for i in range(len(headers))]

    def line(values):
        return "  ".join(v.rjust(w) if num else v.ljust(w)
                         for v, w, num in zip(values, widths, numeric)).rstrip()

    print(line(headers))
    print("-" * len(line(headers)))
    for row in cells:
        print(line(row))


def attempt_rows(records):
    return [(r.delivery_id, r.day.strftime(core.DATE_FORMAT), r.area, r.attempt, r.reason, r.status)
            for r in core.sort_records(records)]


ATTEMPT_HEADERS = core.FIELDS  # the six fields of delivery_records.csv


def heading(text):
    print(f"\n=== {text} ===")


def problems(error):
    print("Not saved:\n  " + "\n  ".join(error.errors))


def mention_backup(store):
    """Tell the user when rows that could not be read were kept in a backup copy of the file."""
    if store.backup:
        print(f"Note: some rows of the file could not be read, so they are not in the saved file. The original "
              f"file was kept as {os.path.basename(store.backup)}, so nothing is lost.")
        store.backup = None


# ---------------------------------------------------------------- features --
def add_record(store):
    heading("Add Delivery Records")
    delivery_id = ask_text("Delivery ID (example D006; just Enter to go back): ", optional=True).upper()
    if not delivery_id:
        return False
    existing = store.attempts_of(delivery_id)
    done = core.successful_attempt(existing, delivery_id)
    if done:
        print(f"  {delivery_id} was already delivered successfully (attempt {done.attempt}), "
              "so no more attempts can be added.")
        return True
    if existing:
        area, number = existing[-1].area, store.next_attempt(delivery_id)
        print(f"  {delivery_id} already has {core.plural(len(existing), 'attempt')}; "
              f"this will be attempt {number} in {area}.")
    else:
        areas = store.known_areas()
        area = (ask_choice("Delivery area:", areas, other=True) if areas
                else ask_text("Delivery area (example Area A): "))
        number = 1
    day = ask_date("Delivery date YYYY-MM-DD", date.today())
    status = ask_choice("Final status of this attempt:", core.STATUSES)
    reason = core.NO_REASON
    if status == core.FAILED:
        reason = ask_choice("Failure reason:", store.known_reasons(), other=True)
    elif status == core.PENDING:
        reason = ask_choice("Failure reason of this attempt:", store.known_reasons(), optional=True,
                            other=True) or core.NO_REASON
    try:
        record = core.make_attempt(delivery_id, day, area, number, reason, status,
                                   store.known_areas(), store.known_reasons())
        store.add(record)
    except core.ValidationError as error:
        problems(error)
    except OSError as error:
        print(f"Could not write the file (is it open in Excel?): {error}")
    else:
        print(f"Saved {record.delivery_id}, attempt {record.attempt}.")
    return True


def view_and_search(store):
    heading("View and Search Deliveries")
    keyword = input("Delivery ID, or part of it (Enter to show every record): ").strip()
    found = core.filter_records(store.records, keyword)
    print(f"\n{core.plural(len(found), 'record')}:")
    table(ATTEMPT_HEADERS, attempt_rows(found))


def update_record(store):
    heading("Update Delivery Records")
    delivery_id = ask_text("Delivery ID to update (just Enter to go back): ", optional=True)
    if not delivery_id:
        return False
    attempts = store.attempts_of(delivery_id)
    if not attempts:
        print("  No delivery has that ID.")
        return True
    record = attempts[0]
    if len(attempts) > 1:
        table(ATTEMPT_HEADERS, attempt_rows(attempts))
        wanted = ask_int("Which attempt number? ")
        chosen = [a for a in attempts if a.attempt == wanted]
        if not chosen:
            print("  That attempt does not exist.")
            return True
        record = chosen[0]
    print("Press Enter to keep the current value.")

    def keep(prompt, current):
        return input(f"{prompt} [{current}]: ").strip() or str(current)

    day = keep("Delivery date", record.day)
    area = keep("Delivery area", record.area)
    number = keep("Attempt number", record.attempt)
    status = keep(f"Final status ({'/'.join(core.STATUSES)})", record.status)
    reason = keep("Failure reason", record.reason)
    if core.match_case(status, core.STATUSES) == core.SUCCESSFUL:
        reason = core.NO_REASON
    try:
        new = core.make_attempt(record.delivery_id, day, area, number, reason, status,
                                store.known_areas(), store.known_reasons())
        store.update(record, new)
    except core.ValidationError as error:
        problems(error)
    except OSError as error:
        print(f"Could not write the file (is it open in Excel?): {error}")
    else:
        print("Updated.")
        mention_backup(store)
    return True


def filter_records(store):
    heading("Filter Delivery Records (press Enter to skip a filter)")
    area = ask_choice("Area:", store.known_areas(), optional=True)
    status = ask_choice("Status:", core.STATUSES, optional=True)
    reason = ask_choice("Failure reason:", [core.NO_REASON] + store.known_reasons(), optional=True)
    attempts = ask_choice("Attempts per delivery:", ["1", "2", "3+"], optional=True)
    found = core.filter_records(store.records, area=area or None, status=status or None,
                                reason=reason or None, attempts=attempts or None)
    print(f"\n{core.plural(len(found), 'matching attempt')}:")
    table(ATTEMPT_HEADERS, attempt_rows(found))


def failure_analysis(store):
    heading("Failed Delivery Analysis")
    reasons = core.failed_by_reason(store.records)
    total = sum(count for _, count in reasons)
    table(["Failure reason", "Failed attempts", "Share"],
          [(name, count, core.format_percent(core.percent(count, total))) for name, count in reasons])
    print(f"\nMost common failure reason: {core.summarize(store.records).top_reason}")


def redelivery_tracking(store):
    heading("Redelivery Tracking")
    infos = core.delivery_infos(store.records)
    table(["Delivery ID", "Area", "Attempts", "Redelivery", "Latest status", "Latest failure reason"],
          [(i.delivery_id, i.area, i.attempts, "Yes" if i.redelivered else "No", i.status, i.last_reason)
           for i in sorted(infos, key=lambda i: (-i.attempts, i.delivery_id))])
    again = sum(1 for i in infos if i.redelivered)
    print(f"\n{again} of {core.plural(len(infos), 'delivery')} needed more than one attempt "
          f"({core.format_percent(core.percent(again, len(infos)))}).")


def success_rate(store):
    heading("Delivery Success Rate Calculation")
    s = core.summarize(store.records)
    print(f"  Successful deliveries : {s.successful} of {core.plural(s.deliveries, 'unique delivery')}")
    print(f"  Delivery success rate : {core.format_percent(s.success_rate)}")


def area_analysis(store):
    heading("Area-Based Delivery Analysis")
    stats = core.success_by_area(store.records)
    table(["Area", "Deliveries", "Successful", "Failed attempts", "Redeliveries", "Success rate"],
          [(a.area, a.deliveries, a.successful, a.failed_attempts, a.redeliveries,
            core.format_percent(a.rate)) for a in stats])
    if len(stats) < 2:
        return
    lowest = min(a.rate for a in stats)
    most = max(a.failed_attempts for a in stats)
    if lowest < max(a.rate for a in stats):
        names = ", ".join(a.area for a in stats if a.rate == lowest)
        print(f"\nLowest success rate  : {names} ({core.format_percent(lowest)})")
    if most > min(a.failed_attempts for a in stats):
        names = ", ".join(a.area for a in stats if a.failed_attempts == most)
        print(f"Most failed attempts : {names} ({most})")


def trend_monitoring(store):
    heading("Delivery Trend Monitoring")
    table(["Date", "Failed attempts", "Redelivery attempts"],
          [(p.day, p.failed_attempts, p.redelivery_attempts) for p in core.trend(store.records)])


def delivery_summary(store):
    heading("Delivery Summary")
    s = core.summarize(store.records)
    areas = ",  ".join(f"{a.area} {core.format_percent(a.rate)}" for a in core.success_by_area(store.records))
    for name, value in [
        ("Total delivery attempts", s.total_attempts), ("Unique deliveries", s.deliveries),
        ("Successful deliveries", s.successful), ("Failed deliveries", s.failed),
        ("Pending deliveries", s.pending), ("Deliveries requiring redelivery", s.redeliveries),
        ("Failed delivery attempts", s.failed_attempts),
        ("Delivery success rate", core.format_percent(s.success_rate)),
        ("Most common failure reason", s.top_reason),
        ("Delivery success rate by area", areas or "-"),
    ]:
        print(f"  {name:<32}{value}")


def data_visualization(store):
    heading("Data Visualization")
    if not store.records:
        print("  No records yet. Add some first.")
        return
    try:
        import delivery_charts as charts
    except ImportError:
        print("  Matplotlib is not installed, so the charts cannot be drawn.\n"
              "  Install it with:  python -m pip install matplotlib")
        return
    names = [spec.name for spec in charts.CHARTS]
    pick = ask_choice("Which chart?", names + ["All four charts"])
    specs = charts.CHARTS if pick == "All four charts" else [charts.CHARTS[names.index(pick)]]
    print("Close the chart window(s) to return to the menu.")
    charts.show(specs, store.records)


def save_and_load(store):
    heading("Save and Load Records")
    print(f"  File: {store.path}")
    print(f"  {core.plural(len(store.records), 'record')} in the program now. Records are loaded when the "
          "program starts\n  and saved after every change, so this is only needed to do it again by hand.")
    pick = ask_choice("What do you want to do?", ["Save the records to the CSV file now",
                                                  "Load the records from the CSV file again"], optional=True)
    try:
        if pick.startswith("Save"):
            store.save()
            print(f"Saved {core.plural(len(store.records), 'record')} to {os.path.basename(store.path)}.")
            mention_backup(store)
        elif pick.startswith("Load") and not os.path.exists(store.path):
            print("The file is missing, so there is nothing to load (the records in the program are kept).\n"
                  "Choose Save to write them to a new file.")
        elif pick.startswith("Load"):
            store.reload()
            print(f"Loaded {core.plural(len(store.records), 'record')} from {os.path.basename(store.path)}.")
            if store.skipped:
                print(f"Warning: {core.plural(store.skipped, 'row')} could not be read and was skipped.")
    except OSError as error:
        print(f"Could not use the file (is it open in Excel?): {error}")


# The 12 required features, numbered as in Section III of the requirements.
FEATURES = [
    ("Add Delivery Records", add_record), ("View and Search Deliveries", view_and_search),
    ("Update Delivery Records", update_record), ("Filter Delivery Records", filter_records),
    ("Failed Delivery Analysis", failure_analysis), ("Redelivery Tracking", redelivery_tracking),
    ("Delivery Success Rate Calculation", success_rate), ("Area-Based Delivery Analysis", area_analysis),
    ("Delivery Trend Monitoring", trend_monitoring), ("Delivery Summary", delivery_summary),
    ("Data Visualization", data_visualization), ("Save and Load Records", save_and_load),
]
ACTIONS = {str(number): action for number, (_, action) in enumerate(FEATURES, start=1)}


def _menu():
    half = len(FEATURES) // 2
    left, right = FEATURES[:half], FEATURES[half:]
    lines = ["", "=" * WIDTH, "  FAILED DELIVERY AND REDELIVERY PATTERN ANALYZER USING PYTHON", "=" * WIDTH]
    for index, ((name, _), (other, _)) in enumerate(zip(left, right), start=1):
        lines.append(f"  {index:>2}. {name:<30}{index + half:>2}. {other}")
    lines += ["   0. Exit  (records are saved after every change)", "-" * WIDTH]
    return "\n".join(lines)


MENU = _menu()


def main(store=None):
    store = store or core.DeliveryStore()
    print(f"Loaded {core.plural(len(store.records), 'record')} from {os.path.basename(store.path)}.")
    if store.path == core.DATA_FILE and core.DATA_DIR != core.BASE_DIR:
        print("Note: Windows does not let this program save in its own folder (for example because of\n"
              f"Controlled folder access), so your records are kept in: {core.DATA_DIR}")
    if store.skipped:
        print(f"Warning: {core.plural(store.skipped, 'row')} could not be read and was skipped.")
    try:
        while True:
            print(MENU)
            choice = input("Choose an option: ").strip()
            if choice == "0":
                print("All changes are already saved. Goodbye!")
                return
            action = ACTIONS.get(choice)
            if not action:
                print("  Invalid choice. Enter a number from the menu.")
            elif action(store) is not False:  # a feature returns False when it was cancelled
                pause()
    except (EOFError, KeyboardInterrupt):
        print("\nProgram closed. Saved records are safe.")


if __name__ == "__main__":
    main()
