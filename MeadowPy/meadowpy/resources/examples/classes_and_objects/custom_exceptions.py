# Custom Exceptions
# You can create your own exception types for clearer error handling.

# === Define a custom exception by inheriting from Exception ===
class InsufficientFundsError(Exception):
    """Raised when a withdrawal exceeds the balance."""
    def __init__(self, balance, amount):
        self.balance = balance
        self.amount = amount
        super().__init__(
            f"Cannot withdraw ${amount:.2f} — "
            f"only ${balance:.2f} available"
        )

class InvalidAgeError(ValueError):
    """Raised when an age value is not valid."""
    pass

# === Using custom exceptions ===
class BankAccount:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def withdraw(self, amount):
        if amount > self.balance:
            raise InsufficientFundsError(self.balance, amount)
        self.balance -= amount
        return self.balance

# === Catching custom exceptions ===
account = BankAccount("Alice", 100)

try:
    account.withdraw(50)
    print(f"Withdrew $50. Balance: ${account.balance:.2f}")
    account.withdraw(200)  # This will fail
except InsufficientFundsError as e:
    print(f"Error: {e}")
    print(f"  Tried: ${e.amount:.2f}, Have: ${e.balance:.2f}")

# === Raising with a simple message ===
def set_age(age):
    if age < 0 or age > 150:
        raise InvalidAgeError(f"{age} is not a valid age")
    return age

try:
    set_age(200)
except InvalidAgeError as e:
    print(f"\nInvalid age: {e}")
