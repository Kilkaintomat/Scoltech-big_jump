import importlib.util
from pathlib import Path
import pytest
spec = importlib.util.spec_from_file_location("guard", Path(__file__).with_name("resource_guard.py"))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

@pytest.mark.parametrize("used,maximum,cpus,expected", [
    (60000,262144,32,2),
    (120000,262144,32,1),
    (200000,262144,32,0),
    (60000,262144,8,1),
    (0,1000000,32,2),
    (0,112767,32,0),
    (0,112768,32,1),
])
def test_capacity_and_cpu_bound(used,maximum,cpus,expected):
    assert guard.choose_workers(used,maximum,cpus)==expected

@pytest.mark.parametrize("values", [(-1,100,8),(101,100,8),(0,0,8),(0,100,0)])
def test_invalid_capacity(values):
    with pytest.raises(ValueError):
        guard.choose_workers(*values)
