from pathlib import Path
import tempfile

import pytest


@pytest.fixture
def tmp_path():
    """Keep test artifacts inside the writable project, including Windows sandboxes."""
    work = Path(__file__).resolve().parents[1] / "work"
    work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="test-", dir=work) as directory:
        yield Path(directory)
