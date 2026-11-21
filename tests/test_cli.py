import subprocess
import sys
from pathlib import Path

import pytest

from task_tracker.cli import main

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run(data_dir: Path, *args: str) -> int:
    return main(["--data-dir", str(data_dir), *args])


def test_add_then_list_shows_the_task(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, "add", "Write docs", "-p", "high", "--due", "2026-12-01") == 0
    assert "Created task 1: Write docs" in capsys.readouterr().out

    assert run(tmp_path, "list") == 0
    out = capsys.readouterr().out
    assert "Write docs" in out
    assert "high" in out
    assert "2026-12-01" in out
    assert "todo" in out


def test_list_on_empty_store_prints_friendly_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, "list") == 0
    assert "No tasks found." in capsys.readouterr().out


def test_list_filters_by_status_and_priority(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, "add", "alpha", "-p", "low")
    run(tmp_path, "add", "bravo", "-p", "high")
    run(tmp_path, "add", "charlie", "-p", "high")
    run(tmp_path, "done", "3")
    capsys.readouterr()

    run(tmp_path, "list", "--priority", "high")
    out = capsys.readouterr().out
    assert "bravo" in out and "charlie" in out and "alpha" not in out

    run(tmp_path, "list", "--status", "done")
    out = capsys.readouterr().out
    assert "charlie" in out and "bravo" not in out

    run(tmp_path, "list", "--status", "todo", "--priority", "high")
    out = capsys.readouterr().out
    assert "bravo" in out and "charlie" not in out and "alpha" not in out


def test_done_and_status_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(tmp_path, "add", "ship it")
    capsys.readouterr()

    assert run(tmp_path, "status", "1", "in_progress") == 0
    assert "Task 1 is now in_progress" in capsys.readouterr().out

    assert run(tmp_path, "done", "1") == 0
    assert "Completed task 1: ship it" in capsys.readouterr().out

    run(tmp_path, "show", "1")
    out = capsys.readouterr().out
    assert "Status:    done" in out
    assert "Completed: -" not in out


def test_show_prints_description(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(tmp_path, "add", "detailed", "-d", "line one\nline two")
    capsys.readouterr()
    assert run(tmp_path, "show", "1") == 0
    out = capsys.readouterr().out
    assert "detailed" in out
    assert "    line one" in out
    assert "    line two" in out


def test_delete_command(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run(tmp_path, "add", "temporary")
    capsys.readouterr()
    assert run(tmp_path, "delete", "1") == 0
    assert "Deleted task 1: temporary" in capsys.readouterr().out
    run(tmp_path, "list")
    assert "No tasks found." in capsys.readouterr().out


def test_unknown_id_returns_error_code_and_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for command in (["done", "42"], ["delete", "42"], ["show", "42"], ["status", "42", "todo"]):
        assert run(tmp_path, *command) == 1
        assert "error: Task 42 not found" in capsys.readouterr().err


def test_invalid_due_date_is_reported_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, "add", "bad date", "--due", "2026-13-45") == 1
    assert "error:" in capsys.readouterr().err
    assert not (tmp_path / "tasks.json").exists()


def test_empty_title_is_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run(tmp_path, "add", "   ") == 1
    assert "Title must not be empty" in capsys.readouterr().err


@pytest.mark.parametrize(
    "args",
    [
        ["add", "x", "-p", "urgent"],
        ["list", "--status", "finished"],
        ["done", "abc"],
        ["status", "1", "finished"],
        [],
    ],
)
def test_argparse_rejects_invalid_arguments_with_exit_code_2(
    tmp_path: Path, args: list[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        run(tmp_path, *args)
    assert excinfo.value.code == 2


def test_malformed_data_file_is_reported_and_never_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "tasks.json"
    path.write_text("{broken", encoding="utf-8")
    assert run(tmp_path, "list") == 1
    assert "not valid JSON" in capsys.readouterr().err
    assert run(tmp_path, "add", "should fail") == 1
    capsys.readouterr()
    assert path.read_text(encoding="utf-8") == "{broken"


def test_empty_data_file_is_treated_as_empty_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "tasks.json").write_text("", encoding="utf-8")
    assert run(tmp_path, "add", "first") == 0
    assert "Created task 1: first" in capsys.readouterr().out


def test_file_option_cannot_escape_data_directory(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data_dir = tmp_path / "data"
    assert run(data_dir, "--file", "../evil.json", "list") == 1
    assert "Invalid data file name" in capsys.readouterr().err
    assert run(data_dir, "--file", "../evil.json", "add", "x") == 1
    capsys.readouterr()
    assert not (tmp_path / "evil.json").exists()


def test_file_option_selects_a_separate_store(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, "--file", "work.json", "add", "work task")
    capsys.readouterr()
    run(tmp_path, "list")
    assert "No tasks found." in capsys.readouterr().out
    run(tmp_path, "--file", "work.json", "list")
    assert "work task" in capsys.readouterr().out


def test_state_persists_across_separate_invocations(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, "add", "one")
    run(tmp_path, "add", "two")
    run(tmp_path, "done", "1")
    run(tmp_path, "delete", "2")
    run(tmp_path, "add", "three")
    capsys.readouterr()
    run(tmp_path, "list")
    out = capsys.readouterr().out
    assert "one" in out and "three" in out and "two" not in out
    assert "   3  " in out  # id 2 was not reused


def test_module_entry_point_runs_as_a_subprocess(tmp_path: Path) -> None:
    base = [sys.executable, "-m", "task_tracker", "--data-dir", str(tmp_path)]
    added = subprocess.run(
        [*base, "add", "From subprocess"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert added.returncode == 0, added.stderr
    listed = subprocess.run(
        [*base, "list"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    assert listed.returncode == 0
    assert "From subprocess" in listed.stdout
    missing = subprocess.run(
        [*base, "done", "99"], cwd=PROJECT_ROOT, capture_output=True, text=True, check=False
    )
    assert missing.returncode == 1
    assert "not found" in missing.stderr
