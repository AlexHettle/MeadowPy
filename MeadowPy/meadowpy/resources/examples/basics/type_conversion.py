# Type Conversion
# Sometimes you need to convert data from one type to another.

# input() always gives you a string, even if you type a number
text = input("Enter a number: ")
print(f"You typed: {text} (type: {type(text).__name__})")

# int() converts to a whole number
number = int(text)
print(f"As integer: {number} (type: {type(number).__name__})")

# float() converts to a decimal number
decimal = float(text)
print(f"As float: {decimal} (type: {type(decimal).__name__})")

# str() converts anything to a string
age = 25
age_text = str(age)
print(f"As string: '{age_text}' (type: {type(age_text).__name__})")

# bool() converts to True/False
# 0, empty string, None, and empty lists are False
# Everything else is True
print(f"\nbool(1) = {bool(1)}")
print(f"bool(0) = {bool(0)}")
print(f'bool("hello") = {bool("hello")}')
print(f'bool("") = {bool("")}')
