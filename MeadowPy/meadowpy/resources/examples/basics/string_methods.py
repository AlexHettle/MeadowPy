# String Methods
# Strings have many built-in methods for common tasks.

message = "  Hello, World!  "

# Removing whitespace from the edges
print(message.strip())       # "Hello, World!"
print(message.lstrip())      # "Hello, World!  "
print(message.rstrip())      # "  Hello, World!"

# Changing case
greeting = "hello world"
print(greeting.upper())      # "HELLO WORLD"
print(greeting.title())      # "Hello World"
print(greeting.capitalize()) # "Hello world"

# Searching and replacing
sentence = "The cat sat on the mat"
print(sentence.replace("cat", "dog"))  # "The dog sat on the mat"
print(sentence.count("the"))           # 1 (case-sensitive!)
print(sentence.find("sat"))            # 8 (index where "sat" starts)

# Splitting a string into a list
csv_line = "Alice,25,Engineer"
parts = csv_line.split(",")
print(parts)  # ['Alice', '25', 'Engineer']

# Joining a list back into a string
words = ["Python", "is", "fun"]
print(" ".join(words))   # "Python is fun"
print("-".join(words))   # "Python-is-fun"

# Checking what a string contains
filename = "report_2024.pdf"
print(filename.startswith("report"))  # True
print(filename.endswith(".pdf"))       # True
print("2024" in filename)              # True
print(filename.isdigit())              # False
