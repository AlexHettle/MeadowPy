# Dictionaries
# A dictionary stores key-value pairs.
# Think of it like a real dictionary: word -> definition.
# Dictionaries use curly braces: {}

# Create a dictionary
student = {
    "name": "Alice",
    "age": 14,
    "grade": "A",
    "hobbies": ["reading", "coding"]
}

# Access values by key
print(f"Name: {student['name']}")
print(f"Age: {student['age']}")

# .get() is safer — returns None if key doesn't exist
print(f"Email: {student.get('email', 'not set')}")

# Add or change values
student["email"] = "alice@example.com"  # Add new key
student["age"] = 15                      # Update existing key

# Loop through a dictionary
print("\nAll student info:")
for key, value in student.items():
    print(f"  {key}: {value}")

# Check if a key exists
if "name" in student:
    print(f"\nStudent name is {student['name']}")

# Useful dictionary methods
print(f"\nKeys: {list(student.keys())}")
print(f"Values: {list(student.values())}")
