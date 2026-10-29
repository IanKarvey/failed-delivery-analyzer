"""
Console (menu-driven) version of the Failed Delivery and Redelivery Pattern Analyzer.

The menu follows the "Required Features of the Program" of the project requirements, in the
requirements' order. It uses the same delivery_core and delivery_charts as the window, so
both versions read and write the same delivery_records.csv and show the same numbers.

Run:  python main.py --console
"""

import os
from datetime import date

import delivery_core as core

MENU = """
==================================================
   FAILED DELIVERY AND REDELIVERY PATTERN ANALYZER
==================================================
  1. Add Delivery Records           7. Delivery Success Rate Calculation
  2. View and Search Deliveries     8. Area-Based Delivery Analysis
  3. Update Delivery Records        9. Delivery Trend Monitoring
  4. Filter Delivery Records       10. Delivery Summary
  5. Failed Delivery Analysis      11. Data Visualization
  6. Redelivery Tracking
  0. Exit  (records are saved after every change)
--------------------------------------------------"""


# ------------------------------------------------------------------ input --
def ask_text(prompt, optional=False):
    while True:
        text = input(prompt).strip()
        if text or optional:
            return text
        print("  This field cannot be empty.")


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
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1]
        if other and text.isdigit() and int(text) == len(options) + 1:
            return ask_text("  Type it: ")
        print("  Please choose one of the numbers shown.")


def ask_int(prompt, minimum=1):
    while True:
        try:
            value = int(input(prompt).strip())
        except ValueError:
            value = minimum - 1
        if value >= minimum:
            return value
        print(f"  Please enter a whole number ({minimum} or more).")


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


ATTEMPT_HEADERS = core.FIELDS  # the six fields of the requirements


def heading(text):
    print(f"\n=== {text} ===")


# ---------------------------------------------------------------- features --
def add_record(store):
    heading("Add Delivery Records")
    delivery_id = ask_text("Delivery ID (example D006): ").upper()
    existing = store.attempts_of(delivery_id)
    if existing:
        area, number = existing[-1].area, store.next_attempt(delivery_id)
        print(f"  {delivery_id} already has {core.plural(len(existing), 'attempt')}; "
              f"this will be attempt {number} in {area}.")
    else:
        areas = store.known_areas()
        area = (ask_choice("Delivery area:", areas, other=True) if areas
                else ask_text("Delivery area (example Area A): "))
        number = 1
    day = input(f"Delivery date YYYY-MM-DD [Enter for {date.today()}]: ").strip() or str(date.today())
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
        print("Not saved:\n  " + "\n  ".join(error.errors))
    except OSError as error:
        print(f"Could not write the file (is it open in Excel?): {error}")
    else:
        print(f"Saved {record.delivery_id}, attempt {record.attempt}.")


def view_and_search(store):
    heading("View and Search Deliveries")
    keyword = input("Delivery ID, or part of it (Enter to show every record): ").strip()
    found = core.filter_records(store.records, keyword)
    print(f"\n{core.plural(len(found), 'record')}:")
    table(ATTEMPT_HEADERS, attempt_rows(found))


def update_record(store):
    heading("Update Delivery Records")
    attempts = store.attempts_of(ask_text("Delivery ID to update: "))
    if not attempts:
        print("  No delivery has that ID.")
        return
    record = attempts[0]
    if len(attempts) > 1:
        table(ATTEMPT_HEADERS, attempt_rows(attempts))
        wanted = ask_int("Which attempt number? ")
        chosen = [a for a in attempts if a.attempt == wanted]
        if not chosen:
            print("  That attempt does not exist.")
            return
        record = chosen[0]
    print("Press Enter to keep the current value.")

    def keep(prompt, current):
        return input(f"{prompt} [{current}]: ").strip() or str(current)

    day = keep("Delivery date", record.day)
    area = keep("Delivery area", record.area)
    number = keep("Attempt number", record.attempt)
    status = keep(f"Final status ({'/'.join(core.STATUSES)})", record.status)
    reason = keep("Failure reason", record.reason)
    if status == core.SUCCESSFUL:
        reason = core.NO_REASON
    try:
        new = core.make_attempt(record.delivery_id, day, area, number, reason, status,
                                store.known_areas(), store.known_reasons())
        store.update(record, new)
    except core.ValidationError as error:
        print("Not saved:\n  " + "\n  ".join(error.errors))
    except OSError as error:
        print(f"Could not write the file (is it open in Excel?): {error}")
    else:
        print("Updated.")


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
    again = sorted((i for i in infos if i.redelivered), key=lambda i: (-i.attempts, i.delivery_id))
    table(["Delivery ID", "Area", "Attempts", "Latest status", "Latest failure reason"],
          [(i.delivery_id, i.area, i.attempts, i.status, i.last_reason) for i in again])
    print(f"\n{len(again)} of {core.plural(len(infos), 'delivery')} needed more than one attempt "
          f"({core.format_percent(core.percent(len(again), len(infos)))}).")


def success_rate(store):
    heading("Delivery Success Rate Calculation")
    s = core.summarize(store.records)
    print(f"  Successful deliveries : {s.successful} of {core.plural(s.deliveries, 'unique delivery')}")
    print(f"  Delivery success rate : {core.format_percent(s.success_rate)}")


def area_analysis(store):
    heading("Area-Based Delivery Analysis")
    stats = core.success_by_area(store.records)
    table(["Area", "Deliveries", "Successful", "Redeliveries", "Success rate"],
          [(a.area, a.deliveries, a.successful, a.redeliveries, core.format_percent(a.rate))
           for a in stats])
    if len(stats) > 1:
        worst = min(stats, key=lambda a: a.rate)
        print(f"\nLowest success rate: {worst.area} ({core.format_percent(worst.rate)})")


def trend_monitoring(store):
    heading("Delivery Trend Monitoring")
    points = core.trend(store.records, "day")
    table(["Date", "Failed attempts", "Redelivery attempts"],
          [(p.start, p.failed_attempts, p.redelivery_attempts) for p in points])


def delivery_summary(store):
    heading("Delivery Summary")
    s = core.summarize(store.records)
    for name, value in [
        ("Total delivery attempts", s.total_attempts), ("Unique deliveries", s.deliveries),
        ("Successful deliveries", s.successful), ("Failed deliveries", s.failed),
        ("Pending deliveries", s.pending), ("Deliveries requiring redelivery", s.redeliveries),
        ("Failed delivery attempts", s.failed_attempts),
        ("Delivery success rate", core.format_percent(s.success_rate)),
        ("Most common failure reason", s.top_reason),
    ]:
        print(f"  {name:<32}{value}")


def data_visualization(store):
    heading("Data Visualization")
    if not store.records:
        print("  No records yet. Add some first.")
        return
    import matplotlib.pyplot as plt

    import delivery_charts as charts

    titles = [spec.title for spec in charts.CHARTS]
    pick = ask_choice("Which chart?", titles + ["All four charts"])
    specs = charts.CHARTS if pick == "All four charts" else [charts.CHARTS[titles.index(pick)]]
    for spec in specs:
        fig = plt.figure(figsize=spec.size, facecolor=charts.SURFACE, layout="constrained")
        spec.draw(fig, store.records)
    print("Close the chart window(s) to return to the menu.")
    plt.show()
    plt.close("all")


ACTIONS = {
    "1": add_record, "2": view_and_search, "3": update_record, "4": filter_records,
    "5": failure_analysis, "6": redelivery_tracking, "7": success_rate, "8": area_analysis,
    "9": trend_monitoring, "10": delivery_summary, "11": data_visualization,
}


def main(store=None):
    store = store or core.DeliveryStore()
    print(f"Loaded {core.plural(len(store.records), 'record')} from {os.path.basename(store.path)}.")
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
            if action:
                action(store)
            else:
                print("  Invalid choice. Enter a number from the menu.")
    except (EOFError, KeyboardInterrupt):
        print("\nProgram closed. Saved records are safe.")


if __name__ == "__main__":
    main()
