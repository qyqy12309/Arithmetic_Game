"""Tkinter interface with immediate, no-Enter answer detection."""

import argparse
from datetime import datetime
import math
import time
import tkinter as tk
from tkinter import messagebox, ttk
import uuid

from .analysis import summarize_records
from .core import (
    OPERATIONS,
    generate_question,
    is_correction_edit,
    validate_operation_ranges,
    validate_operations,
    validate_positive_range,
)
from .storage import append_records, create_session_file


def timestamp_now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


class ArithmeticTrainerApp(tk.Tk):
    def __init__(self, history_directory="history"):
        super().__init__()
        self.title("Mental Arithmetic Trainer")
        self.resizable(False, False)
        self.history_directory = history_directory
        self.history_path = None

        self.active = False
        self.processing_answer = False
        self.score = 0
        self.records = []
        self.current_question = None
        self.question_started_monotonic = None
        self.question_started_at = ""
        self.deadline = 0.0
        self.session_id = ""
        self.previous_answer_text = ""
        self.correction_edits = 0
        self.timer_job = None

        self.range_vars = {
            "addition": {
                "first_minimum": tk.StringVar(value="2"),
                "first_maximum": tk.StringVar(value="100"),
                "second_minimum": tk.StringVar(value="2"),
                "second_maximum": tk.StringVar(value="100"),
            },
            "multiplication": {
                "first_minimum": tk.StringVar(value="2"),
                "first_maximum": tk.StringVar(value="12"),
                "second_minimum": tk.StringVar(value="2"),
                "second_maximum": tk.StringVar(value="100"),
            },
        }
        self.duration_var = tk.StringVar(value="120")
        self.operation_vars = {
            operation: tk.BooleanVar(value=True)
            for operation in OPERATIONS
        }
        self.question_var = tk.StringVar(value="Choose settings and start")
        self.answer_var = tk.StringVar()
        self.score_var = tk.StringVar(value="Score: 0")
        self.timer_var = tk.StringVar(value="Time: 120")
        self.status_var = tk.StringVar(value="")

        self._build_widgets()
        self.answer_var.trace_add("write", self._answer_changed)

    def _build_widgets(self):
        outer = ttk.Frame(self, padding=16)
        outer.grid()

        settings = ttk.LabelFrame(outer, text="Session settings", padding=10)
        settings.grid(row=0, column=0, sticky="ew")

        self.operation_buttons = []
        self.setting_entries = []

        addition_button = ttk.Checkbutton(
            settings, text="Addition", variable=self.operation_vars["addition"]
        )
        addition_button.grid(row=0, column=0, columnspan=8, sticky="w")
        self.operation_buttons.append(addition_button)
        self._add_range_row(settings, 1, "addition", "+")

        subtraction_button = ttk.Checkbutton(
            settings, text="Subtraction", variable=self.operation_vars["subtraction"]
        )
        subtraction_button.grid(row=2, column=0, columnspan=8, sticky="w", pady=(8, 0))
        self.operation_buttons.append(subtraction_button)
        ttk.Label(settings, text="Addition problems in reverse.").grid(
            row=3, column=1, columnspan=7, sticky="w"
        )

        multiplication_button = ttk.Checkbutton(
            settings, text="Multiplication", variable=self.operation_vars["multiplication"]
        )
        multiplication_button.grid(row=4, column=0, columnspan=8, sticky="w", pady=(8, 0))
        self.operation_buttons.append(multiplication_button)
        self._add_range_row(settings, 5, "multiplication", "×")

        division_button = ttk.Checkbutton(
            settings, text="Division", variable=self.operation_vars["division"]
        )
        division_button.grid(row=6, column=0, columnspan=8, sticky="w", pady=(8, 0))
        self.operation_buttons.append(division_button)
        ttk.Label(settings, text="Multiplication problems in reverse.").grid(
            row=7, column=1, columnspan=7, sticky="w"
        )

        ttk.Label(settings, text="Duration:").grid(row=8, column=0, sticky="w", pady=(12, 0))
        self.duration_entry = ttk.Entry(settings, textvariable=self.duration_var, width=6)
        self.duration_entry.grid(row=8, column=1, sticky="w", pady=(12, 0))
        ttk.Label(settings, text="seconds").grid(row=8, column=2, sticky="w", pady=(12, 0))
        self.setting_entries.append(self.duration_entry)

        self.start_button = ttk.Button(settings, text="Start session", command=self.start_session)
        self.start_button.grid(row=9, column=0, columnspan=8, sticky="ew", pady=(12, 0))

        info = ttk.Frame(outer, padding=(0, 14, 0, 8))
        info.grid(row=1, column=0, sticky="ew")
        ttk.Label(info, textvariable=self.score_var).grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.timer_var).grid(row=0, column=1, sticky="e")
        info.columnconfigure(1, weight=1)

        ttk.Label(outer, textvariable=self.question_var, font=("TkDefaultFont", 24)).grid(row=2, column=0, pady=10)
        self.answer_entry = ttk.Entry(outer, textvariable=self.answer_var, justify="center", font=("TkDefaultFont", 18), state="disabled")
        self.answer_entry.grid(row=3, column=0, sticky="ew", padx=40)
        ttk.Label(outer, textvariable=self.status_var, justify="center").grid(row=4, column=0, pady=(10, 0))

    def _add_range_row(self, parent, row, family, symbol):
        variables = self.range_vars[family]
        ttk.Label(parent, text="Range:").grid(row=row, column=0, sticky="w")
        labels = ("to", symbol, "to")
        variable_names = ("first_minimum", "first_maximum", "second_minimum", "second_maximum")
        for index, variable_name in enumerate(variable_names):
            entry = ttk.Entry(parent, textvariable=variables[variable_name], width=6)
            entry.grid(row=row, column=1 + index * 2, padx=(2, 2))
            self.setting_entries.append(entry)
            if index < len(labels):
                ttk.Label(parent, text=labels[index]).grid(row=row, column=2 + index * 2)

    def _selected_operations(self):
        return [name for name, variable in self.operation_vars.items() if variable.get()]

    def _read_configuration(self):
        operations = validate_operations(self._selected_operations())
        operation_ranges = {}
        try:
            duration = int(self.duration_var.get())
            for family, variables in self.range_vars.items():
                first_range = (
                    int(variables["first_minimum"].get()),
                    int(variables["first_maximum"].get()),
                )
                second_range = (
                    int(variables["second_minimum"].get()),
                    int(variables["second_maximum"].get()),
                )
                operation_ranges[family] = (first_range, second_range)
        except ValueError as error:
            raise ValueError("All range values and seconds must be whole numbers.") from error

        for family, (first_range, second_range) in operation_ranges.items():
            validate_positive_range(*first_range, f"{family.title()} first range")
            validate_positive_range(*second_range, f"{family.title()} second range")
        validate_operation_ranges(operations, operation_ranges)
        if duration <= 0:
            raise ValueError("Seconds must be greater than zero.")
        return operations, operation_ranges, duration

    def _set_settings_enabled(self, enabled):
        state = "normal" if enabled else "disabled"
        for widget in self.operation_buttons + self.setting_entries:
            widget.configure(state=state)

    def start_session(self):
        try:
            operations, operation_ranges, duration = self._read_configuration()
        except ValueError as error:
            messagebox.showerror("Invalid settings", str(error), parent=self)
            return

        try:
            history_path = create_session_file(self.history_directory)
        except OSError as error:
            messagebox.showerror("History error", str(error), parent=self)
            return

        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        self.operations = operations
        self.operation_ranges = operation_ranges
        self.duration = duration
        self.history_path = history_path
        self.session_id = uuid.uuid4().hex
        self.score = 0
        self.records = []
        self.current_question = None
        self.active = True
        self.deadline = time.monotonic() + duration
        self.score_var.set("Score: 0")
        self.status_var.set("")
        self.start_button.configure(state="disabled")
        self._set_settings_enabled(False)
        self.answer_entry.configure(state="normal")
        self._clear_answer()
        self._show_next_question()
        self.answer_entry.focus_set()
        self._update_timer()

    def _clear_answer(self):
        self.processing_answer = True
        self.answer_var.set("")
        self.previous_answer_text = ""
        self.processing_answer = False

    def _show_next_question(self):
        self.current_question = generate_question(
            self.operations, operation_ranges=self.operation_ranges
        )
        self.question_started_monotonic = time.monotonic()
        self.question_started_at = timestamp_now()
        self.correction_edits = 0
        self.previous_answer_text = ""
        self.question_var.set(f"{self.current_question['text']} = ?")

    def _answer_changed(self, *_trace_arguments):
        if self.processing_answer or not self.active or self.current_question is None:
            return
        if time.monotonic() >= self.deadline:
            self._finish_session()
            return

        current_text = self.answer_var.get()
        if is_correction_edit(self.previous_answer_text, current_text):
            self.correction_edits += 1
        self.previous_answer_text = current_text

        if current_text in {"", "-"}:
            return
        try:
            answer = int(current_text)
        except ValueError:
            return
        if answer != self.current_question["correct_answer"]:
            return

        self._record_solved_question()
        self._clear_answer()
        if time.monotonic() >= self.deadline:
            self._finish_session(record_expired=False)
        else:
            self._show_next_question()
            self.answer_entry.focus_set()

    def _base_record(self, response_seconds):
        question = self.current_question
        family = "addition" if question["operation"] in {"addition", "subtraction"} else "multiplication"
        first_range, second_range = self.operation_ranges[family]
        return {
            "session_id": self.session_id,
            "question_number": len(self.records) + 1,
            "interface_mode": "gui",
            "operation": question["operation"],
            "first_number": question["first_number"],
            "second_number": question["second_number"],
            "correct_answer": question["correct_answer"],
            "question_started_at": self.question_started_at,
            "question_ended_at": timestamp_now(),
            "response_seconds": round(response_seconds, 6),
            "wrong_submissions": "",
            "correction_edits": self.correction_edits,
            "score_after": self.score,
            "minimum": min(first_range[0], second_range[0]),
            "maximum": max(first_range[1], second_range[1]),
            "session_duration_seconds": self.duration,
        }

    def _save_record(self, record):
        self.records.append(record)
        append_records(self.history_path, [record])

    def _record_solved_question(self):
        elapsed = time.monotonic() - self.question_started_monotonic
        self.score += 1
        record = self._base_record(elapsed)
        record.update({
            "outcome": "solved",
            "eventually_correct": True,
            "clean_solve": self.correction_edits == 0,
            "score_after": self.score,
        })
        self._save_record(record)
        self.score_var.set(f"Score: {self.score}")
        self.current_question = None

    def _record_expired_question(self):
        if self.current_question is None:
            return
        elapsed = time.monotonic() - self.question_started_monotonic
        record = self._base_record(elapsed)
        record.update({
            "outcome": "expired",
            "eventually_correct": False,
            "clean_solve": False,
        })
        self._save_record(record)
        self.current_question = None

    def _update_timer(self):
        # A scheduled callback is no longer pending once it begins running.
        # Clearing the id avoids trying to cancel an already-fired Tk event.
        self.timer_job = None
        if not self.active:
            return
        remaining = max(0.0, self.deadline - time.monotonic())
        self.timer_var.set(f"Time: {math.ceil(remaining)}")
        if remaining <= 0:
            self._finish_session()
        else:
            self.timer_job = self.after(100, self._update_timer)

    def _finish_session(self, record_expired=True):
        if not self.active:
            return
        self.active = False
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        if record_expired:
            self._record_expired_question()
        self.answer_entry.configure(state="disabled")
        self._set_settings_enabled(True)
        self.start_button.configure(state="normal", text="Start new session")
        self.timer_var.set("Time: 0")
        self.question_var.set("Session complete")

        summary = summarize_records(self.records)
        self.status_var.set(
            f"Solved {summary['solved']} of {summary['presented']} presented  •  "
            f"Median {summary['median_response_seconds']:.2f}s  •  "
            f"Clean solves {summary['gui_clean_solve_rate']:.0%}"
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Tkinter mental arithmetic trainer.")
    parser.add_argument(
        "--history-directory",
        "--history",
        dest="history_directory",
        default="history",
        help="root directory for dated session CSV files (default: history)",
    )
    args = parser.parse_args(argv)
    app = ArithmeticTrainerApp(args.history_directory)
    app.mainloop()


if __name__ == "__main__":
    main()
