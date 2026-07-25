# CSV Files
# CSV = Comma-Separated Values, a common data format.
# Think of it like a simple spreadsheet.

import csv

# === Writing a CSV file ===
students = [
    ["Name", "Age", "Grade"],  # Header row
    ["Alice", 14, "A"],
    ["Bob", 15, "B+"],
    ["Charlie", 14, "A-"],
]

with open("students.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerows(students)  # Write all rows at once
print("CSV file written!")

# === Reading a CSV file ===
print("\nReading students.csv:")
with open("students.csv", "r") as f:
    reader = csv.reader(f)
    header = next(reader)  # First row is the header
    print(f"  Columns: {header}")
    for row in reader:
        print(f"  {row[0]:10} Age: {row[1]}  Grade: {row[2]}")

# === Using DictReader for named columns ===
print("\nWith DictReader:")
with open("students.csv", "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Access columns by name instead of index!
        print(f"  {row['Name']} is {row['Age']} and got {row['Grade']}")
