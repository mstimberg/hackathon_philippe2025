import pytest
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment for all tests."""
    # Suppress print statements during tests for cleaner output
    import builtins
    original_print = builtins.print
    
    def quiet_print(*args, **kwargs):
        # Only print if explicitly requested with verbose flag
        if '--verbose' in sys.argv or '-v' in sys.argv:
            original_print(*args, **kwargs)
    
    builtins.print = quiet_print
    
    yield
    
    # Restore original print function after tests
    builtins.print = original_print


# Configuration for pytest
pytest_plugins = []

def pytest_configure(config):
    """Configure pytest with custom settings."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    ) 