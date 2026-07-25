# Comments & Readability
# Good code is code that humans can read easily.

# === Single-line comments ===
# This is a comment — Python ignores it.
# Use comments to explain WHY, not WHAT.

# Bad comment (describes what the code already says):
x = 5  # Set x to 5

# Good comment (explains the reasoning):
max_retries = 5  # Server times out after 5 failed attempts

# === Multi-line strings as documentation ===
def calculate_bmi(weight_kg, height_m):
    """Calculate Body Mass Index.

    Args:
        weight_kg: Weight in kilograms
        height_m: Height in meters

    Returns:
        BMI as a float, rounded to 1 decimal.
    """
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 1)

# === Good variable names ===
# Bad:  a = 70; b = 1.75
# Good:
weight = 70
height = 1.75
result = calculate_bmi(weight, height)
print(f"BMI for {weight}kg at {height}m: {result}")

# You can read the docstring with help()
help(calculate_bmi)
