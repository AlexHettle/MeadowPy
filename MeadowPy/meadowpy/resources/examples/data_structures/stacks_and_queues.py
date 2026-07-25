# Stacks & Queues
# Two common patterns for processing data in order.

# === STACK (Last In, First Out) ===
# Think of a stack of plates — you add and remove from the top.
print("=== Stack (LIFO) ===")
stack = []

# Push items onto the stack
for item in ["A", "B", "C", "D"]:
    stack.append(item)
    print(f"  Push {item} -> {stack}")

# Pop items off the stack (reverse order!)
print("\nPopping:")
while stack:
    item = stack.pop()  # Removes and returns the LAST item
    print(f"  Pop {item} -> {stack}")

# === QUEUE (First In, First Out) ===
# Think of a line at a store — first person in line is served first.
from collections import deque  # Efficient for queues

print("\n=== Queue (FIFO) ===")
queue = deque()

# Enqueue — add to the back
for person in ["Alice", "Bob", "Charlie"]:
    queue.append(person)
    print(f"  Join: {person} -> {list(queue)}")

# Dequeue — remove from the front
print("\nServing:")
while queue:
    person = queue.popleft()  # Removes the FIRST item
    print(f"  Serve: {person} -> {list(queue)}")
