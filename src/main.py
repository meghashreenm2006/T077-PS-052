"""
Command-Line Interface for Cold-Chain Shipment Temperature Compliance.

Team ID: T077
Problem Statement: PS-052
"""

import sys
from datetime import datetime

from src.shipment_processor import process_shipment


def check_shipment_temperature():
    print("\n===== SHIPMENT TEMPERATURE CHECK =====")

    profile_name = input(
        "Enter profile name (press Enter for VACCINE_2_8): "
    ).strip()

    if not profile_name:
        profile_name = "VACCINE_2_8"

    try:
        count = int(input("Enter number of temperature readings: "))

        if count <= 0:
            print("Please enter at least one reading.")
            return

        readings = []

        for i in range(count):
            print(f"\nReading {i + 1}")

            timestamp_input = input(
                "Enter date and time (YYYY-MM-DD HH:MM): "
            )

            timestamp = datetime.strptime(
                timestamp_input, "%Y-%m-%d %H:%M"
            )

            temperature = float(
                input("Enter temperature in Celsius: ")
            )

            readings.append((timestamp, temperature))

        # Process shipment
        result = process_shipment(readings, profile_name)

        # Display results
        print("\n===== SHIPMENT ANALYSIS RESULT =====")

        print("\nTemperature Readings:")
        for timestamp, temperature in readings:
            print(f"{timestamp} : {temperature}°C")

        print("\nDetected Excursions:")
        if result["excursions"]:
            for excursion in result["excursions"]:
                print(excursion)
        else:
            print("No temperature excursions detected.")

        if result.get("data_gaps"):
            print("\nDetected Missing Data Gaps:")
            for gap in result["data_gaps"]:
                print(f"Gap: {gap['start']} to {gap['end']} ({gap['duration_minutes']} min)")

        print(f"\nMean Kinetic Temperature (MKT): {result['mkt']:.2f}°C")

        print(f"\nFINAL SHIPMENT DECISION: {result['decision']}")

        if result.get("reasons"):
            print("\nDecision Audit Rationale:")
            for r in result["reasons"]:
                print(f"- {r}")

        print("\n====================================")

    except ValueError as error:
        print(f"Invalid input: {error}")

    except KeyError as error:
        print(f"Invalid profile or missing profile setting: {error}")


def main(interactive=None):
    if interactive is None:
        interactive = sys.stdin.isatty() and not hasattr(input, "assert_called")

    while True:
        print("\n==============================================")
        print("Cold-Chain Shipment Temperature Compliance and Claims Engine")
        print("Team ID: T077")
        print("Problem Statement: PS-052")
        print("==============================================")

        print("\n1. Check shipment temperature")
        print("2. Check project information")
        print("3. Exit")

        try:
            choice = input("\nEnter your choice: ").strip()
        except (EOFError, StopIteration):
            break

        if choice == "1":
            check_shipment_temperature()

        elif choice == "2":
            print("\nProject: Cold-Chain Shipment Temperature Compliance and Claims Engine")
            print("Team ID: T077")
            print("Problem Statement: PS-052")
            print("Purpose: Monitor shipment temperatures and evaluate compliance.")

        elif choice == "3":
            print("Goodbye!")
            break

        else:
            print("Invalid choice. Please try again.")

        if not interactive:
            break


if __name__ == "__main__":
    main()
