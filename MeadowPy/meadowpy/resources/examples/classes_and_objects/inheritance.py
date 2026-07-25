# Inheritance
# A child class can inherit from a parent class,
# reusing its code and adding new features.

# Parent class
class Animal:
    def __init__(self, name, sound):
        self.name = name
        self.sound = sound

    def speak(self):
        print(f"{self.name} says {self.sound}!")

    def __str__(self):
        return self.name


# Child class — inherits from Animal
class Cat(Animal):
    def __init__(self, name, indoor=True):
        # super() calls the parent's __init__
        super().__init__(name, "Meow")
        self.indoor = indoor

    def purr(self):
        """Only cats can purr — this is a new method."""
        print(f"{self.name} purrs softly...")


class Dog(Animal):
    def __init__(self, name, breed):
        super().__init__(name, "Woof")
        self.breed = breed

    def fetch(self, item):
        print(f"{self.name} fetches the {item}!")


# Create animals
whiskers = Cat("Whiskers", indoor=True)
rex = Dog("Rex", "German Shepherd")

# Both can use the parent's speak() method
whiskers.speak()  # Whiskers says Meow!
rex.speak()       # Rex says Woof!

# Each has its own special methods
whiskers.purr()
rex.fetch("ball")

# isinstance() checks if an object is a certain type
print(f"\nIs whiskers a Cat? {isinstance(whiskers, Cat)}")
print(f"Is whiskers an Animal? {isinstance(whiskers, Animal)}")
print(f"Is rex a Cat? {isinstance(rex, Cat)}")
