# Verification record

Updated 2026-10-31. The standalone integration is implemented and verified for the
workflows below. It remains experimental; this is not a production-readiness claim.

## Automated checks

The latest full suite passed 77 standard-library tests. Coverage includes session
binding and rejection of other sessions, closed-question ordering, authenticated
socket reporting, 50 simultaneous reports, bounded writes, PTY input and resize,
terminal restoration, and child-shutdown error paths. Global installation tests
cover preserving existing hooks, backups, idempotence, name conflicts, malformed
configuration, and project-level disable checks.

A mutation of the closed-question guard caused tests to fail. The restored guard
passed. The repeated-question provider regression also failed before its fix.
`git diff --check` passed for tracked changes; this does not lint untracked files.

### 2026-11-02: Herdr app plugin packaging

`python3 -m unittest discover -s tests` ran 92 tests and passed (OK) on the
plugin branch after the review fixes. The new coverage includes
`polytoken-herdr remove --global` (only adapter entries removed, stale
entries from a moved checkout removed, no file created when nothing was
installed, reinstall afterwards), repeated install/remove cycles that keep the
first `hooks.json.herdr-backup`, `install-app`/`remove-app` for the Herdr
`programs.json` entry, and an `install.sh`/`uninstall.sh` round trip. These are
unit tests in isolated temporary homes. No human or stock-daemon runtime check
was repeated for this change. The 2026-10-31 record above remains the history
for the earlier 77-test run.

## Runtime evidence

Tested versions: Polytoken 0.9.4 and hc 0.1.15 on macOS.

- An isolated hc probe parsed OSC status, returned blocked from wait, and refused
  ordinary input with exit 9. The real PTY serialization probe preserved split
  control sequences without stray screen characters.
- Stock-daemon probes exercised production hooks and relay for working/idle and
  unanswered-question blocked status. Global discovery passed using scratch XDG
  configuration, an empty project, and no `--config-dir`.
- After the one-shot question fix, `probe_polytoken.py --daemon --global --question`
  passed: the relay reported blocked, scoped reap returned 0, a real question-close
  hook arrived, and the private live-session listing was empty. No answer was sent.
- Human-run project-mode tests confirmed initial idle at turn 1 and guarded
  ordinary hc send returning idle at turn 2. hc kill left the terminal finished,
  exit 129, status cleared. Human detach worked.
- The operator reported the combined global/question probe passed and reached
  the question UI after reattachment. The supplied shutdown record showed the
  global launcher finished, reason killed, exit 129, status cleared, turn 7.
  Both of the two observed processes no longer existed after shutdown.

The original human run did accept the agreement and receive OK, but hc status
was null. Correcting project hook discovery and serializing terminal output
resolved that failure in subsequent human runs.

## Review findings addressed

Project hooks on the tested Polytoken version must live under `<cwd>/.polytoken`;
an arbitrary `--config-dir` did not redirect hook discovery. Global hooks use the
separate documented XDG location. The launcher validates the selected scope.

Two independent terminal writers corrupted split CSI output. The wrapper now
owns a private child PTY and serializes status and TUI bytes at control-sequence
boundaries. Retaining the slave through final drain prevents macOS output loss.

The default socket backlog accepted only 7 of 50 concurrent reports. A backlog
of 64 passes the burst regression. Status writes time out after 0.2 seconds;
bulk output has five seconds. A 300 ms full-pipe stall recovers in the test.

A child exiting between poll and terminate could skip terminal cleanup. The
proxy now tolerates ProcessLookupError and restores resources in a nested finally,
including when waiting for the child raises an error. Failed daemon reaping keeps
the private registry and reports its recovery path.

The test provider originally requested a question on every response, including
after the user answered. It now asks once and returns OK on the next request.
A real HTTP regression proves that change. Empty submission does not dismiss
`ask_user_question`; Ctrl+\\ detaches the hc viewer, and the probe later terminates
its managed session. The earlier test instructions were misleading about this.

Review covered status reduction, hook transport, configuration and launch commands,
output serialization, and proxy cleanup. The implementation uses argv process
launches, fixed status strings and a bounded local transport; hook stdout is empty.
The unused `wait_for_tui` helper remains a cleanup candidate, not a runtime dependency.

## Known limits and follow-up coverage

- The fixed answer-to-idle path has HTTP test coverage but has not been rerun in
  the stock TUI. The earlier repeated-question run does not prove that path.
- Question blocking and viewer reattachment have runtime evidence. Every tool
  permission dialog, cancellation path, provider failure, and subagent identity
  combination has not been tested.
- A finished terminal and absence of observed descendants do not prove that no
  detached daemon escaped observation. The proxy signals its immediate child;
  daemon cleanup relies on the private registry reap. SIGKILL cannot run cleanup.
- Status is best effort. Lost or reordered events can leave stale state, and
  prompt IDs do not provide total ordering within a turn. Deferred status may be
  coalesced. A relay acknowledgment is not proof that hc observed the status.
- Hooks can continue a turn after stop. Idle means handback, never task success;
  the adapter does not emit done or make authorization decisions.
- Relay credentials protect against accidental cross-session routing, not code
  running as the same OS user. Global Polytoken settings may still apply.
- Linux has not been runtime-tested here; Windows is unsupported. Persistent test
  profiles retain human choices, but acceptance persistence has not been verified
  across two runs. Use one probe at a time per profile.

## Safety boundaries

No live global hooks or pre-existing Herdr terminals were modified. Global-mode
tests used isolated user configuration. No agreement was accepted automatically,
no permission response was synthesized, and no blocked-input override was used.
The deslop skill was installed globally at the operator's request; this did not
change Polytoken hooks. No commits, pushes, or release claims were made.
