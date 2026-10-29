# Failed Delivery and Redelivery Pattern Analyzer Using Python
### Terminal version

A simple program for recording delivery attempts, finding out why deliveries fail, tracking which
deliveries needed a redelivery, and seeing the results as tables and charts. **No coding needed.**

This is the **console-based, menu-driven program** that the project requirements describe. There is no
window and no buttons: you type a number, press Enter, and the program answers. It contains what the
requirements list: the **12 required features**, the CSV file **delivery_records.csv**, and the
**four Matplotlib charts**. (The version with a graphical window is in the folder
`Failed Delivery Analyzer`; it uses the same rules and gives the same numbers.)

---

## How to start it

**Step 1 - Install Python (one time only).** Skip if the computer already has it.
1. Go to **https://www.python.org/downloads/** and click the big yellow **Download Python** button.
2. Open the downloaded file.
3. **IMPORTANT:** at the bottom of the first screen tick **"Add python.exe to PATH"**.
4. Click **Install Now**, wait for "Setup was successful", then **Close**.

**Step 2 - Open the program.** Double-click **run.bat** in this folder.
The first time it downloads one extra tool (matplotlib, about 1 minute, needs internet).
After that it opens at once. Or, in a terminal opened in this folder: `python main.py`

---

## How to use it

Type the number of what you want and press **Enter**. After each result the program waits for you to
press **Enter** again, so you can read it before the menu comes back.

```
==========================================================================
  FAILED DELIVERY AND REDELIVERY PATTERN ANALYZER USING PYTHON
==========================================================================
   1. Add Delivery Records           7. Delivery Success Rate Calculation
   2. View and Search Deliveries     8. Area-Based Delivery Analysis
   3. Update Delivery Records        9. Delivery Trend Monitoring
   4. Filter Delivery Records       10. Delivery Summary
   5. Failed Delivery Analysis      11. Data Visualization
   6. Redelivery Tracking           12. Save and Load Records
   0. Exit  (records are saved after every change)
--------------------------------------------------------------------------
```

| # | Required feature | What you do / what you see |
|---|---|---|
| 1 | Add Delivery Records | Answer the questions: Delivery ID, area, date, final status, and the failure reason. Just press Enter at the first question to go back. |
| 2 | View and Search Deliveries | Shows every saved record. Type a Delivery ID (or part of one, like `D004`) to find a delivery. |
| 3 | Update Delivery Records | Type the Delivery ID (and the attempt number if it has several), then press Enter to keep a value or type a new one. |
| 4 | Filter Delivery Records | Pick an area, a status, a failure reason and/or a number of attempts (Enter skips a filter). |
| 5 | Failed Delivery Analysis | The failure reasons with their counts, and the most common one. |
| 6 | Redelivery Tracking | The number of attempts each delivery needed, and which ones were redelivered. |
| 7 | Delivery Success Rate Calculation | The percentage of deliveries completed successfully. |
| 8 | Area-Based Delivery Analysis | Deliveries, successes, failed attempts and success rate for each area, and the weakest area. |
| 9 | Delivery Trend Monitoring | Failed attempts and redelivery attempts for each day. |
| 10 | Delivery Summary | Total attempts, successful and failed deliveries, deliveries requiring redelivery, the most common failure reason, and the success rate by area. |
| 11 | Data Visualization | Opens the charts (see below). |
| 12 | Save and Load Records | Save the records to the CSV file, or load them from it again. (This also happens by itself, see below.) |

**The four charts (menu 11).** Choose one, or all four. Each opens in its own Matplotlib window:
*Failed Deliveries by Reason Bar Chart*, *Delivery Success Rate by Area Bar Chart*,
*Redelivery Trends Line Graph* and *Delivery Status Pie Chart*. **Close the chart window(s) to return
to the menu.** The buttons at the bottom of a chart window (zoom, save as picture...) are Matplotlib's own.

**Adding a redelivery:** choose 1 and type the **same Delivery ID** again. The area and the next attempt
number are filled in by themselves.

**Tips**
- Dates are written like this: **2026-10-12** (year-month-day). Pressing Enter uses today's date.
  Years from 2000 to 2100 are accepted. If a date is written wrongly (or the year is a typo such as 0026),
  the program says so and asks again.
- A **Successful** attempt has no failure reason. A **Failed** attempt needs one: pick one from the
  list, or choose *Other* and type your own. A **Pending** attempt may have one, or not.
- A delivery that has already succeeded cannot get more attempts, and a successful attempt has to be the
  last attempt of its delivery (Update refuses a change that would break this).
- If something is wrong, the program says what, and nothing is saved.
- The program comes with the **sample records** from the requirements so you can try everything. They are not real.
- **Ctrl+C**, or closing the window, is safe: everything is already saved.
- Use **one window** of the program at a time: each window keeps its own copy of the records in memory.

### How the numbers are defined
The file has **one row per delivery attempt**, as the requirements' note says: a delivery that needs a
redelivery appears on several rows with the same Delivery ID.

- **Unique delivery:** one Delivery ID. Its status is the Final Status of its *latest* attempt.
- **Failed attempt:** an attempt with a failure reason (or status Failed). A Pending attempt that records
  a reason counts as a failed attempt too.
- **Deliveries requiring redelivery:** unique deliveries with more than one attempt.
- **Delivery success rate (overall and per area):** successful unique deliveries / all unique deliveries.
  Pending deliveries are not successful yet, so they stay in the total.
- **Redelivery attempts (trend chart and menu 9):** attempts numbered 2 or higher, counted per day.

With the sample records this gives: 7 attempts, 5 deliveries, 3 successful, 4 failed attempts, 2 deliveries
requiring redelivery, success rate 60%, most common failure reason *Recipient unavailable*; by area:
Area A 100%, Area B 50%, Area C 0%.

---

## Where your information is saved

| File | What is inside |
|---|---|
| **delivery_records.csv** | Every delivery attempt: Delivery ID, Delivery Date, Delivery Area, Attempt Number, Failure Reason, Final Status |
| **error_log.txt** | Only appears if something goes wrong (useful to send to the programmer) |
| **delivery_records_backup.csv** | Only appears if some rows of the file could not be read and you then updated a record or saved by hand: a copy of the original file, so those rows are not lost |

They are in the same folder as the program. If Windows blocks that folder (for example it is under
`Program Files`, or Windows Security's **Controlled folder access** does not let Python write in
Documents), the program saves them in `C:\Users\<your name>\AppData\Local\Delivery-Analyzer-Terminal`
instead. It tells you so when it starts, and menu 12 shows the exact path. (To keep the records next to the
program, put the program folder somewhere Windows does not protect, such as `C:\Delivery Analyzer`, or allow
Python in Windows Security > Ransomware protection > Controlled folder access.)

The program **loads** the file whenever it starts and **saves** after every change, so you never need to
save by hand. You can open **delivery_records.csv** in Excel to look at it, but **do not save it from Excel**: Excel can
change how the dates are written (for example 1/10/2026), and the program can no longer read them. Close it
in Excel before you add or update records in the program, or the program cannot save (it tells you, and
nothing is lost). If you must save from Excel, choose **CSV UTF-8** and check that dates still look like 2026-10-12.

## Start fresh (remove the sample data)
1. Close the program.
2. Open **delivery_records.csv** with Notepad (right-click, **Open with**, **Notepad**).
3. Delete everything **except the first line**, then save.

To get the sample records back, delete **delivery_records.csv** completely. The next start recreates it.

## Move it to another computer
Copy the **whole program folder**. Your records travel with it inside **delivery_records.csv** (if the program
told you at the start that your records are kept in the AppData folder, copy **delivery_records.csv** from
there into the program folder as well). The other computer needs Python too (Step 1 above).

---

## Something went wrong?

| Problem | What to do |
|---|---|
| "Python is not installed" (run.bat) | Do Step 1 above, and make sure you ticked **Add python.exe to PATH**. |
| It can't download matplotlib (run.bat) | Connect to the internet and double-click **run.bat** again. |
| "...installed without Tk" (run.bat) | The menu works, but charts cannot open. Run the Python installer again, choose **Modify**, and tick **tcl/tk and IDLE**. |
| "Could not write the file" | Close **delivery_records.csv** if it is open in Excel, then try again. Nothing is lost. |
| "Some rows ... could not be read" at the start | A few lines in the file are damaged (for example a date not written as 2026-10-12). The program ignores them and keeps working. Fix those lines in Notepad. If you update a record before fixing them, the program keeps the original file as **delivery_records_backup.csv**, so the lines are not lost. |
| The black window closes by itself (run.bat) | Open a terminal in this folder and type `python main.py` to see the message. |
| "The program stopped unexpectedly" | Your records are safe. Details are in **error_log.txt** in the data folder. |

*Using a Mac or Linux? The program was made on Windows, but open a terminal in the folder and run:*
`python3 -m pip install -r requirements.txt` *then* `python3 main.py`

---

## For programmers

Only the Python standard library is used, plus **Matplotlib** for the charts (it is loaded only when you
open menu 11). There is no window code in this folder.

| File | Purpose |
|---|---|
| `main.py` | starts the menu; writes error_log.txt if the program crashes |
| `delivery_console.py` | the menu and the 12 features, in the requirements' order |
| `delivery_core.py` | CSV file handling (`csv` module), validation and all analysis |
| `delivery_charts.py` | the four Matplotlib charts |
| `sample_data/delivery_records.csv` | the requirements' sample records; a fresh install starts from this |
| `run.bat` | launcher that installs what is missing, then starts the program |
| `requirements.txt` | matplotlib |
