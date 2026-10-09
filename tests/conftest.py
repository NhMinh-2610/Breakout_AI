import pytest

from breakout_ai.config import Settings
from breakout_ai.storage import Store


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "test.sqlite3", market_enabled=False)


@pytest.fixture
def store(settings):
    return Store(settings.database_path)
