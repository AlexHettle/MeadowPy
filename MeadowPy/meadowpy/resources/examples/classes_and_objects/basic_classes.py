# Basic Classes
# A class is a blueprint for creating objects.
# Objects bundle data (attributes) and actions (methods).

class Dog:
    # __init__ runs when you create a new Dog
    # "self" refers to the specific dog being created
    def __init__(self, name, breed):
        self.name = name      # Store the name
        self.breed = breed    # Store the breed
        self.tricks = []      # Start with no tricks

    def learn_trick(self, trick):
        """Teach the dog a new trick."""
        self.tricks.append(trick)
        print(f"{self.name} learned {trick}!")

    def show_tricks(self):
        """Display all tricks the dog knows."""
        if self.tricks:
            tricks_str = ", ".join(self.tricks)
            print(f"{self.name} knows: {tricks_str}")
        else:
            print(f"{self.name} doesn't know any tricks yet.")

    def __str__(self):
        """This controls what print() shows."""
        return f"{self.name} the {self.breed}"


# Create Dog objects
buddy = Dog("Buddy", "Golden Retriever")
max_dog = Dog("Max", "Beagle")

print(buddy)  # Uses __str__
print(max_dog)

# Teach some tricks
buddy.learn_trick("sit")
buddy.learn_trick("shake")
max_dog.learn_trick("roll over")

print()
buddy.show_tricks()
max_dog.show_tricks()
