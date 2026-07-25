# Reading & Writing Files
# Python can create, write to, and read text files.

# === Writing a file ===
# "w" mode creates/overwrites the file
# "with" automatically closes the file when done
with open("example.txt", "w") as f:
    f.write("Hello, file!\n")
    f.write("This is line 2.\n")
    f.write("Python is fun!\n")

print("File written!")

# === Reading the whole file ===
with open("example.txt", "r") as f:
    content = f.read()
print("\n--- Full content ---")
print(content)

# === Reading line by line ===
print("--- Line by line ---")
with open("example.txt", "r") as f:
    for line_num, line in enumerate(f, 1):
        # .strip() removes the newline at the end
        print(f"Line {line_num}: {line.strip()}")

# === Appending to a file ===
# "a" mode adds to the end without erasing
with open("example.txt", "a") as f:
    f.write("This line was appended!\n")

# Read again to confirm
with open("example.txt", "r") as f:
    lines = f.readlines()  # Returns a list of lines
print(f"\nFile now has {len(lines)} lines.")
