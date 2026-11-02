# Working on polytoken-herdr-core

Last verified: 2026-10-31

## Scope and safety

Standalone Python standard-library adapter for stock, closed-source Polytoken.
Use documented hooks and CLI surfaces, and `hc`, not legacy `herdr`. Read
`hc --skill` before runtime work.

Runtime tests own their terminals and use a unique HC_SESSION, isolated HOME/XDG
paths and private session registries. Leave live global hooks, the user's core,
and existing terminals untouched. Humans decide agreements and permissions.
Do not copy acceptance records, synthesize approvals or use hc send --force.
Keep credentials out of output and context.

## Commands

```sh
python3 -m unittest discover -s tests -v
python3 scripts/probe_hc.py --relay --split-csi --proxy
python3 scripts/probe_polytoken.py --daemon --global --question
```

Human-only combined probe:

```sh
python3 scripts/probe_integration.py --interactive --global --question \
  --profile ~/.local/share/polytoken-herdr-test-profile
```

The profile must be new or previously marked by the probe. It retains human
choices while project/core runtime state remains disposable. Use one probe per
profile at a time. First attach: decide any agreement, wait OK, detach Ctrl+\\.
Second attach: inspect the pending question and detach; empty submission does
not dismiss it. The provider now asks once if a human chooses to answer instead.
No agent should answer. Checks cover blocked-send refusal, shutdown and observed
process disappearance; they cannot rule out unobserved detached processes.

## Contracts and code map

- `status.py` binds on session_start, rejects other sessions, retains closed IDs,
  and treats idle as handback rather than task success. No done status.
- `hook.py`/`relay.py` report observational facts with empty hook stdout, fixed OSC
  strings and bounded transport. Credentials prevent accidental routing, not
  malicious same-user access. Reports may be lost or reordered.
- `proxy.py`/`stream.py`/`output.py` serialize TUI and status writes. Retain the PTY
  slave through final drain on macOS. Deadlines: status 0.2s, bulk output 5s.
- `launcher.py` owns a private registry; failed reap retains it for recovery.
  Never substitute a global reap. It signals the immediate child, not all groups.
- `config.py` supports fresh project setup and opt-in global merge with backup,
  conflict refusal and idempotence. Global launch rejects project disable/duplicate
  entries. Arbitrary --config-dir did not redirect project hook discovery on 0.9.4.
- `scripts/` contains isolated probes; `tests/` contains unittest regressions.

## Verified delivery and follow-up roadmap

93 tests pass. Project and global human runs established status, ordinary send,
viewer detach/reattach and terminal shutdown with status cleared. Two observed
processes disappeared in the global run. Global headless question probe passed
blocked status, close-on-reap and empty private session listing. Full evidence
and caveats are in docs/review.md. Do not repeat passed human checks without a
specific new assertion.

The integration is delivered as experimental. Follow-up coverage:

1. Verify answer-to-idle in the stock TUI after the mock-provider one-shot fix.
   The prior repeated-question behavior was a probe defect, not an adapter result.
2. Expand permission/cancellation/provider/subagent and detached-process coverage.
   Never claim exhaustive cleanup from a finished hc record or observed PID set.
3. Verify persistent-profile acceptance across two runs and Linux runtime behavior.
4. Consider removing unused launcher.wait_for_tui after reference review and user
   agreement; do not replace runtime evidence with tests of that obsolete helper.

Keep README.md for humans choosing and using the project. Keep agent directions
and the roadmap here; detailed evidence belongs in docs/review.md. Apply deslop
to reader-facing prose. Manual hc controls are for direct herdr-core users; the
Herdr application invokes those controls automatically, while humans still decide
permissions. Update evidence with exact commands and distinguish tests, human
reports, and inference.
