# Logical Operators
# Combine multiple conditions to make complex decisions.

# "and" — both must be True
# "or"  — at least one must be True
# "not" — flips True to False (and vice versa)

# === A theme park ride checker ===
print("=== Theme Park Ride Checker ===")
height = int(input("Your height in cm: "))
age = int(input("Your age: "))
has_parent = input("Is a parent with you? (y/n): ").lower() == "y"

# Roller coaster: must be tall enough AND old enough
can_ride_coaster = height >= 140 and age >= 10

# Bumper cars: tall enough OR has a parent
can_ride_bumper = height >= 120 or has_parent

# Haunted house: old enough AND NOT too young
can_ride_haunted = age >= 13 and not (age < 8)

print(f"\nRoller Coaster: {'Yes!' if can_ride_coaster else 'No'}")
print(f"Bumper Cars:    {'Yes!' if can_ride_bumper else 'No'}")
print(f"Haunted House:  {'Yes!' if can_ride_haunted else 'No'}")

# === Short-circuit evaluation ===
# Python stops checking as soon as it knows the result.
items = []
# "and" stops at the first False value
if items and items[0] == "apple":
    print("First item is apple")
else:
    print("\nList is empty or doesn't start with apple")
# This is safe! Python never checks items[0] because items is empty.
