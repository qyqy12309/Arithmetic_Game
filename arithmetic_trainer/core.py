"""Pure arithmetic and question-generation logic shared by both interfaces."""

import random


OPERATIONS = ("addition", "subtraction", "multiplication", "division")
SYMBOLS = {
    "addition": "+",
    "subtraction": "−",
    "multiplication": "×",
    "division": "÷",
}

OPERATION_ALIASES = {
    "+": "addition",
    "add": "addition",
    "addition": "addition",
    "-": "subtraction",
    "subtract": "subtraction",
    "subtraction": "subtraction",
    "*": "multiplication",
    "x": "multiplication",
    "multiply": "multiplication",
    "multiplication": "multiplication",
    "/": "division",
    "divide": "division",
    "division": "division",
}


def normalize_operation(operation):
    """Return the full operation name for a supported name or symbol."""
    key = operation.strip().lower()
    try:
        return OPERATION_ALIASES[key]
    except KeyError as error:
        raise ValueError(f"Unsupported operation: {operation!r}") from error


def validate_range(minimum, maximum):
    if minimum > maximum:
        raise ValueError("The minimum cannot be greater than the maximum.")


def validate_positive_range(minimum, maximum, label="Range"):
    """Validate one inclusive range used by the GUI's operand settings."""
    if minimum <= 0 or maximum <= 0:
        raise ValueError(f"{label} values must be positive integers.")
    if minimum > maximum:
        raise ValueError(f"{label} minimum cannot be greater than its maximum.")


def validate_operations(operations, minimum=1, maximum=12):
    if not operations:
        raise ValueError("Choose at least one operation.")
    normalized = [normalize_operation(operation) for operation in operations]
    if "division" in normalized and minimum == 0 and maximum == 0:
        raise ValueError("Division needs at least one possible non-zero divisor.")
    return normalized


def calculate(operation, first_number, second_number):
    """Calculate an answer. Division is restricted to exact integer results."""
    operation = normalize_operation(operation)
    if operation == "addition":
        return first_number + second_number
    if operation == "subtraction":
        return first_number - second_number
    if operation == "multiplication":
        return first_number * second_number
    if second_number == 0:
        raise ValueError("Cannot divide by zero.")
    quotient, remainder = divmod(first_number, second_number)
    if remainder:
        raise ValueError("Division questions must have an integer answer.")
    return quotient


def _non_zero_random_integer(minimum, maximum, rng):
    if minimum == 0 and maximum == 0:
        raise ValueError("Division needs at least one possible non-zero divisor.")
    if minimum == 0:
        return rng.randint(1, maximum)
    if maximum == 0:
        return rng.randint(minimum, -1)

    value = rng.randint(minimum, maximum)
    if value == 0:
        return 1
    return value


def validate_operation_ranges(operations, operation_ranges):
    """Validate the two range families used by the GUI."""
    normalized = validate_operations(operations)
    required_families = set()
    if any(operation in {"addition", "subtraction"} for operation in normalized):
        required_families.add("addition")
    if any(operation in {"multiplication", "division"} for operation in normalized):
        required_families.add("multiplication")

    for family in required_families:
        try:
            first_range, second_range = operation_ranges[family]
            first_minimum, first_maximum = first_range
            second_minimum, second_maximum = second_range
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"{family.title()} needs two operand ranges.") from error
        validate_positive_range(first_minimum, first_maximum, f"{family.title()} first range")
        validate_positive_range(second_minimum, second_maximum, f"{family.title()} second range")
    return normalized


def _generate_from_operation_ranges(operation, operation_ranges, rng):
    family = "addition" if operation in {"addition", "subtraction"} else "multiplication"
    first_range, second_range = operation_ranges[family]
    first_operand = rng.randint(*first_range)
    second_operand = rng.randint(*second_range)

    if operation == "addition":
        first_number = first_operand
        second_number = second_operand
        correct_answer = first_operand + second_operand
    elif operation == "subtraction":
        first_number = first_operand + second_operand
        if rng.choice((True, False)):
            second_number = first_operand
            correct_answer = second_operand
        else:
            second_number = second_operand
            correct_answer = first_operand
    elif operation == "multiplication":
        first_number = first_operand
        second_number = second_operand
        correct_answer = first_operand * second_operand
    else:
        first_number = first_operand * second_operand
        if rng.choice((True, False)):
            second_number = first_operand
            correct_answer = second_operand
        else:
            second_number = second_operand
            correct_answer = first_operand

    return first_number, second_number, correct_answer


def generate_question(
    operations=("multiplication",),
    minimum=1,
    maximum=12,
    rng=None,
    operation_ranges=None,
):
    """Generate a valid question and return it as a plain dictionary.

    ``minimum`` and ``maximum`` retain the original shared-range behavior used
    by the terminal. The GUI supplies ``operation_ranges`` to use two ranges
    for each related pair of operations.
    """
    rng = rng or random

    if operation_ranges is not None:
        normalized = validate_operation_ranges(operations, operation_ranges)
        operation = rng.choice(normalized)
        first_number, second_number, correct_answer = _generate_from_operation_ranges(
            operation, operation_ranges, rng
        )
        return {
            "operation": operation,
            "first_number": first_number,
            "second_number": second_number,
            "correct_answer": correct_answer,
            "text": f"{first_number} {SYMBOLS[operation]} {second_number}",
        }

    validate_range(minimum, maximum)
    normalized = validate_operations(operations, minimum, maximum)
    operation = rng.choice(normalized)

    if operation == "division":
        second_number = _non_zero_random_integer(minimum, maximum, rng)
        correct_answer = rng.randint(minimum, maximum)
        first_number = second_number * correct_answer
    else:
        first_number = rng.randint(minimum, maximum)
        second_number = rng.randint(minimum, maximum)
        if operation == "subtraction" and first_number < second_number:
            first_number, second_number = second_number, first_number
        correct_answer = calculate(operation, first_number, second_number)

    return {
        "operation": operation,
        "first_number": first_number,
        "second_number": second_number,
        "correct_answer": correct_answer,
        "text": f"{first_number} {SYMBOLS[operation]} {second_number}",
    }


def is_correction_edit(previous_text, current_text):
    """Say whether an Entry edit corrected existing text instead of appending."""
    if current_text == previous_text:
        return False
    return not (len(current_text) > len(previous_text) and current_text.startswith(previous_text))
