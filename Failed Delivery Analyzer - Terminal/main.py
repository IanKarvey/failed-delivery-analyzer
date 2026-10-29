"""
Failed Delivery and Redelivery Pattern Analyzer Using Python   (terminal version)

    python main.py

A menu in this terminal with the 12 required features. The records are kept in
delivery_records.csv, in the same folder as the program. Most people just double-click run.bat.
"""

import sys
import traceback


def main():
    try:
        import delivery_console
        delivery_console.main()
    except Exception as error:  # a bug: keep a record of it instead of just vanishing
        import delivery_core
        log = delivery_core.log_error(traceback.format_exc())
        print(f"\nThe program stopped unexpectedly: {error}\n"
              f"Your records are safe. Details were saved to: {log}")
        sys.exit(1)  # run.bat sees this and keeps its window open


if __name__ == "__main__":
    main()
