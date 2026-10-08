"""Countdown-based terminal interface for the arithmetic trainer."""

import argparse
from datetime import datetime
from pathlib import Path
import time
import uuid

from .analysis import summarize_records
from .core import generate_question, validate_operations, validate_range
from .storage import append_records, create_session_file


def timestamp_now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def parse_operations(value):
    operations = [part.strip() for part in value.split(",") if part.strip()]
    if not operations:
        raise argparse.ArgumentTypeError("provide at least one comma-separated operation")
    return operations


def make_record(question, *, session_id, question_number, started_at,
                response_seconds, wrong_submissions, score, minimum, maximum,
                duration):
    return {
        "session_id": session_id,
        "question_number": question_number,
        "interface_mode": "terminal",
        "operation": question["operation"],
        "first_number": question["first_number"],
        "second_number": question["second_number"],
        "correct_answer": question["correct_answer"],
        "question_started_at": started_at,
        "question_ended_at": timestamp_now(),
        "response_seconds": round(response_seconds, 6),
        "outcome": "solved",
        "eventually_correct": True,
        "wrong_submissions": wrong_submissions,
        "correction_edits": "",
        "clean_solve": wrong_submissions == 0,
        "score_after": score,
        "minimum": minimum,
        "maximum": maximum,
        "session_duration_seconds": duration,
    }


def run_session(operations, minimum, maximum, duration, history_directory):
    validate_range(minimum, maximum)
    operations = validate_operations(operations, minimum, maximum)
    if duration <= 0:
        raise ValueError("Duration must be greater than zero.")

    session_id = uuid.uuid4().hex
    history_path = create_session_file(history_directory)
    deadline = time.monotonic() + duration
    score = 0
    records = []

    print(f"\nYou have {duration} seconds. Press Ctrl+C to stop.\n")
    try:
        while time.monotonic() < deadline:
            question = generate_question(operations, minimum, maximum)
            question_number = len(records) + 1
            started_at = timestamp_now()
            started_monotonic = time.monotonic()
            wrong_submissions = 0

            while True:
                typed = input(f"{question['text']} = ")
                try:
                    answer = int(typed)
                except ValueError:
                    wrong_submissions += 1
                    print("Please enter a whole number.")
                    continue

                if answer == question["correct_answer"]:
                    break
                wrong_submissions += 1
                print("Not yet—edit your answer and try again.")

            score += 1
            elapsed = time.monotonic() - started_monotonic
            record = make_record(
                question,
                session_id=session_id,
                question_number=question_number,
                started_at=started_at,
                response_seconds=elapsed,
                wrong_submissions=wrong_submissions,
                score=score,
                minimum=minimum,
                maximum=maximum,
                duration=duration,
            )
            records.append(record)
            append_records(history_path, [record])
            print(f"Correct — score: {score}\n")
    except (KeyboardInterrupt, EOFError):
        print("\nSession stopped.")

    summary = summarize_records(records)
    print("\nSession summary")
    print(f"Score: {score}")
    print(f"Median response time: {summary['median_response_seconds']:.2f}s")
    print(f"Terminal submission accuracy: {summary['terminal_submission_accuracy']:.1%}")
    print(f"History: {Path(history_path).resolve()}")
    return records


def build_parser():
    parser = argparse.ArgumentParser(description="Practise mental arithmetic in the terminal.")
    parser.add_argument("--operations", type=parse_operations, default=["multiplication"],
                        help="comma-separated operations, e.g. +,-,x,/ (default: x)")
    parser.add_argument("--minimum", type=int, default=1)
    parser.add_argument("--maximum", type=int, default=12)
    parser.add_argument("--duration", type=int, default=60, help="session length in seconds")
    parser.add_argument(
        "--history-directory",
        "--history",
        dest="history_directory",
        default="history",
        help="root directory for dated session CSV files (default: history)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        run_session(
            args.operations,
            args.minimum,
            args.maximum,
            args.duration,
            args.history_directory,
        )
    except ValueError as error:
        raise SystemExit(f"Configuration error: {error}") from error


if __name__ == "__main__":
    main()
