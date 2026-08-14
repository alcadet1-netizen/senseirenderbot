import sys
import os
import unittest

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.texts.phrases import check_easter_egg

class TestEasterEggRegex(unittest.TestCase):
    def test_word_boundary(self):
        # "gg" is a key
        self.assertIsNotNone(check_easter_egg("gg"), "Should match 'gg'")
        self.assertIsNotNone(check_easter_egg("gg wp"), "Should match 'gg' in 'gg wp'")
        self.assertIsNone(check_easter_egg("egg"), "Should NOT match 'gg' in 'egg'")
        self.assertIsNone(check_easter_egg("dagger"), "Should NOT match 'gg' in 'dagger'")

    def test_phrase_boundary(self):
        # "rush b" is a key
        self.assertIsNotNone(check_easter_egg("rush b"), "Should match 'rush b'")
        self.assertIsNotNone(check_easter_egg("go rush b now"), "Should match 'rush b' in sentence")
        self.assertIsNone(check_easter_egg("brush b"), "Should NOT match 'rush b' in 'brush b'")
        self.assertIsNone(check_easter_egg("rush back"), "Should NOT match 'rush b' in 'rush back'")

    def test_numbers(self):
        # "69" is a key
        self.assertIsNotNone(check_easter_egg("69"), "Should match '69'")
        self.assertIsNotNone(check_easter_egg("number 69"), "Should match '69' in sentence")
        self.assertIsNone(check_easter_egg("169"), "Should NOT match '69' in '169'")
        self.assertIsNone(check_easter_egg("690"), "Should NOT match '69' in '690'")

if __name__ == '__main__':
    unittest.main()
