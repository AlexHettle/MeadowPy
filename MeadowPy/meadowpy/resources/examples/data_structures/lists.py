# Lists
# A list holds multiple items in order.
# Lists use square brackets: []

# Create a list
colors = ["red", "green", "blue"]
print("Original:", colors)

# Access items by index (starts at 0)
print(f"First: {colors[0]}")   # red
print(f"Last: {colors[-1]}")    # blue (-1 = last item)

# Add items
colors.append("yellow")          # Add to end
colors.insert(1, "orange")        # Insert at position 1
print(f"After adding: {colors}")

# Remove items
colors.remove("green")            # Remove by value
popped = colors.pop()             # Remove and return last item
print(f"Popped: {popped}")
print(f"After removing: {colors}")

# Slicing — get a sub-list
numbers = [0, 1, 2, 3, 4, 5]
print(f"\nnumbers[1:4] = {numbers[1:4]}")  # [1, 2, 3]
print(f"numbers[:3] = {numbers[:3]}")      # [0, 1, 2]
print(f"numbers[3:] = {numbers[3:]}")      # [3, 4, 5]

# Useful list functions
nums = [3, 1, 4, 1, 5, 9, 2]
print(f"\nLength: {len(nums)}")
print(f"Sorted: {sorted(nums)}")
print(f"Sum: {sum(nums)}")
print(f"Min: {min(nums)}, Max: {max(nums)}")
