"""Command-line entry point: argument parsing and output formatting only."""

import argparse
import os
import sys
from collections.abc import Callable, Sequence
from typing import TextIO

from task_tracker.errors import TaskTrackerError
from task_tracker.models import Priority, Status, Task
from task_tracker.service import TaskService
from task_tracker.storage import DEFAULT_FILENAME, JsonTaskRepository

ENV_DATA_DIR = "TASK_TRACKER_DATA_DIR"
DEFAULT_DATA_DIR = "data"

Handler = Callable[[argparse.Namespace, TaskService, TextIO], int]

_PRIORITIES = [p.value for p in Priority]
_STATUSES = [s.value for s in Status]


def format_task_line(task: Task) -> str:
    due = task.due_date.isoformat() if task.due_date else "-"
    return (
        f"{task.id:>4}  {task.status.value:<11}  {task.priority.value:<8}  {due:<10}  {task.title}"
    )


def _format_header() -> str:
    return f"{'ID':>4}  {'STATUS':<11}  {'PRIORITY':<8}  {'DUE':<10}  TITLE"


def _cmd_add(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    task = service.create_task(
        args.title, description=args.description, priority=args.priority, due_date=args.due
    )
    print(f"Created task {task.id}: {task.title}", file=out)
    return 0


def _cmd_list(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    tasks = service.list_tasks(status=args.status, priority=args.priority)
    if not tasks:
        print("No tasks found.", file=out)
        return 0
    print(_format_header(), file=out)
    for task in tasks:
        print(format_task_line(task), file=out)
    return 0


def _cmd_show(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    task = service.get_task(args.id)
    completed = task.completed_at.isoformat() if task.completed_at else "-"
    print(f"Task {task.id}", file=out)
    print(f"  Title:     {task.title}", file=out)
    print(f"  Status:    {task.status.value}", file=out)
    print(f"  Priority:  {task.priority.value}", file=out)
    print(f"  Due:       {task.due_date.isoformat() if task.due_date else '-'}", file=out)
    print(f"  Created:   {task.created_at.isoformat()}", file=out)
    print(f"  Completed: {completed}", file=out)
    if task.description:
        print("  Description:", file=out)
        for line in task.description.splitlines():
            print(f"    {line}", file=out)
    return 0


def _cmd_done(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    task = service.complete_task(args.id)
    print(f"Completed task {task.id}: {task.title}", file=out)
    return 0


def _cmd_status(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    task = service.set_status(args.id, args.status)
    print(f"Task {task.id} is now {task.status.value}", file=out)
    return 0


def _cmd_delete(args: argparse.Namespace, service: TaskService, out: TextIO) -> int:
    task = service.delete_task(args.id)
    print(f"Deleted task {task.id}: {task.title}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task-tracker", description="A small task tracker backed by a local JSON file."
    )
    parser.add_argument(
        "--data-dir",
        default=os.environ.get(ENV_DATA_DIR, DEFAULT_DATA_DIR),
        help=f"directory for the data file (env: {ENV_DATA_DIR}; default: ./{DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--file",
        default=DEFAULT_FILENAME,
        help=f"plain *.json file name inside the data directory (default: {DEFAULT_FILENAME})",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create a task")
    add.add_argument("title")
    add.add_argument("-d", "--description", default="")
    add.add_argument("-p", "--priority", choices=_PRIORITIES, default=Priority.MEDIUM.value)
    add.add_argument("--due", metavar="YYYY-MM-DD", default=None, help="optional due date")
    add.set_defaults(handler=_cmd_add)

    list_ = sub.add_parser("list", help="list tasks, optionally filtered")
    list_.add_argument("--status", choices=_STATUSES, default=None)
    list_.add_argument("--priority", choices=_PRIORITIES, default=None)
    list_.set_defaults(handler=_cmd_list)

    show = sub.add_parser("show", help="show every field of one task")
    show.add_argument("id", type=int)
    show.set_defaults(handler=_cmd_show)

    done = sub.add_parser("done", help="mark a task as completed")
    done.add_argument("id", type=int)
    done.set_defaults(handler=_cmd_done)

    status = sub.add_parser("status", help="set a task's status")
    status.add_argument("id", type=int)
    status.add_argument("status", choices=_STATUSES)
    status.set_defaults(handler=_cmd_status)

    delete = sub.add_parser("delete", help="delete a task")
    delete.add_argument("id", type=int)
    delete.set_defaults(handler=_cmd_delete)

    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the CLI. Returns 0 on success, 1 on a handled error (argparse exits 2)."""
    out = stdout if stdout is not None else sys.stdout
    err = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    handler: Handler = args.handler
    try:
        repository = JsonTaskRepository(args.data_dir, args.file)
        return handler(args, TaskService(repository), out)
    except TaskTrackerError as exc:
        print(f"error: {exc}", file=err)
        return 1
