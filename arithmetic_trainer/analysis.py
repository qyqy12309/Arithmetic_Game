"""Read question history and calculate useful, carefully named metrics."""

import argparse
from collections import defaultdict
import statistics

from .storage import read_records


def _as_bool(value):
    return str(value).strip().lower() in {"1", "true", "yes"}


def _as_int(record, key, default=0):
    try:
        return int(record.get(key, default))
    except (TypeError, ValueError):
        return default


def _as_float(record, key, default=0.0):
    try:
        return float(record.get(key, default))
    except (TypeError, ValueError):
        return default


def has_carrying(first_number, second_number):
    """Return whether adding two non-negative integers requires a carry."""
    if first_number < 0 or second_number < 0:
        return False
    while first_number or second_number:
        if first_number % 10 + second_number % 10 >= 10:
            return True
        first_number //= 10
        second_number //= 10
    return False


def has_borrowing(first_number, second_number):
    """Return whether non-negative first_number - second_number needs borrowing."""
    if first_number < second_number or second_number < 0:
        return False
    borrow = 0
    while first_number or second_number:
        top_digit = first_number % 10 - borrow
        bottom_digit = second_number % 10
        if top_digit < bottom_digit:
            return True
        borrow = 0
        first_number //= 10
        second_number //= 10
    return False


def range_bucket(first_number, second_number):
    largest = max(abs(first_number), abs(second_number))
    if largest <= 9:
        return "0–9"
    if largest <= 19:
        return "10–19"
    if largest <= 49:
        return "20–49"
    if largest <= 99:
        return "50–99"
    return "100+"


def summarize_records(records):
    records = list(records)
    solved = [record for record in records if record.get("outcome") == "solved"]
    response_times = [_as_float(record, "response_seconds") for record in solved]
    total_seconds = sum(response_times)

    terminal = [
        record
        for record in solved
        if record.get("interface_mode") == "terminal" and "wrong_submissions" in record
    ]
    wrong_submissions = sum(_as_int(record, "wrong_submissions") for record in terminal)
    terminal_attempts = len(terminal) + wrong_submissions
    terminal_accuracy = len(terminal) / terminal_attempts if terminal_attempts else 0.0

    gui = [record for record in solved if record.get("interface_mode") == "gui"]
    clean_gui = sum(_as_bool(record.get("clean_solve")) for record in gui)

    return {
        "presented": len(records),
        "solved": len(solved),
        "completion_rate": len(solved) / len(records) if records else 0.0,
        "median_response_seconds": statistics.median(response_times) if response_times else 0.0,
        "questions_per_minute": len(solved) * 60 / total_seconds if total_seconds else 0.0,
        "terminal_submission_accuracy": terminal_accuracy,
        "terminal_submission_accuracy_available": bool(terminal),
        "gui_clean_solve_rate": clean_gui / len(gui) if gui else 0.0,
        "gui_clean_solve_rate_available": bool(gui),
    }


def _add_group(groups, category, label, response_seconds):
    groups[(category, str(label))].append(response_seconds)


def weakness_groups(records, minimum_samples=3):
    """Return sufficiently sampled groups, slowest first by median response time."""
    groups = defaultdict(list)
    for record in records:
        if record.get("outcome") != "solved":
            continue
        operation = record.get("operation", "unknown")
        first = _as_int(record, "first_number")
        second = _as_int(record, "second_number")
        elapsed = _as_float(record, "response_seconds")

        _add_group(groups, "operation", operation, elapsed)
        _add_group(groups, "range", range_bucket(first, second), elapsed)
        _add_group(groups, "operand pair", f"{first}, {second}", elapsed)

        if operation == "multiplication":
            for factor in {first, second}:
                _add_group(groups, "multiplication factor", factor, elapsed)
        elif operation == "addition":
            _add_group(groups, "addition feature", "carrying" if has_carrying(first, second) else "no carrying", elapsed)
        elif operation == "subtraction":
            _add_group(groups, "subtraction feature", "borrowing" if has_borrowing(first, second) else "no borrowing", elapsed)

    results = []
    for (category, label), times in groups.items():
        if len(times) >= minimum_samples:
            results.append({
                "category": category,
                "label": label,
                "samples": len(times),
                "median_response_seconds": statistics.median(times),
            })
    return sorted(results, key=lambda item: item["median_response_seconds"], reverse=True)


def print_report(records, minimum_samples=3):
    summary = summarize_records(records)
    print("Performance summary")
    print(f"Presented: {summary['presented']}")
    print(f"Solved: {summary['solved']}")
    print(f"Completion rate: {summary['completion_rate']:.1%}")
    print(f"Questions per minute: {summary['questions_per_minute']:.1f}")
    print(f"Median response: {summary['median_response_seconds']:.2f}s")
    if summary["terminal_submission_accuracy_available"]:
        print(f"Terminal submission accuracy: {summary['terminal_submission_accuracy']:.1%}")
    else:
        print("Terminal submission accuracy: unavailable in this CSV schema")
    if summary["gui_clean_solve_rate_available"]:
        print(f"GUI clean-solve rate: {summary['gui_clean_solve_rate']:.1%}")
    else:
        print("GUI clean-solve rate: unavailable without interface mode")

    groups = weakness_groups(records, minimum_samples)
    print(f"\nSlowest sufficiently sampled groups (minimum {minimum_samples}):")
    if not groups:
        print("Not enough data yet.")
        return
    for group in groups[:10]:
        print(f"- {group['category']}: {group['label']} — "
              f"{group['median_response_seconds']:.2f}s median ({group['samples']} questions)")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Analyze arithmetic training history.")
    parser.add_argument(
        "history",
        nargs="?",
        default="history",
        help="session history directory or a specific CSV file (default: history)",
    )
    parser.add_argument("--minimum-samples", type=int, default=3)
    args = parser.parse_args(argv)
    if args.minimum_samples <= 0:
        raise SystemExit("--minimum-samples must be greater than zero")
    print_report(read_records(args.history), args.minimum_samples)


if __name__ == "__main__":
    main()
