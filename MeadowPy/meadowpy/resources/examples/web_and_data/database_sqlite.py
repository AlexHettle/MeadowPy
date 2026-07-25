# Database (SQLite)
# SQLite is a lightweight database built into Python.

import sqlite3

# === Create an in-memory database ===
# Use ":memory:" for a temporary database (no file created)
conn = sqlite3.connect(":memory:")
cursor = conn.cursor()

# === Create a table ===
cursor.execute("""
    CREATE TABLE students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        grade REAL,
        subject TEXT
    )
""")

# === Insert data ===
students = [
    ("Alice", 92.5, "Math"),
    ("Bob", 85.0, "Science"),
    ("Charlie", 78.3, "Math"),
    ("Diana", 95.1, "Science"),
    ("Eve", 88.7, "Math"),
]

# executemany inserts multiple rows at once
cursor.executemany(
    "INSERT INTO students (name, grade, subject) VALUES (?, ?, ?)",
    students
)
conn.commit()
print(f"Inserted {len(students)} students")

# === Query data ===
print("\nAll students:")
for row in cursor.execute("SELECT * FROM students"):
    print(f"  {row}")

# === Filtered query ===
print("\nMath students with grade > 80:")
cursor.execute(
    "SELECT name, grade FROM students WHERE subject = ? AND grade > ?",
    ("Math", 80)
)
for name, grade in cursor.fetchall():
    print(f"  {name}: {grade}")

# === Aggregate functions ===
cursor.execute("SELECT AVG(grade), MAX(grade), MIN(grade) FROM students")
avg, max_g, min_g = cursor.fetchone()
print(f"\nStats: avg={avg:.1f}, max={max_g}, min={min_g}")

# === Always close the connection ===
conn.close()
print("\nDatabase closed. (In-memory DB is now gone)")
