# Verification record

## 2026-11-12: built-in reporter migration

Current local versions: `polytoken --version` printed **0.9.7** and `hc --version`
printed **0.1.20** on macOS. `polytoken --help`, `new --help` and `continue --help`
confirmed the attached CLI commands and `--sessions-dir`; they do not document
callback argv.

### Sources and design

[Polytoken's TUI Orchestrators documentation](https://docs.polytoken.dev/using-polytoken/tui-orchestrators/)
describes `HERDR_ENV`, `HERDR_BIN_PATH`, `HERDR_PANE_ID`, three state reports,
release on TUI exit, model/facet metadata and a resume command. Its
[changelog](https://docs.polytoken.dev/changelog/) dates baseline Herdr support
to 0.8.18 and improvements to 0.8.19. That is a documentation claim about baseline
support, not a verified minimum version for this adapter's callback ABI.

The approach comes from [Timo Freiberg's wrapper](https://github.com/TimoFreiberg/dotfiles/blob/main/bin/herdr-polytoken).
A GitHub root listing and recursive-tree licence search found no licence covering
that script; only two unrelated skill directories had licence files. This
adapter implements the approach independently and credits the source in README.

The new path is built-in reporter → absolute adapter callback → inner `/dev/tty`
→ fixed-frame extraction and serialization → outer terminal. The hook reducer,
hook handler and relay socket are deleted. The existing PTY proxy is retained:
a real isolated split-CSI experiment proved that removing it corrupts output.
Private-registry cleanup is retained for new managed sessions. Native resumes and
explicit registries are never reaped by the adapter.

### Fresh automated evidence

`python3 -m unittest discover -s tests -v` passed **80 tests** after the serialized
callback change. Tests cover fixed callback translation, invalid/duplicate
arguments, restricted session IDs, absolute callback environment, null-stream
output routing, restore-label validation, both sessions-directory argument forms,
legacy hook cleanup, backup/idempotence, preserving program aliases and fields,
installer round trips and the retained PTY/serialization/cleanup behavior.
Tests for the deleted reducer and relay were deleted with those components;
this count is not comparable to historical totals. New focused tests failed
before their production implementation. Probe-helper unit tests use doubles;
their printed PASS lines are not runtime evidence.

### Fresh isolated runtime evidence

Commands:

```sh
python3 scripts/probe_reporter.py
python3 scripts/probe_stock_reporter.py
```

- Callback session `phc-probe-45d44f69fe32`: working, idle, blocked and clear
  observed through `hc get`, callbacks using null streams and a changed cwd.
- Direct-write split-CSI session `phc-probe-74d06ac09d4f`: **failed**, rendering
  `mSPLIT-CSI-CHECK`. This rejected removing the PTY serializer.
- Serialized callback session `phc-probe-5f4bb958dfc3`: all three states and
  release passed, labels were read through hc, and the deliberately split CSI
  rendered without the stray character. This invokes the adapter's real callback
  executable and retained proxy, with synthetic callback arguments.
- Final callback session `phc-probe-1143f338ac85` also passed those checks and
  `herdr-app check mods/polytoken` under the private environment. The mod check
  proves its initial render, not live menu/start/resume interaction.
- Stock session `phc-stock-5b4507898c9a` stopped at an update question. No answer
  was supplied and no update was performed.
- With documented `updates.automatic_check=false` only in the scratch global
  config, stock session `phc-stock-b43978f3dafc` reached the licence agreement.
  It was left unanswered. **No stock callbacks were observed.** This does not
  confirm installed Polytoken's actual callback arguments or state transitions.
- Final stock harness session `phc-stock-39b5de02997a` also stopped at the
  unanswered licence agreement, emitted no callbacks, and left default
  terminal identities unchanged.

The successful probes compared the default hc session's terminal identities
before and after and found them unchanged. Each probe used a unique HC_SESSION,
private HOME/XDG paths, socket and registry and cleaned up only its own terminal
and core. The failed split-CSI probe also cleaned up its private terminal/core;
the successful next probe found the same default identities. No acceptance
record was copied and no agreement, permission or question was answered.

### Follow-up: human-check safety and capture retention

The human reporter check is now one command: `python3 scripts/probe_stock_reporter.py --human`.
It gives two on-screen steps, reports incomplete startup with exit code 2, and
unwinds on early exit or SIGTERM. It never supplies a human decision. Cleanup
uses the installed OpenAPI's authenticated `/health` and `/terminate` routes,
reading credentials only from its private session tree as described in
[Daemon Authentication](https://docs.polytoken.dev/reference/daemon-auth/).
If an authenticated daemon does not exit, the probe rechecks its PID/start-time/
command identity before signalling that immediate process. No forced CLI flag
is used. Every cleanup is attempted even if an earlier action fails.

- The follow-up full suite passes **87 tests**. New checks cover exclusive
  captures, process-identity stability, graceful and deliberately stubborn
  owned daemon processes, invalid ownership records and cleanup after an error.
- Early-exit session `phc-stock-5bb466c12636` was sent SIGTERM after owned terminal
  creation, before any agreement choice. Cleanup completed, the probe exited
  143, and default terminal identities were unchanged. This tests early startup
  exit; it does not establish native daemon cleanup after human acceptance.
- Callback session `phc-probe-5385de0f47f3` passed states/release, split CSI and
  the mod check with the new capture journal. Default terminal identities were
  unchanged.
- Every future probe creates an exclusive per-HC_SESSION journal before starting
  its core. Session identity is repeated in each record; raw stock callback
  captures have their own session-named file. `--capture-dir` collects these
  records without replacing previous runs.

### Operator acceptance and fresh combined stock check

The operator reported “polytoken-herdr-core reporter: human check run, EULA agreed”.
Their `phc-stock-f6b2d898ecab` capture contains working, idle, metadata and release
argv, but its initial hc status was null and its journal lacks cleanup completion.
That historical result remains incomplete; it is not called a pass.

The exact owned scratch HOME was identified through its session-named recorder
and reused in place, with the operator's choices intact. No acceptance file was
copied or modified. Fresh stock session `phc-stock-5d4fc2fb19a9` reached idle with
native callback exit codes 0 and no callback stderr; the earlier null-status
result was not reproduced. Actual metadata arguments carry display tokens for
model and facet; state reports carry the terminal operand, source, agent, state,
sequence, session ID and a trailing resume argv after `--`.

Combined session `probe-31085deb41d9` exercised actual public adapter commands
inside an owned shell and an explicit private caller-owned registry:

1. `run --global --sessions-dir ...` started real stock Polytoken and reached idle.
2. Ordinary follow-up completed a newer idle turn.
3. `/detach` released the TUI and hc status cleared.
4. `restore` read the same terminal's recorded labels and reattached the same native session.
5. Another ordinary follow-up completed, then the mock question reported blocked.
   An ordinary send was refused; no answer was supplied.
6. Owned terminal shutdown and authenticated private-daemon cleanup completed.
   The default core's terminal identities were unchanged before/after.

This combined probe has no forced CLI cleanup flag. Its session journal is
exclusive and records each phase. It validates retained-registry restoration;
it does not make disposable new-session history durable or establish every UI,
permission, cancellation, provider or detached-process path. Installed Polytoken
was 0.9.7 and hc was 0.1.20; older ABI compatibility is still not established.

### Known limits and remaining checks

- Native reporter argv and start/idle/blocked/release now have isolated stock
  evidence above; the earlier unanswered-agreement records remain historical.
- New managed sessions retain the old disposable-history behavior: cleanup deletes
  their private tree. A recorded restore label cannot recover history deleted
  with that tree; restore is usable only while that history remains available.
  Durable restoration of such sessions needs an explicit design decision.
- Restore of a running daemon in a retained registry passed. Stopped-daemon
  history, real menu/mod/alias launches, answer-to-idle and broader process cleanup
  still need runtime checks. Static argv and installer tests do not prove the app UI.
- The bridge removes asynchronous hook reduction and socket delivery. Failed
  callbacks, terminal stalls and abrupt process death can still lose reports.
  Status deferred during incomplete terminal sequences can be coalesced; idle
  is not success. Metadata has no OSC equivalent and is ignored.
- Permission, cancellation, provider, subagent and detached-process coverage is
  incomplete. Linux has not been runtime-tested; Windows is unsupported.
- The old human tests below establish only the former hook/relay implementation.
  They are retained as history and are not acceptance evidence for this change.

---

# Historical verification: hook/relay implementation

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
