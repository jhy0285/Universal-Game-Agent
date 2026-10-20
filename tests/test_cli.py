import json

from uga.cli import main


def test_doctor_and_schema_export(tmp_path, capsys):
    assert main(["doctor"]) == 0
    assert json.loads(capsys.readouterr().out)["version"] == "0.1.0"
    assert main(["schemas", "--output", str(tmp_path)]) == 0
    assert len(list(tmp_path.glob("*.schema.json"))) == 7
