"""Tests for the Delivery Analyzer.   Run:  python -m unittest -v"""

import os
os.environ.setdefault("MPLBACKEND", "Agg")  # draw charts without opening windows

import tempfile
import time
import tkinter as tk
import types
import unittest
from datetime import date
from unittest import mock

from matplotlib.figure import Figure

import delivery_charts as charts
import delivery_core as core
import delivery_dialogs as dialogs
import delivery_ui_kit as kit

# The sample data from the requirements document. Tests use this fixed copy, never the
# live delivery_records.csv, so using the app can't break the tests.
SAMPLE_TEXT = """Delivery ID,Delivery Date,Delivery Area,Attempt Number,Failure Reason,Final Status
D001,2026-10-01,Area A,1,Recipient unavailable,Failed
D001,2026-10-02,Area A,2,None,Successful
D002,2026-10-02,Area B,1,Incorrect address,Failed
D003,2026-10-03,Area A,1,None,Successful
D004,2026-10-04,Area C,1,Delivery postponed,Failed
D004,2026-10-05,Area C,2,Recipient unavailable,Pending
D005,2026-10-05,Area B,1,None,Successful
"""


def read_text(path):
    with open(path, encoding="utf-8") as file:
        return file.read()


def attempt(delivery_id, day, area, number, reason, status):
    return core.Attempt(delivery_id, date.fromisoformat(day), area, number, reason, status)


def render_chart(spec, records, path):
    """Draw a chart into a PNG file (only to check that it can be drawn)."""
    fig = Figure(figsize=spec.size)
    charts.apply_layout(fig)
    spec.draw(fig, records)
    fig.savefig(path, dpi=100)
    return path


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def check_everything_fits(case, app, label):
    """Every visible widget on every page sits inside the window, and tables keep room for rows."""
    tables = {0: ["tree"], 1: ["tree", "history_tree"], 2: ["area_tree", "reason_tree"]}
    from delivery_ui_kit import px
    for index, page in enumerate(app.pages):
        app.show(index)
        app.update()
        right = app.winfo_rootx() + app.winfo_width()
        bottom = app.winfo_rooty() + app.winfo_height()
        for widget in descendants(page):
            if not widget.winfo_ismapped():
                continue
            case.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(), right + 1,
                                 f"{label} {type(page).__name__}: {widget} sticks out on the right")
            case.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(), bottom + 1,
                                 f"{label} {type(page).__name__}: {widget} sticks out at the bottom")
        for name in tables.get(index, []):  # every table keeps room for at least ~2 rows
            case.assertGreaterEqual(getattr(page, name).winfo_height(), px(110),
                                    f"{label} {type(page).__name__}.{name} is squeezed too small")


class TempStoreCase(unittest.TestCase):
    """Each test gets its own temporary CSV holding the sample data."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "delivery_records.csv")
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            f.write(SAMPLE_TEXT)
        self.store = core.DeliveryStore(self.path)
        self.original = list(self.store.records)

    def tearDown(self):
        self.dir.cleanup()


class AnalysisTests(TempStoreCase):
    """The numbers below are the ones worked out from the PDF's sample data."""

    def test_summary(self):
        s = core.summarize(self.store.records)
        self.assertEqual((s.total_attempts, s.deliveries), (7, 5))
        self.assertEqual((s.successful, s.failed, s.pending), (3, 1, 1))
        self.assertEqual((s.redeliveries, s.failed_attempts), (2, 4))
        self.assertAlmostEqual(s.success_rate, 60.0)
        self.assertEqual(s.top_reason, "Recipient unavailable (2)")

    def test_failed_by_reason(self):
        self.assertEqual(core.failed_by_reason(self.store.records),
                         [("Recipient unavailable", 2), ("Delivery postponed", 1),
                          ("Incorrect address", 1)])

    def test_success_by_area(self):
        rates = {a.area: (a.deliveries, a.successful, a.rate)
                 for a in core.success_by_area(self.store.records)}
        self.assertEqual(rates, {"Area A": (2, 2, 100.0), "Area B": (2, 1, 50.0), "Area C": (1, 0, 0.0)})

    def test_trend_fills_empty_days_with_zero(self):
        points = core.trend(self.store.records, "day")
        self.assertEqual([p.failed_attempts for p in points], [1, 1, 0, 1, 1])
        self.assertEqual([p.redelivery_attempts for p in points], [0, 1, 0, 0, 1])

    def test_trend_weeks_and_months(self):
        weeks = core.trend(self.store.records, "week")  # Oct 1-4 is one week, Oct 5 (Mon) the next
        self.assertEqual([(p.start.isoformat(), p.failed_attempts) for p in weeks],
                         [("2026-09-28", 3), ("2026-10-05", 1)])
        self.assertEqual(len(core.trend(self.store.records, "month")), 1)
        records = [attempt("D1", "2026-01-31", "A", 1, "x", "Failed"),
                   attempt("D2", "2026-03-02", "A", 1, "x", "Failed")]
        self.assertEqual([p.start.month for p in core.trend(records, "month")], [1, 2, 3])

    def test_unspecified_failure_reason_is_still_counted(self):
        records = [attempt("D1", "2026-01-01", "A", 1, "None", "Failed")]  # hand-edited file
        self.assertEqual(core.failed_by_reason(records), [("Not specified", 1)])

    def test_pending_counts_as_not_yet_successful(self):
        records = [attempt("D1", "2026-01-01", "A", 1, "None", "Pending")]
        self.assertEqual(core.success_by_area(records)[0].rate, 0.0)

    def test_empty_data(self):
        s = core.summarize([])
        self.assertEqual((s.deliveries, s.success_rate, s.top_reason), (0, 0.0, "-"))
        self.assertEqual(core.trend([]), [])
        self.assertEqual(core.success_by_area([]), [])


class FilterTests(TempStoreCase):
    def ids(self, **kw):
        return [(r.delivery_id, r.attempt) for r in core.sort_records(
            core.filter_records(self.store.records, **kw))]

    def test_filters(self):
        self.assertEqual(self.ids(text="d00"), [(f"D00{i}", n) for i, n in
                                                [(1, 1), (1, 2), (2, 1), (3, 1), (4, 1), (4, 2), (5, 1)]])
        self.assertEqual(self.ids(text="d004"), [("D004", 1), ("D004", 2)])
        self.assertEqual(len(self.ids(area="Area A")), 3)
        self.assertEqual(len(self.ids(status="Failed")), 3)
        self.assertEqual(self.ids(reason="Incorrect address"), [("D002", 1)])
        self.assertEqual(len(self.ids(attempts="2")), 4)   # D001 and D004 both have 2 attempts
        self.assertEqual(len(self.ids(attempts="1")), 3)
        self.assertEqual(self.ids(attempts="3+"), [])
        self.assertEqual(self.ids(area="Area C", status="Pending"), [("D004", 2)])


class ValidationTests(TempStoreCase):
    def errors(self, record, editing=None):
        return core.validate(record, self.store.records, editing)

    def test_valid_new_attempt(self):
        self.assertEqual(self.errors(attempt("D006", "2026-10-06", "Area A", 1, "None", "Pending")), [])

    def test_status_and_reason_must_agree(self):
        self.assertTrue(self.errors(attempt("D006", "2026-10-06", "Area A", 1, "Incorrect address", "Successful")))
        self.assertTrue(self.errors(attempt("D006", "2026-10-06", "Area A", 1, "None", "Failed")))

    def test_duplicate_attempt_number_rejected(self):
        self.assertTrue(self.errors(attempt("D004", "2026-10-06", "Area C", 2, "None", "Successful")))

    def test_no_new_attempt_after_success_but_editing_is_allowed(self):
        again = attempt("D001", "2026-10-09", "Area A", 3, "None", "Successful")
        self.assertTrue(self.errors(again))
        second = self.store.records[1]  # D001 attempt 2 (Successful)
        edited = attempt("D001", "2026-10-02", "Area A", 2, "None", "Successful")
        self.assertEqual(self.errors(edited, editing=second), [])

    def test_missing_fields_and_bad_attempt_number(self):
        problems = self.errors(attempt("", "2026-10-06", "", 0, "None", "Pending"))
        self.assertEqual(len(problems), 3)

    def test_make_attempt_normalises_text(self):
        record = core.make_attempt(" d007 ", "2026-10-06", "area  a", "2", "RECIPIENT unavailable",
                                   "failed", self.store.known_areas(), self.store.known_reasons())
        self.assertEqual((record.delivery_id, record.area, record.attempt, record.reason, record.status),
                         ("D007", "Area A", 2, "Recipient unavailable", "Failed"))

    def test_make_attempt_reports_bad_date_and_number(self):
        with self.assertRaises(core.ValidationError) as caught:
            core.make_attempt("D1", "06/10/2026", "A", "two", "None", "Pending")
        self.assertEqual(len(caught.exception.errors), 2)


class FileTests(TempStoreCase):
    def test_missing_file_is_created_with_header(self):
        path = os.path.join(self.dir.name, "new.csv")
        self.assertEqual(core.load_records(path), ([], 0))
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), ",".join(core.FIELDS))

    def test_add_and_update_persist_to_the_file(self):
        new = attempt("D006", "2026-10-06", "Area B", 1, "Incorrect address", "Failed")
        self.store.add(new)
        self.assertEqual(len(core.load_records(self.path)[0]), 8)
        fixed = attempt("D006", "2026-10-06", "Area B", 1, "Delivery postponed", "Failed")
        self.store.update(new, fixed)
        saved = core.load_records(self.path)[0]
        self.assertEqual((len(saved), saved[-1].reason), (8, "Delivery postponed"))
        self.assertEqual(saved[:7], self.original)                       # the other records are untouched

    def test_a_failed_write_leaves_memory_unchanged(self):
        before = list(self.store.records)
        self.store.path = self.dir.name  # a folder, so writing "the file" fails
        with self.assertRaises(OSError):
            self.store.update(self.store.records[0],
                              attempt("D001", "2026-10-01", "Area A", 1, "Incorrect address", "Failed"))
        self.assertEqual(self.store.records, before)

    def test_append_survives_missing_final_newline(self):
        with open(self.path, "w", newline="", encoding="utf-8") as f:
            f.write(",".join(core.FIELDS) + "\r\nD001,2026-10-01,Area A,1,None,Successful")
        core.DeliveryStore(self.path).add(attempt("D002", "2026-10-02", "Area A", 1, "None", "Pending"))
        records, skipped = core.load_records(self.path)
        self.assertEqual(([r.delivery_id for r in records], skipped), (["D001", "D002"], 0))

    def test_unreadable_rows_are_skipped_not_fatal(self):
        with open(self.path, "w", newline="", encoding="utf-8-sig") as f:  # BOM, as Excel writes it
            f.write(",".join(core.FIELDS) + "\n"
                    "D001,2026-10-01,Area A,1,None,successful\n"   # status case is tolerated
                    "D002,01/10/2026,Area A,1,None,Pending\n"      # bad date
                    "D003,2026-10-01,Area A,one,None,Pending\n"    # bad attempt number
                    "D004,2026-10-01,Area A,1,None,Delayed\n"      # unknown status
                    ",2026-10-01,Area A,1,None,Pending\n"          # missing ID
                    "D006,2026-10-01\n")                           # short row
        records, skipped = core.load_records(self.path)
        self.assertEqual(([(r.delivery_id, r.status) for r in records], skipped),
                         ([("D001", "Successful")], 5))


class PackagingTests(TempStoreCase):
    """Things that make the program easy to hand to someone else."""

    def test_sample_data_ships_with_the_program(self):
        self.assertTrue(os.path.exists(core.SAMPLE_FILE))
        records, skipped = core.load_records(core.SAMPLE_FILE)
        self.assertEqual((len(records), skipped), (7, 0))

    def test_first_run_starts_with_the_sample_records(self):
        fresh = os.path.join(self.dir.name, "fresh.csv")
        self.assertTrue(core.create_file_if_missing(fresh, seed=core.SAMPLE_FILE))
        self.assertEqual(len(core.load_records(fresh)[0]), 7)
        self.assertFalse(core.create_file_if_missing(fresh, seed=core.SAMPLE_FILE))  # never overwrites

    def test_existing_data_is_never_replaced_by_the_sample(self):
        before = read_text(self.path)
        core.create_file_if_missing(self.path, seed=core.SAMPLE_FILE)
        self.assertEqual(read_text(self.path), before)

    def test_data_goes_to_appdata_when_the_program_folder_is_read_only(self):
        with mock.patch.object(core, "_is_writable", return_value=False), \
                mock.patch.dict(os.environ, {"LOCALAPPDATA": self.dir.name}):
            folder = core._data_folder()
        self.assertEqual(folder, os.path.join(self.dir.name, core.APP_NAME))
        self.assertTrue(os.path.isdir(folder))

    def test_errors_are_written_to_a_log_file(self):
        log = os.path.join(self.dir.name, "error_log.txt")
        with mock.patch.object(core, "LOG_FILE", log):
            core.log_error("first problem")
            core.log_error("second problem")
        text = read_text(log)
        self.assertIn("first problem", text)
        self.assertIn("second problem", text)

    def test_the_program_draws_its_own_icon(self):
        from delivery_ui_kit import make_icon
        icon = make_icon(64)
        self.assertEqual(icon.size, (64, 64))
        self.assertEqual(icon.getpixel((0, 0))[3], 0)       # rounded corner is transparent
        self.assertGreater(icon.getpixel((32, 8))[3], 200)  # body is solid
        lid = icon.getpixel((29, 21))                       # the parcel's white lid
        self.assertTrue(all(channel > 240 for channel in lid[:3]), lid)
        badge = icon.getpixel((47, 38))                     # inside the red 'failed' badge, off the cross
        self.assertTrue(badge[0] > 200 and badge[1] < 120 and badge[2] < 120, badge)
        for size in (16, 32, 48, 256):                      # every size the window and .exe need
            self.assertEqual(make_icon(size).size, (size, size))


class ChartTests(TempStoreCase):

    def test_each_chart_can_be_revealed_from_nothing_to_the_finished_chart(self):
        fig = Figure()
        records = self.store.records

        reveal = charts.draw_failure_reasons(fig, records)            # bars grow from the left
        bars = fig.axes[0].patches
        final = [bar.get_width() for bar in bars]
        reveal(0.0)
        self.assertTrue(all(bar.get_width() == 0 for bar in bars))
        reveal(0.5)
        self.assertTrue(all(0 < bar.get_width() < end for bar, end in zip(bars, final)))
        reveal(1.0)
        self.assertEqual([bar.get_width() for bar in bars], final)

        reveal = charts.draw_success_by_area(fig, records)            # bars rise from the baseline
        bars = fig.axes[0].patches
        final = [bar.get_height() for bar in bars]
        reveal(0.0)
        self.assertTrue(all(bar.get_height() == 0 for bar in bars))
        reveal(1.0)
        self.assertEqual([bar.get_height() for bar in bars], final)

        reveal = charts.draw_trends(fig, records, "day")              # the lines are drawn left to right
        lines = fig.axes[0].lines
        final = [list(line.get_ydata()) for line in lines]
        reveal(0.5)
        self.assertTrue(all(len(line.get_xdata()) < len(values) for line, values in zip(lines, final)))
        reveal(1.0)
        self.assertEqual([list(line.get_ydata()) for line in lines], final)

        reveal = charts.draw_status_pie(fig, records)                 # the pie opens from its centre
        wedges = fig.axes[0].patches
        reveal(0.0)
        self.assertTrue(all(wedge.r < 0.01 for wedge in wedges))
        reveal(1.0)
        self.assertTrue(all(wedge.r == 1.0 for wedge in wedges))

    def test_all_four_charts_render(self):
        for spec in charts.CHARTS:
            path = render_chart(spec, self.store.records, os.path.join(self.dir.name, spec.key + ".png"))
            self.assertGreater(os.path.getsize(path), 5000, spec.key)

    def test_charts_handle_no_data(self):
        for spec in charts.CHARTS:
            render_chart(spec, [], os.path.join(self.dir.name, spec.key + ".png"))

    def test_the_trend_chart_handles_a_long_date_range(self):
        records = [attempt(f"D{i}", date.fromordinal(739000 + i * 3).isoformat(), "A", 1, "x", "Failed")
                   for i in range(120)]
        render_chart(charts.CHARTS[2], records, os.path.join(self.dir.name, "trend.png"))

    def test_empty_charts_have_nothing_to_reveal(self):
        for spec in charts.CHARTS:
            self.assertIsNone(spec.draw(Figure(), []))


class ConsoleTests(TempStoreCase):
    def run_menu(self, answers):
        import delivery_console
        with mock.patch("builtins.input", side_effect=answers), mock.patch("builtins.print"):
            delivery_console.main(self.store)

    def test_the_menu_follows_the_required_features_in_the_requirements_order(self):
        import delivery_console
        names = ["Add Delivery Records", "View and Search Deliveries", "Update Delivery Records",
                 "Filter Delivery Records", "Failed Delivery Analysis", "Redelivery Tracking",
                 "Delivery Success Rate Calculation", "Area-Based Delivery Analysis",
                 "Delivery Trend Monitoring", "Delivery Summary", "Data Visualization"]
        for number, name in enumerate(names, start=1):
            self.assertIn(f"{number}. {name}", delivery_console.MENU)   # numbered in the requirements' order
        self.assertEqual(sorted(delivery_console.ACTIONS, key=int), [str(i) for i in range(1, 12)])
        self.assertNotIn("Delete", delivery_console.MENU)

    def test_update_a_record(self):
        # menu 3 -> D002 (one attempt) -> keep date/area/attempt, status Failed->Pending, keep reason
        self.run_menu(["3", "D002", "", "", "", "Pending", "", "0"])
        self.assertEqual(self.store.attempts_of("D002")[0].status, "Pending")
        self.assertEqual(core.load_records(self.path)[0][2].status, "Pending")

    def test_every_feature_runs_without_error(self):
        # view/search (keyword), filter (four optional filters), the analyses, trends, summary,
        # and the charts (all four; plt.show is a no-op with the test backend)
        with mock.patch("matplotlib.pyplot.show"):
            self.run_menu(["2", "d00", "4", "", "", "", "", "5", "6", "7", "8", "9", "10",
                           "11", "5", "99", "0"])

    def test_add_a_redelivery(self):
        # menu 1 -> ID D004 (exists, so area and attempt 3 are filled in) -> today -> status 1 (Successful)
        self.run_menu(["1", "D004", "", "1", "0"])
        saved = core.load_records(self.path)[0]
        self.assertEqual((len(saved), saved[-1].delivery_id, saved[-1].attempt, saved[-1].status),
                         (8, "D004", 3, "Successful"))

    def test_invalid_entry_is_refused_with_a_message(self):
        # D001 was already delivered, so a new attempt must be refused and nothing saved
        self.run_menu(["1", "D001", "", "1", "0"])
        self.assertEqual(len(core.load_records(self.path)[0]), 7)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.name == "nt", "needs a display")
class WindowTests(TempStoreCase):
    def setUp(self):
        super().setUp()
        import tkinter
        import delivery_gui
        import delivery_ui_kit
        self.gui, self.kit = delivery_gui, delivery_ui_kit
        self.motion_before = delivery_ui_kit.Motion.enabled
        # Animations are built in. Most tests start with them off (as Windows' "reduce motion"
        # setting would) so they are instant; the animation tests switch them on themselves.
        self.motion_patch = mock.patch.object(delivery_gui, "os_animations_enabled", return_value=False)
        self.motion_patch.start()
        try:
            self.app = delivery_gui.DeliveryApp(self.store)
        except tkinter.TclError as error:
            self.motion_patch.stop()
            self.skipTest(f"Tk not available: {error}")

    def tearDown(self):
        self.app.destroy()
        self.motion_patch.stop()
        self.kit.Motion.enabled = self.motion_before
        super().tearDown()

    def wait_until(self, condition, seconds=4.0):
        """Run the window's event loop until condition() is true (animations need real time)."""
        end = time.time() + seconds
        while time.time() < end:
            self.app.update()
            if condition():
                return True
            time.sleep(0.01)
        return condition()

    def rows(self, tree):
        return [tree.item(i, "values") for i in tree.get_children()]

    def test_pages_show_the_sample_numbers(self):
        self.app.update()
        page = self.app.records_page
        self.assertEqual(len(self.rows(page.tree)), 7)
        self.assertEqual(self.app.analysis_page.tiles["rate"].value.cget("text"), "60%")
        self.assertEqual(self.app.analysis_page.tiles["failed_attempts"].value.cget("text"), "4")
        self.assertEqual([r[0] for r in self.rows(self.app.tracking_page.tree)], ["D001", "D004"])

    def test_filters_and_search(self):
        page = self.app.records_page
        page.status_var.set("Failed")
        self.assertEqual(len(self.rows(page.tree)), 3)
        page.clear_filters()
        page.search_var.set("d003")
        self.assertEqual([r[0] for r in self.rows(page.tree)], ["D003"])

    def test_every_page_and_chart_draws(self):
        for index in range(len(self.app.pages)):
            self.app.show(index)
            self.app.update()
        for spec in charts.CHARTS:
            self.app.charts_page.select(spec.key)
            self.app.update()

    def test_dialog_adds_a_redelivery_and_rejects_bad_input(self):
        dialog = self.gui.RecordDialog(self.app)
        dialog.id_var.set("D004")                        # existing delivery -> next attempt, same area
        self.assertEqual((dialog.area_var.get(), dialog.attempt_var.get()), ("Area C", "3"))
        dialog.status_var.set("Failed")                  # a failed attempt must have a reason
        dialog.reason_var.set("")
        dialog.save()
        self.assertIn("failure reason", dialog.field_errors["reason"])   # shown beside the box
        self.assertEqual(len(self.store.records), 7)
        dialog.reason_var.set("Incorrect address")
        dialog.save()
        self.assertEqual(len(self.store.records), 8)
        self.assertEqual(len(core.load_records(self.path)[0]), 8)

    def test_clicking_the_greyed_out_reason_box_switches_status_to_failed(self):
        dialog = self.gui.RecordDialog(self.app)
        self.assertEqual(str(dialog.reason_box.cget("state")), "disabled")
        self.assertIn("click here", dialog.notes["reason"].cget("text"))
        dialog._reason_clicked()
        self.assertEqual(dialog.status_var.get(), "Failed")
        self.assertEqual(str(dialog.reason_box.cget("state")), "normal")
        self.assertIn("required", dialog.notes["reason"].cget("text"))
        dialog.destroy()

    def test_nothing_overflows_the_window_at_any_size(self):
        """Every visible widget on every page must sit inside the window, small or large."""
        for size in ("1000x680", "1320x860", "1600x1000"):
            self.app.geometry(size)
            check_everything_fits(self, self.app, size)

    def test_short_windows_trade_decoration_for_table_rows(self):
        """On a 1366x768 laptop (window about 1306x658) the tables must still show several rows."""
        records, analysis = self.app.records_page, self.app.analysis_page
        for size, short in (("1306x658", True), ("1320x900", False)):
            self.app.geometry(size)
            self.app.show(self.gui.RECORDS)
            self.app.update()
            self.assertEqual((records.short, analysis.short), (short, short), size)
            self.assertEqual(records.strip_grid.winfo_ismapped(), not short)      # totals step aside
            self.app.show(self.gui.ANALYSIS)
            self.app.update()
            tiles = list(analysis.tiles.values())
            self.assertTrue(all(tile.compact == short for tile in tiles), size)
            self.assertEqual(tiles[0].hint.winfo_ismapped(), not short)           # the caption line goes first
            self.assertEqual(tiles[0].value.cget("text"), "7")                    # the numbers stay
        self.app.geometry("1306x658")
        self.app.show(self.gui.RECORDS)
        self.app.update()
        self.assertGreaterEqual(records.tree.winfo_height(), self.kit.px(250))           # about six rows
        self.app.show(self.gui.ANALYSIS)
        self.app.update()
        tree = analysis.area_tree                                                # all three areas, none cut off
        for item in tree.get_children():
            box = tree.bbox(item)
            self.assertTrue(box, "an area row is scrolled out of view")
            self.assertLessEqual(box[1] + box[3], tree.winfo_height())

    def test_a_bug_inside_a_button_is_logged_and_shown_not_silent(self):
        log = os.path.join(self.dir.name, "error_log.txt")
        with mock.patch.object(core, "LOG_FILE", log), \
                mock.patch.object(self.gui, "message") as shown:
            try:
                raise RuntimeError("boom")
            except RuntimeError as error:
                self.app.report_callback_exception(type(error), error, error.__traceback__)
        self.assertIn("boom", read_text(log))
        self.assertIn("boom", shown.call_args[0][2])   # message(app, heading, text)

    # ------------------------------------------------------------- animations --
    def animations_on(self):
        self.kit.Motion.enabled = True

    def test_count_up_runs_then_lands_on_the_exact_text(self):
        self.animations_on()
        tile = self.app.analysis_page.tiles["rate"]
        tile.set(66.666, "66.7%", "%", from_zero=True)
        self.assertTrue(tile._tween.running)
        self.assertEqual(tile.value.cget("text"), "0%")                 # starts from zero...
        self.assertTrue(self.wait_until(lambda: not tile._tween.running))
        self.assertEqual(tile.value.cget("text"), "66.7%")              # ...and ends on the exact figure

    def test_an_unchanged_number_does_not_replay(self):
        self.animations_on()
        tile = self.app.analysis_page.tiles["attempts"]
        tile.set(7, "7", from_zero=True)
        self.assertTrue(self.wait_until(lambda: not tile._tween.running))
        tile.set(7, "7")
        self.assertFalse(tile._tween.running)

    def test_with_animations_off_everything_jumps_to_the_final_state(self):
        tile = self.app.analysis_page.tiles["successful"]
        tile.set(3, "3", from_zero=True)
        self.assertEqual(tile.value.cget("text"), "3")
        self.assertFalse(tile._tween.running)

    def test_toast_slides_in_waits_and_slides_out(self):
        self.app.update()      # let the window finish its first layout, the animation runs on the clock
        self.animations_on()
        self.app.notify("Added D006", kind="success", seconds=0.6)
        chip = self.app.toast.chip
        self.assertIsNotNone(chip)
        self.assertTrue(self.wait_until(lambda: chip.winfo_x() >= 0))          # slid in to its place
        self.assertTrue(self.wait_until(lambda: self.app.toast.chip is None))  # slid out and removed

    def test_a_long_toast_message_is_shortened_to_fit(self):
        self.app.update()
        self.app.notify("C:\\very\\long\\folder\\" * 40, kind="info", seconds=0.1)
        self.app.update()
        self.assertLessEqual(self.app.toast.chip.winfo_reqwidth(), self.app.toast.winfo_width())

    def test_every_chart_plays_in_and_ends_on_the_finished_chart(self):
        self.animations_on()
        self.app.show(3)
        page = self.app.charts_page
        for spec in charts.CHARTS:
            page.select(spec.key)
            play = page._play
            self.assertTrue(play.running, spec.key)
            self.assertTrue(self.wait_until(lambda: not play.running, 6), spec.key)
            self.assertEqual(type(page.figure.get_layout_engine()).__name__, "ConstrainedLayoutEngine")

    def test_a_saved_row_flashes_then_is_selected(self):
        self.animations_on()
        new = attempt("D006", "2026-10-06", "Area B", 1, "Incorrect address", "Failed")
        self.store.add(new)
        page = self.app.records_page
        self.app.refresh_all(select=new)
        item = next(i for i, r in page.items.items() if r is new)
        self.assertEqual(tuple(page.tree.item(item, "tags")), ("flash",))
        self.assertTrue(self.wait_until(lambda: not page._flash.running))
        self.assertEqual(tuple(page.tree.item(item, "tags")), ("Failed",))   # normal look again
        self.assertEqual(page.tree.selection(), (item,))                      # and selected

    def test_buttons_fade_on_hover_and_need_a_press_and_release_to_click(self):
        self.animations_on()
        clicks = []
        button = self.kit.PillButton(self.app, "Test", lambda: clicks.append(1), "secondary")
        button.pack()
        self.app.update()
        button._set_hover(True)
        self.assertTrue(self.wait_until(lambda: button.mix == 1.0))
        self.assertEqual(button._level, button.LEVELS)
        button._set_hover(False)
        self.assertTrue(self.wait_until(lambda: button.mix == 0.0))
        event = types.SimpleNamespace(x=5, y=5)
        button._click(event)                      # a release without a press is not a click
        self.assertEqual(clicks, [])
        button._press(event)
        self.assertTrue(button.pressed)
        button._click(event)
        self.assertEqual((clicks, button.pressed), ([1], False))
        button.destroy()

    def test_tab_highlight_fades_to_the_active_tab(self):
        self.animations_on()
        self.app.show(2)
        self.assertTrue(self.wait_until(lambda: self.app.tabs[2].level["active"] == 1.0
                                        and self.app.tabs[0].level["active"] == 0.0))

    def test_the_top_bar_shows_the_logo_not_letters(self):
        logo = self.app.logo
        self.assertEqual(str(logo.cget("image")), str(self.app._logo))
        self.assertEqual(logo.cget("text"), "")
        self.assertGreaterEqual(self.app._logo.height(), 40)

    def test_the_tabs_run_along_the_top_in_the_requirements_order(self):
        self.app.geometry("1400x860")
        self.app.update()
        bar = self.app.topbar
        self.assertEqual([tab.text for tab in self.app.tabs], [name for _, name, _ in self.app.PAGES])
        xs = [tab.winfo_rootx() for tab in self.app.tabs]
        self.assertEqual(xs, sorted(xs))                                 # left to right
        for tab in self.app.tabs:
            self.assertLess(tab.winfo_rooty(), self.app.pages[0].winfo_rooty())   # above the page
            self.assertLess(tab.winfo_rooty() + tab.winfo_height(), bar.winfo_rooty() + bar.winfo_height() + 1)
        self.assertGreater(self.app.pages[0].winfo_width(), self.app.winfo_width() - 80)  # the page has the full width

    def test_every_tab_stays_fully_visible_on_narrow_windows(self):
        """Narrow windows drop the title text and the file note; the five tabs never get cut off."""
        for size, compact in (("1000x700", True), ("1400x860", False)):
            self.app.geometry(size)
            self.app.update()
            self.assertEqual(self.app.compact, compact)
            self.assertEqual(self.app.brand_words.winfo_ismapped(), not compact)
            self.assertEqual(self.app.file_note.winfo_ismapped(), not compact)
            edge = self.app.topbar.winfo_rootx() + self.app.topbar.winfo_width()
            for tab in self.app.tabs:
                self.assertTrue(tab.label.winfo_ismapped())
                self.assertLessEqual(tab.winfo_rootx() + tab.winfo_width(), edge, tab.text)
            if not compact:  # and the tabs never run into the file note
                last = self.app.tabs[-1]
                self.assertLess(last.winfo_rootx() + last.winfo_width(), self.app.file_note.winfo_rootx())

    def test_table_columns_scale_to_the_table_width(self):
        """The last column must never be cut off: column widths always fit inside the table."""
        for size in ("1000x700", "1500x900"):
            self.app.geometry(size)
            self.app.show(0)
            self.app.update()
            tree = self.app.records_page.tree
            total = sum(int(tree.column(name, "width")) for name in tree["columns"])
            self.assertLessEqual(total, tree.winfo_width())
            self.assertGreater(total, tree.winfo_width() - 30)  # and they use the room

    def test_empty_state_message_is_shown_without_rows(self):
        page = self.app.tracking_page
        self.app.show(1)
        self.app.update()
        page.tree.selection_remove(*page.tree.selection())
        page.refresh()
        self.app.update()
        self.assertTrue(page.history_tree.empty_label.winfo_ismapped())
        self.assertIn("Select a delivery", page.history_tree.empty_label.cget("text"))
        self.assertGreater(page.history_tree.empty_label.winfo_width(), 150)  # not cut off
        page.tree.selection_set(page.tree.get_children()[0])
        self.app.update()  # the selection event is delivered asynchronously
        self.assertFalse(page.history_tree.empty_label.winfo_ismapped())

    def test_dialog_blocks_attempts_after_success(self):
        dialog = self.gui.RecordDialog(self.app)
        dialog.id_var.set("D001")
        self.assertIn("already delivered", dialog.hint_var.get())
        dialog.save()
        self.assertIn("already delivered", dialog.field_errors["id"])
        dialog.destroy()

    def test_dialog_edits_a_record(self):
        record = self.store.records[0]
        dialog = self.gui.RecordDialog(self.app, record)
        dialog.status_var.set("Successful")              # reason is reset to None automatically
        self.assertEqual(dialog.reason_var.get(), "None")
        dialog.save()
        self.assertEqual(core.load_records(self.path)[0][0].status, "Successful")

    # ------------------------------------------------- forms, dialogs and calendar --
    def test_every_wrong_box_gets_its_own_message_and_fixing_it_clears_it(self):
        dialog = self.gui.RecordDialog(self.app)
        dialog.id_var.set("D006")
        dialog.status_var.set("Failed")            # a failed attempt needs a reason...
        dialog.date_var.set("18/10/2026")          # ...the date is in the wrong format...
        dialog.save()                              # ...and no area was chosen
        self.assertEqual(set(dialog.field_errors), {"date", "area", "reason"})
        self.assertEqual(str(dialog.notes["date"].cget("fg")), "#c02f2f")
        self.assertIn("YYYY-MM-DD", dialog.notes["date"].cget("text"))
        self.assertEqual(len(self.store.records), 7)             # nothing was saved
        dialog.date_var.set("2026-10-18")
        self.assertNotIn("date", dialog.field_errors)            # editing the box clears its message
        self.assertEqual(dialog.notes["date"].cget("text"), dialog.NOTES["date"])
        dialog.destroy()

    def test_calendar_moves_by_day_week_and_month_and_picks_a_date(self):
        picked = []
        anchor = tk.Frame(self.app)
        anchor.pack()
        self.app.update()
        picker = dialogs.DatePicker(anchor, date(2027, 1, 31), picked.append)
        self.assertEqual(len(picker.days), 42)                   # always six rows
        picker.move(days=1)
        self.assertEqual(picker.selected, date(2027, 2, 1))
        picker.move(days=-7)
        self.assertEqual(picker.selected, date(2027, 1, 25))
        picker.selected = date(2027, 1, 31)
        picker.move(months=1)                                    # no 31st of February
        self.assertEqual(picker.selected, date(2027, 2, 28))
        picker.move(months=-3)
        self.assertEqual(picker.selected, date(2026, 11, 28))
        self.assertEqual(picker.month_label.cget("text"), "November 2026")
        picker.change_month(2)
        self.assertEqual(picker.month_label.cget("text"), "January 2027")
        picker.choose(date(2026, 12, 25))
        self.assertEqual(picked, [date(2026, 12, 25)])
        self.assertFalse(picker.winfo_exists())
        anchor.destroy()

    def test_the_form_date_can_be_picked_from_the_calendar(self):
        dialog = self.gui.RecordDialog(self.app)
        dialog.date_var.set("2026-10-18")
        dialog.open_calendar()
        self.assertEqual(dialog.picker.selected, date(2026, 10, 18))     # opens on the date in the box
        dialog.picker.choose(date(2026, 11, 2))
        self.assertEqual(dialog.date_var.get(), "2026-11-02")
        dialog.destroy()

    def click_when_open(self, button, delay=120):
        """Press a button of the pop-up that is about to open (it blocks until closed)."""
        def press():
            box = next(w for w in self.app.winfo_children() if isinstance(w, dialogs.ModalDialog))
            getattr(box, button).invoke()
        self.app.after(delay, press)

    def test_error_messages_use_the_apps_own_dialog(self):
        self.click_when_open("ok_button")
        dialogs.message(self.app, "Could not save", "The file is open in Excel.")    # returns once OK is pressed

    # ----------------------------------------------------------- data tools --

    # ------------------------------------------------------ keyboard & tooltips --
    def test_buttons_and_tabs_can_be_reached_and_used_with_the_keyboard(self):
        calls = []
        button = self.kit.PillButton(self.app, "Go", lambda: calls.append("go"), "secondary")
        button.pack()
        self.app.update()
        self.assertTrue(int(str(button.cget("takefocus"))))              # Tab can reach it
        button._key(None)                                                # what Space / Enter do
        self.assertEqual(calls, ["go"])
        button._set_focus(True)                                          # focus shows a ring
        self.assertTrue(any(key[0] == "pill" and key[-1] == self.kit.FOCUS for key in self.kit._images))
        button.set_enabled(False)
        self.assertFalse(int(str(button.cget("takefocus"))))             # a greyed-out button is skipped
        button._key(None)
        self.assertEqual(calls, ["go"])
        button.destroy()
        item = self.app.tabs[2]
        self.assertTrue(int(str(item.cget("takefocus"))))
        item.focus_force()
        self.app.update()
        item.event_generate("<Return>")                                  # a real key press opens the page
        self.app.update()
        self.assertTrue(item.active)
        for key in ("<Return>", "<space>"):
            self.assertTrue(self.app.tabs[0].bind(key), f"tab has no {key}")

    def test_the_file_note_says_where_the_records_are_saved_when_it_is_not_the_program_folder(self):
        self.assertIn("delivery_records.csv", self.app.file_var.get())
        self.assertEqual(self.app.file_tip.current_text(), f"Saved in: {self.dir.name}")   # the test file is elsewhere
        with mock.patch.object(core, "BASE_DIR", self.dir.name):
            self.assertEqual(self.app.file_tip.current_text(), "")        # the program's own folder: nothing to add

    def test_text_boxes_show_a_focus_ring(self):
        entry = self.app.records_page.search_entry
        shell = entry.master.master
        entry.focus_force()
        self.app.update()
        self.assertEqual(shell.ring, self.kit.FOCUS)
        self.app.records_page.edit_button.focus_force()
        self.app.update()
        self.assertIsNone(shell.ring)

    def test_a_tooltip_explains_why_edit_is_greyed_out(self):
        page = self.app.records_page
        tip = page.edit_tip
        self.assertFalse(page.edit_button.enabled)
        tip.show()
        self.assertIsNotNone(tip.window)
        self.assertEqual(tip.window.winfo_children()[0].cget("text"), "Select a record in the table first")
        tip.hide()
        self.assertIsNone(tip.window)
        page.tree.selection_set(page.tree.get_children()[0])
        self.app.update()
        self.assertEqual(tip.current_text(), "")                         # enabled: nothing to explain

    # ----------------------------------------------- nothing beyond the requirements --
    def test_the_window_has_no_controls_beyond_the_requirements(self):
        """The requirements ask for Add, View/Search, Update, Filter, analysis and charts - nothing else."""
        buttons = lambda root: [w.text for w in descendants(root) if isinstance(w, self.kit.PillButton)]
        self.assertEqual(buttons(self.app.records_page), ["+  Add delivery", "Edit", "Clear filters"])
        self.assertEqual(buttons(self.app.charts_page), [spec.title for spec in charts.CHARTS])
        self.assertEqual(buttons(self.app.tracking_page) + buttons(self.app.analysis_page), [])
        self.assertEqual(buttons(self.app.topbar), [])                   # no reload, no animations switch
        self.assertFalse(hasattr(self.app.charts_page, "period_var"))    # no day/week/month chooser
        self.assertFalse(hasattr(self.app, "delete_record"))             # the requirements have no Delete
        names = [name for _, name, _ in self.app.PAGES]
        self.assertEqual(names, ["Records", "Redelivery Tracking", "Analysis", "Charts"])   # no Requirements / Guide page

    def test_the_form_has_the_six_required_fields_and_one_calendar_button(self):
        dialog = self.gui.RecordDialog(self.app)
        captions = [w.cget("text") for w in dialog.body.grid_slaves(column=0)
                    if isinstance(w, tk.Label) and w.cget("text") in dict(dialogs.FIELD_CAPTIONS).values()]
        self.assertEqual(sorted(captions), sorted(["Delivery ID", "Delivery Date", "Delivery Area",
                                                   "Attempt Number", "Failure Reason", "Final Status"]))
        self.assertEqual(sorted(w.text for w in descendants(dialog) if isinstance(w, self.kit.PillButton)),
                         ["Calendar", "Cancel", "Save"])
        dialog.destroy()

    def test_the_row_under_the_pointer_is_highlighted(self):
        self.app.update()
        tree = self.app.records_page.tree
        item = tree.get_children()[0]                                    # D001 attempt 1: Failed
        x, y, width, height = tree.bbox(item)
        tree.event_generate("<Motion>", x=x + 20, y=y + height // 2)
        self.app.update()
        self.assertEqual(tuple(tree.item(item, "tags")), ("Failed_hover",))
        tree.event_generate("<Leave>")
        self.app.update()
        self.assertEqual(tuple(tree.item(item, "tags")), ("Failed",))

    # ------------------------------------------------------- the requirements document --
    def test_the_window_uses_the_required_field_names(self):
        self.assertEqual([c[0] for c in self.gui.RecordsPage.COLUMNS], core.FIELDS)
        self.assertEqual([spec.title for spec in charts.CHARTS],
                         ["Failed Deliveries by Reason", "Delivery Success Rate by Area",
                          "Redelivery Trends", "Delivery Status"])
        self.assertEqual([c[0] for c in self.gui.TrackingPage.HISTORY],
                         ["Attempt Number", "Delivery Date", "Failure Reason", "Final Status"])


class ScalingTests(TempStoreCase):
    """The window must also fit on 125% / 150% Windows display scaling."""

    def test_everything_fits_and_keeps_its_proportions_at_150_percent(self):
        import delivery_gui
        import delivery_ui_kit as ui
        import tkinter

        self.original_scaling = []

        def fake_init(root):
            self.original_scaling.append(root.tk.call("tk", "scaling"))
            root.tk.call("tk", "scaling", 1.5 * 96 / 72)  # like a 144 dpi screen
            ui.init_scaling(root)

        before = ui.Motion.enabled
        with mock.patch.object(delivery_gui, "os_animations_enabled", return_value=False), \
                mock.patch.object(delivery_gui, "init_scaling", fake_init):
            try:
                app = delivery_gui.DeliveryApp(self.store)
            except tkinter.TclError as error:
                self.skipTest(f"Tk not available: {error}")
            try:
                self.assertEqual(ui.Scale.factor, 1.5)
                self.assertEqual(ui.px(38), 57)
                button = app.records_page.add_button
                self.assertEqual(int(button.cget("height")), ui.px(38))    # buttons grew with the text
                app.geometry(f"{ui.px(1000)}x{ui.px(680)}")
                check_everything_fits(self, app, "150%")
            finally:
                # the scaling belongs to the whole display, so put it back for the tests that follow
                app.tk.call("tk", "scaling", self.original_scaling[0])
                app.destroy()
                ui.Scale.factor = 1.0
                ui.Motion.enabled = before


class AccessibilityTests(unittest.TestCase):
    def test_contrast_ratio_matches_the_wcag_definition(self):
        self.assertAlmostEqual(kit.contrast_ratio("#000000", "#ffffff"), 21.0, places=1)
        self.assertAlmostEqual(kit.contrast_ratio("#777777", "#777777"), 1.0, places=2)

    def test_every_text_colour_pair_meets_its_contrast_target(self):
        for name, foreground, background, minimum in kit.TEXT_PAIRS:
            self.assertGreaterEqual(kit.contrast_ratio(foreground, background), minimum,
                                    f"{name}: {foreground} on {background}")


class FieldErrorTests(TempStoreCase):
    def test_validate_fields_names_the_box_with_the_problem(self):
        delivered = attempt("D001", "2026-10-09", "Area A", 3, "None", "Successful")   # D001 already succeeded
        self.assertEqual(list(core.validate_fields(delivered, self.store.records)), ["id"])
        incomplete = attempt("D006", "2026-10-09", "", 0, "None", "Failed")
        self.assertEqual(list(core.validate_fields(incomplete, self.store.records)),
                         ["area", "attempt", "reason"])                                # in form order

    def test_make_attempt_reports_every_problem_at_once_when_given_the_records(self):
        with self.assertRaises(core.ValidationError) as caught:
            core.make_attempt("D006", "18/10/2026", "", "1", "None", "Failed", records=self.store.records)
        self.assertEqual(set(caught.exception.fields), {"date", "area", "reason"})
        with self.assertRaises(core.ValidationError) as caught:     # without records: only what can't be read
            core.make_attempt("D006", "18/10/2026", "", "1", "None", "Failed")
        self.assertEqual(set(caught.exception.fields), {"date"})

    def test_the_stores_errors_carry_the_fields(self):
        with self.assertRaises(core.ValidationError) as caught:
            self.store.add(attempt("D004", "2026-10-09", "Area C", 2, "None", "Pending"))   # attempt 2 exists
        self.assertEqual(list(caught.exception.fields), ["attempt"])


if __name__ == "__main__":
    unittest.main()
