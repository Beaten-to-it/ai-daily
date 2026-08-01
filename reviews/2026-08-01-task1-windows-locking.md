# Task 1 Windows Locking Adversarial Review

## Artifact

- Base commit: `2ee3dc417cebc30db84fedf5d1affb4af2a3c661`
- Branch: `codex/windows-rebuild`
- Review session: `66805637-2193-454b-8d85-fe07967b1c70`
- Requested and resolved primary model: `claude-opus-5`
- Effort: `xhigh`
- Mode: read-only, tools limited to `Read,Grep,Glob`

| File | SHA-256 before and after review |
|---|---|
| `nbs/locking.py` | `6731B25D4BF34D4E169CB189793A79DAACCF0A5FAD81A6C9E2A3A9D579171053` |
| `tests/test_locking.py` | `739722D12E09E0D5DFA5A127835EEF2058AD9EC279605A835A9285C89A0B31BB` |
| `nbs/orchestrate.py` | `58ADB65B3498C25258D2E7F36D3915B2BF3E27CD1C7352AB211AF1B682432B66` |
| `nbs/schedule.py` | `51A111BFB9C52639382EDFECD80EBAB06F4A64898654DEEEB22DFC02F29A8CDF` |

The reviewer did not modify the tree. File hashes were rechecked after the review and matched the request.

## Gate Result

- Critical: 0
- High: 0
- Gate: passed

The reviewer independently confirmed that Windows `msvcrt` byte-range locks and POSIX `flock` are nonblocking here, a second handle conflicts, process death releases the lock, `orchestrate.run` remains inside the lock, and `orchestrate.Busy` compatibility is preserved.

## Findings and Disposition

| ID | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | Medium | Non-contention `OSError` values are reported as busy. | Accepted for hardening backlog. The observed effect is fail-closed availability and diagnostic loss, not integrity loss. |
| M2 | Medium | Lock-file setup and the zero-byte priming write can raise outside the busy contract. | Accepted for hardening backlog. Remove the unnecessary priming write when the locking helper is next hardened. |
| M3 | Medium | An unlock error can mask an otherwise successful run result. | Accepted for hardening backlog. Closing the handle releases the lock; a guarded unlock can be added with a focused regression test. |
| M4 | Medium | Replacing a held lock file on POSIX creates a new inode and defeats exclusion. | Deferred. It is inherited POSIX behavior, requires an operator to delete an active ignored file, and the supported target is Windows. |
| L5 | Low | `_SCHEDULE_LOCK` is bound at import time and tests can touch the real repo lock. | Accepted into planned Task 7, where schedule paths and entry points are rebuilt for Windows. |
| L6 | Low | The lock file has no holder PID or start time. | Rejected for this release. Holder metadata adds writes and stale-state interpretation without improving mutual exclusion. |

Medium and Low findings do not trigger another automatic review round under the project review policy.

## Verification

- `python -m pytest tests/test_locking.py tests/test_orchestrate.py tests/test_schedule.py -q` -> `60 passed`
- `python -m pytest -q` -> `255 passed, 11 failed`, with zero collection errors
- The 11 failures are mapped to later Windows work: path separators, POSIX permission assertions, Git subprocess encoding, and email test setup.
