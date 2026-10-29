# Failed Delivery and Redelivery Pattern Analyzer

A simple program for recording delivery attempts, finding out why deliveries fail, tracking which
deliveries needed a redelivery, and seeing the results in tables and charts. **No coding needed.**

It was built to the project requirements and contains everything they describe: the 12 required features, a CSV file for the records, and four Matplotlib charts.

---

## Easiest way: the no-install version (no Python needed)

1. Copy the whole **`dist\Delivery Analyzer`** folder to the computer (a USB flash drive is fine).
   Or send the single file **`dist\Delivery-Analyzer.zip`**, and unzip it on the other computer.
2. Open the folder and double-click **Delivery Analyzer.exe**.

That's all. Nothing to install, no internet needed. Keep the **`_internal`** folder next to the
.exe: it is part of the program.

> **Windows says "Windows protected your PC"?** The program is not digitally signed, so Windows
> asks once. Click **More info**, then **Run anyway**. If an antivirus blocks it, choose to allow it.

The first start takes a few seconds (you will see a small "Starting up..." box). Later starts are quicker.

---

## The other way: run it with Python (run.bat)

Use this if you want to read or change the program itself.

**Step 1 - Install Python (one time only).** Skip if the computer already has it.
1. Go to **https://www.python.org/downloads/** and click the big yellow **Download Python** button.
2. Open the downloaded file.
3. **IMPORTANT:** at the bottom of the first screen tick **"Add python.exe to PATH"**.
4. Click **Install Now**, wait for "Setup was successful", then **Close**.

**Step 2 - Open the program.** Double-click **run.bat** in the program folder.
The first time it downloads two extra tools (matplotlib and pillow, about 1 minute, needs internet).
After that it opens at once.

The requirements describe a console program, so that version is included too: double-click
**run_console.bat** for a text menu. It uses the same records.

### Making the no-install version yourself
Only needed if you changed the code. Double-click **build_exe.bat** (needs Python and internet once,
takes a few minutes). The finished program appears in **dist\Delivery Analyzer**, and a ready-to-share
**dist\Delivery-Analyzer.zip** next to it.

---

## What is in it (the requirements' features)

Click the tabs along the top of the window: **Records**, **Redelivery Tracking**, **Analysis** and **Charts**.

| Required feature | Where |
|---|---|
| Add Delivery Records | **Records**: **+ Add delivery**. The form has the six fields of the requirements. |
| View and Search Deliveries | **Records**: the table, and **Search Delivery ID**. |
| Update Delivery Records | **Records**: select a row, then **Edit** (or double-click the row). |
| Filter Delivery Records | **Records**: area, status, failure reason, attempts per delivery. **Clear filters** resets. |
| Failed Delivery Analysis | **Analysis**: the failure reasons table and the most common failure reason. |
| Redelivery Tracking | **Redelivery Tracking**: attempts per delivery. Click a delivery to see each attempt. |
| Delivery Success Rate Calculation | **Analysis**: the delivery success rate. |
| Area-Based Delivery Analysis | **Analysis**: delivery success rate by area (the lowest is marked). |
| Delivery Trend Monitoring | **Charts**: Redelivery Trends. |
| Delivery Summary | **Analysis**: the summary tiles. |
| Data Visualization | **Charts**: Failed Deliveries by Reason, Delivery Success Rate by Area, Redelivery Trends, Delivery Status. |
| Save and Load Records | **delivery_records.csv**: loaded when the program starts, saved after every change. |

**Adding a redelivery:** add another record with the **same Delivery ID**. The area and the next
attempt number fill in by themselves.

**Tips**
- Dates are written like this: **2026-10-12** (year-month-day), or choose one with **Calendar**.
- A **Successful** attempt has no failure reason. A **Failed** attempt needs one: pick one from the
  list or type your own. The *Failure Reason* box is greyed out while the status is Successful; click it
  to switch the status to Failed.
- A delivery that has already succeeded cannot get more attempts.
- When something is wrong in the form, a message appears next to each box that needs fixing.
- The program comes with the **sample records** from the requirements so you can try everything. They are not real.

### How the numbers are defined
The file has **one row per delivery attempt**. A delivery that needs a redelivery appears on several
rows with the same Delivery ID.

- **Unique delivery:** one Delivery ID. Its status is the Final Status of its *latest* attempt.
- **Failed attempt:** an attempt with a failure reason (or status Failed). A Pending attempt that records
  a reason counts as a failed attempt too.
- **Requiring redelivery:** a unique delivery with more than one attempt.
- **Delivery success rate (per area and overall):** successful unique deliveries / all unique deliveries.
  Pending deliveries are not successful yet, so they stay in the total.
- **Redelivery attempts (trend chart):** attempts numbered 2 or higher, counted per day.

---

## Where your information is saved

| File | What is inside |
|---|---|
| **delivery_records.csv** | Every delivery attempt |
| **error_log.txt** | Only appears if something goes wrong (useful to send to the programmer) |

They are in the same folder as the program. If Windows blocks that folder (for example it is under
`Program Files`), the program saves them in `C:\Users\<your name>\AppData\Local\Delivery-Analyzer`
instead. Point at the file name at the top right of the window to see that path.

The program saves after every change, so you never need to press a "save" button.
You can open **delivery_records.csv** in Excel to look at it. Close it there before you add or edit
records in the program, or the program cannot save (it tells you, and nothing is lost).

## Start fresh (remove the sample data)
1. Close the program.
2. Open **delivery_records.csv** with Notepad (right-click, **Open with**, **Notepad**).
3. Delete everything **except the first line**, then save.

To get the sample records back, delete **delivery_records.csv** completely. The next start recreates it.

## Move it to another computer
Copy the **whole program folder** (or the **dist\Delivery Analyzer** folder). Your records travel with it
inside **delivery_records.csv** if that file is in the folder. If pointing at the file name (top right) shows an `AppData`
path, copy **delivery_records.csv** from there into the program folder first.

Use **one window at a time** on the same records: each window keeps its own copy in memory.

---

## Something went wrong?

| Problem | What to do |
|---|---|
| "Python is not installed" (run.bat) | Do Step 1 above, and make sure you ticked **Add python.exe to PATH**. Or use the no-install version. |
| It can't download the extra tools (run.bat) | Connect to the internet and double-click **run.bat** again. |
| "...installed without Tk" (run.bat) | Run the Python installer again, choose **Modify**, and tick **tcl/tk and IDLE**. |
| "Could not write the CSV file" | Close **delivery_records.csv** if it is open in Excel, then try again. Nothing is lost. |
| "Some rows ... could not be read" message | A few lines in the file are damaged (for example a date not written as 2026-10-12). The program ignores them and keeps working. Fix or delete those lines in Notepad. |
| Nothing happens when I double-click | Wait a few seconds (the first start is slow). If still nothing, right-click and choose **Run as administrator**. |
| A "Something went wrong" box | Your records are safe. Details are in **error_log.txt** in the data folder. |

*Using a Mac or Linux? The program was made on Windows, but open a terminal in the folder and run:*
`python3 -m pip install -r requirements.txt` *then* `python3 main.py`

---

## For programmers

The window follows the size of the screen and the Windows display scaling (125%, 150%...), can be used
with the keyboard (Tab, Space, Enter, Esc; a ring shows where you are), and its text colours are checked
against the WCAG contrast ratio by a test. Small animations (numbers counting up, charts drawing in, a saved
row lighting up) are built in and follow Windows' own "Show animations" setting.

| File | Purpose |
|---|---|
| `main.py` | starts the window (with a "Starting up..." box), or the text menu with `--console` |
| `delivery_core.py` | CSV file handling, validation and all analysis (no screen code) |
| `delivery_charts.py` | the four Matplotlib charts, shared by the window and the console |
| `delivery_gui.py` | the window: the Records, Redelivery Tracking, Analysis and Charts pages |
| `delivery_dialogs.py`, `delivery_widgets.py`, `delivery_ui_kit.py` | the add / edit form and calendar, shared widgets, and the look (rounded cards, pill buttons, animation engine) |
| `delivery_console.py` | the text-menu version, in the requirements' feature order |
| `sample_data/delivery_records.csv` | the requirements' sample records; a fresh install starts from this |
| `run.bat`, `run_console.bat` | launchers that install what is missing, then start the program |
| `build_exe.bat`, `build_exe.py` | build the no-install version with PyInstaller |
| `requirements.txt` | matplotlib and pillow |
| `test_delivery_analyzer.py` | the tests: `python -m unittest -v` |
