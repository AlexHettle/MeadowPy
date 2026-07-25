# If / Elif / Else
# Use "if" to run code only when a condition is true.

age = int(input("Enter your age: "))

# "if" checks the first condition
# "elif" (else if) checks another condition if the first was false
# "else" runs if nothing above was true
if age < 0:
    print("That's not a valid age!")
elif age < 13:
    print("You're a child.")
elif age < 18:
    print("You're a teenager.")
elif age < 65:
    print("You're an adult.")
else:
    print("You're a senior.")

# Comparison operators:
#   ==  equal to          !=  not equal to
#   <   less than          >   greater than
#   <=  less or equal      >=  greater or equal

# You can combine conditions with "and", "or", "not"
has_ticket = True
if age >= 13 and has_ticket:
    print("\nYou can enter the movie!")
elif not has_ticket:
    print("\nYou need a ticket first.")
else:
    print("\nSorry, you're too young for this movie.")
