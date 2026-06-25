# Nested Structures
# Real data often combines lists and dictionaries.

# A list of dictionaries — like a mini database
students = [
    {"name": "Alice", "grade": 92, "subject": "Math"},
    {"name": "Bob", "grade": 85, "subject": "Science"},
    {"name": "Charlie", "grade": 78, "subject": "Math"},
    {"name": "Diana", "grade": 95, "subject": "Science"},
    {"name": "Eve", "grade": 88, "subject": "Math"},
]

# Print all students
print("All students:")
for s in students:
    print(f"  {s['name']:10} {s['subject']:8} Grade: {s['grade']}")

# Filter: only Math students
math_students = [s for s in students if s["subject"] == "Math"]
print(f"\nMath students: {len(math_students)}")

# Find the highest grade
top = max(students, key=lambda s: s["grade"])
print(f"Top student: {top['name']} with {top['grade']}")

# Calculate average grade
avg = sum(s["grade"] for s in students) / len(students)
print(f"Class average: {avg:.1f}")

# Group by subject
by_subject = {}
for s in students:
    subj = s["subject"]
    if subj not in by_subject:
        by_subject[subj] = []
    by_subject[subj].append(s["name"])

print("\nGrouped by subject:")
for subj, names in by_subject.items():
    print(f"  {subj}: {', '.join(names)}")
