import sys

import pytest

from uga.core.errors import UGAError
from uga.integrations.process import run_tool


def test_owned_python_command_result_timeout_and_output_budget(tmp_path):
    result = run_tool([sys.executable, "-c", "print('uga-fixture')"], tmp_path, approved=True)
    assert result.returncode == 0 and result.output.strip() == "uga-fixture"
    with pytest.raises(TimeoutError):
        run_tool(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            tmp_path,
            approved=True,
            timeout_s=0.02,
        )
    with pytest.raises(UGAError):
        run_tool([sys.executable, "-c", "raise SystemExit(7)"], tmp_path, approved=True)
    with pytest.raises(UGAError, match="output limit"):
        run_tool(
            [sys.executable, "-c", "print('x'*5000)"], tmp_path, approved=True, max_output_bytes=100
        )
    with pytest.raises(UGAError, match="memory limit"):
        run_tool(
            [sys.executable, "-c", "import time; data=bytearray(2000000); time.sleep(1)"],
            tmp_path,
            approved=True,
            max_rss_mb=1,
        )
