
import sys
import os
import random

# Add project root to path
sys.path.append(os.getcwd())

from src.texts.easter_eggs import EASTER_EGGS
from src.texts.phrases import check_easter_egg

print("Checking EASTER_EGGS structure...")
found_issue = False
for key, value in EASTER_EGGS.items():
    if not isinstance(value, list):
        print(f"Error: Key '{key}' has value of type {type(value)}")
        found_issue = True
    else:
        for i, item in enumerate(value):
            if not isinstance(item, str):
                print(f"Error: Key '{key}' item {i} is not a string! Type: {type(item)}, Value: {item}")
                found_issue = True

if not found_issue:
    print("EASTER_EGGS structure seems correct.")

print("\nTesting check_easter_egg with 'Привет'...")
response = check_easter_egg("Привет")
print(f"Response type: {type(response)}")
print(f"Response value: {response}")

if isinstance(response, list):
    print("CRITICAL: Response is a list!")
