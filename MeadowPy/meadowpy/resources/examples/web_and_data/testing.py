# Testing
# Tests help you catch bugs and verify your code works.

# === The function we want to test ===
def calculate_average(numbers):
    """Calculate the average of a list of numbers."""
    if not numbers:
        raise ValueError("Cannot average an empty list")
    return sum(numbers) / len(numbers)


def is_palindrome(text):
    """Check if text reads the same forwards and backwards."""
    cleaned = text.lower().replace(" ", "")
    return cleaned == cleaned[::-1]

# === Using assert — the simplest test ===
# assert checks that something is True; crashes if False
assert calculate_average([10, 20, 30]) == 20.0
assert calculate_average([5]) == 5.0
assert is_palindrome("racecar") == True
assert is_palindrome("hello") == False
assert is_palindrome("A man a plan a canal Panama") == True
print("All assert tests passed!")

# === Using unittest — the standard library approach ===
import unittest


class TestAverage(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(calculate_average([10, 20, 30]), 20.0)

    def test_single_value(self):
        self.assertEqual(calculate_average([42]), 42.0)

    def test_floats(self):
        result = calculate_average([1.5, 2.5])
        self.assertAlmostEqual(result, 2.0)

    def test_empty_list_raises_error(self):
        with self.assertRaises(ValueError):
            calculate_average([])


class TestPalindrome(unittest.TestCase):
    def test_palindrome(self):
        self.assertTrue(is_palindrome("racecar"))

    def test_not_palindrome(self):
        self.assertFalse(is_palindrome("hello"))

# Run the tests
# verbosity=2 shows each test name and result
unittest.main(argv=[""], exit=False, verbosity=2)
