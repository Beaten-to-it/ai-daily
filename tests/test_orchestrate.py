import pytest
from nbs import orchestrate, config

def test_lock_is_exclusive(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(orchestrate, "ROOT", tmp_path)
    with orchestrate._lock():
        with pytest.raises(orchestrate.Busy):
            with orchestrate._lock():
                pass
    # released after the outer block — re-acquirable
    with orchestrate._lock():
        pass
