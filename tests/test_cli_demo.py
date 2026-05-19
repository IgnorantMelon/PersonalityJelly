from pathlib import Path

from personality_jelly.cli.main import main


def test_cli_demo_runs_end_to_end(tmp_path: Path, capsys) -> None:
    source_file = tmp_path / "sample.md"
    source_file.write_text("# 第一章\n\n林霜总是先观察，再行动。", encoding="utf-8")

    exit_code = main(
        [
            "demo",
            str(source_file),
            "--character",
            "林霜",
            "--user-message",
            "请记住，我喜欢在夜里写作。",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "source_work_id=sw_" in output
    assert "character_id=char_" in output
    assert "assistant=我记住了" in output
    assert "critic_action=accept" in output
    assert "memory_count=1" in output

