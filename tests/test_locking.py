import pytest

from nbs import locking


def test_exclusive_lock_rejects_second_holder_and_releases(tmp_path):
    path = tmp_path / "run.lock"

    with locking.exclusive_lock(path):
        with pytest.raises(locking.BusyLock):
            with locking.exclusive_lock(path):
                pass

    with locking.exclusive_lock(path):
        pass
