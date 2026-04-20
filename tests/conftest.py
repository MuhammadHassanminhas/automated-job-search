import pytest

# NOTE: app.* imports are intentionally in test files, not here.
# conftest must remain importable so pytest can collect all tests.
# Fixtures referencing app.* are defined below — tests using them
# will fail with ModuleNotFoundError pointing at app/, which is the
# expected red state before implementation.


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"
