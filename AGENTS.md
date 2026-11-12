# Working on polytoken-herdr-core

Last verified: 2026-11-12

## Scope and safety

Standalone Python standard-library adapter for stock, closed-source Polytoken.
Use documented reporter and CLI surfaces, and `hc`, not legacy `herdr`. Read
`hc --skill` before runtime work.

Runtime tests own their terminals and use a unique HC_SESSION, isolated HOME/XDG
paths and private session registries. Leave live global hooks, the user's core,
and existing terminals untouched. Humans decide agreements and permissions.
Do not copy acceptance records, synthesize approvals or use hc send --force.
Keep credentials out of output and context.

## Commands

```sh
python3 -m unittest discover -s tests -v
python3 scripts/probe_reporter.py
python3 scripts/probe_stock_reporter.py
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

- `report.py` parses built-in reporter callbacks and validates session IDs. Idle
  means handback, not task success; no done status. `reporter.py` binds the absolute
  callback executable, reopens `/dev/tty` and records validated restore labels.
- `proxy.py`/`stream.py`/`output.py` serialize TUI and status writes. Retain the PTY
  slave through final drain on macOS. Deadlines: status 0.2s, bulk output 5s.
- `launcher.py` owns a private registry; failed reap retains it for recovery.
  Never substitute a global reap. It signals the immediate child, not all groups.
- `config.py` migrates obsolete project/global adapter hooks with a retained
  backup, preserving other configuration. No new status hooks are installed;
  status no longer depends on project hook discovery.
- `scripts/` contains isolated probes; `tests/` contains unittest regressions.

## Verified delivery and follow-up roadmap

86 tests pass. The built-in callback bridge has isolated working/idle/blocked,
release and split-CSI runtime evidence on hc 0.1.20. After an operator decided the agreement in its original scratch HOME, stock
Polytoken 0.9.7 passed start/release/restore, follow-up and unanswered blocked-input
checks through the public adapter. No acceptance records were copied. Earlier
project/global human passes cover only the former hook/relay path.
Full evidence and caveats are in docs/review.md. Do not repeat passed human
checks without a specific new assertion.

The integration is delivered as experimental. Follow-up coverage:

1. Verify stock reporter callbacks, resume/restore and answer-to-idle in the TUI.
   The prior repeated-question behavior was a probe defect, not an adapter result.
2. Expand permission/cancellation/provider/subagent and detached-process coverage.
   Never claim exhaustive cleanup from a finished hc record or observed PID set.
3. Verify persistent-profile acceptance across two runs and Linux runtime behavior.
4. `launcher.wait_for_tui` now serves standalone runs outside hc; managed runs
   retain the PTY proxy to prevent callback/TUI control-sequence interleaving.

Keep README.md for humans choosing and using the project. Keep agent directions
and the roadmap here; detailed evidence belongs in docs/review.md. Apply deslop
to reader-facing prose. Manual hc controls are for direct herdr-core users; the
Herdr application invokes those controls automatically, while humans still decide
permissions. Update evidence with exact commands and distinguish tests, human
reports, and inference.
