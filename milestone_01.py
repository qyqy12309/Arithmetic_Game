"""Milestone 1: one multiplication question, intentionally kept tiny."""

import random


first_number = random.randint(1, 12)
second_number = random.randint(1, 12)
correct_answer = first_number * second_number

typed_answer = input(f"{first_number} × {second_number} = ")
answer = int(typed_answer)

if answer == correct_answer:
    print("Correct!")
else:
    print(f"Not quite. The answer is {correct_answer}.")
