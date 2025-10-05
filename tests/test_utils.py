from claudesync import utils
from claudesync.project_instructions import ProjectInstructions


class DummyConfig:
    def get(self, key, default=None):
        return default


def test_get_local_files_excludes_project_instructions(tmp_path):
    instructions_path = tmp_path / ProjectInstructions.INSTRUCTIONS_FILE
    instructions_path.write_text("# instructions", encoding="utf-8")

    other_file = tmp_path / "notes.txt"
    other_file.write_text("content", encoding="utf-8")

    files = utils.get_local_files(DummyConfig(), str(tmp_path))

    assert ProjectInstructions.INSTRUCTIONS_FILE not in files
    assert "notes.txt" in files
