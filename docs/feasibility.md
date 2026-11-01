# Integration feasibility

Investigated 2026-10-31 with installed Polytoken 0.9.4 and hc 0.1.15.

## Verified at runtime

Run `python3 scripts/probe_hc.py` (Python 3 and hc required).
The probe removes inherited HC variables, selects a unique HC_SESSION and
scratch XDG paths, starts its own core, and cleans up its terminal and core.
It does not launch Polytoken, read credentials, or install hooks.

On hc 0.1.15:

- A terminal program can report root status with
  `ESC ] 7501 ; state=working:app=polytoken ESC \\`.
- `state=blocked:kind=permission:app=polytoken` is retained by `hc get`.
- `hc wait` returns `reason: status`, `status: blocked`.
- The working-to-blocked transition increments `turn`; this is not proof of
  successful task completion.
- `hc send` refuses a blocked terminal with exit code 9. The integration must
  preserve this protection, not use `--force` to answer permission prompts.

This verifies the hc side only, not end-to-end Polytoken integration.

## Documented interfaces, not yet exercised end to end

Polytoken's [hook documentation](https://docs.polytoken.dev/harness-engineering/hooks/)
describes project `.polytoken/hooks.json` entries with a Bash handler receiving
JSON on stdin. Hooks receive `POLYTOKEN_SESSION_ID` when known. Hook stdout is
reserved for result JSON; it is not a route to the attached terminal.

`pre_model_turn` and `stop` are blocking hooks. Prompt-open and prompt-close
hooks are fire-and-forget; close is documented once per registration and
carries an interrogative ID. The documentation does not establish a global
sequence number or execution-order guarantee for concurrent handlers.

Installed CLI help confirms:

- `polytoken new --prompt TEXT` submits an initial prompt after attachment.
- `new --no-attach` starts a daemon without a TUI.
- `attach SESSION_ID` attaches to a running daemon.
- `new` and `attach` accept `--sessions-dir` for an isolated registry.

These CLI surfaces do not establish a supported external structured-answer API.
A human can interact with the attached TUI; automated permission answers remain
out of scope. Ordinary `hc send` input still needs a real Polytoken runtime test.

The hc [protocol documentation](https://github.com/herdrdev/herdr-core/blob/master/schema/README.md)
describes terminal operations and event subscriptions. Upstream
[status encoding](https://github.com/herdrdev/herdr-core/blob/cfbb01df6c883b88d7bf9ac0d4704b0bc5a7a0f8/crates/herdr-core/src/status.rs)
uses colon-separated key/value fields, base64 title/message fields, and an
optional ID for child records. Root `clear` clears all records. These additional
fields and clear behavior have not been tested by this project's probe.

## Isolated Polytoken exec probe

Run `python3 scripts/probe_polytoken.py`. This creates scratch HOME and XDG
paths, a private project config, a local credential-free mock provider, and
hooks that retain only field names and routing metadata. No license acceptance
flag is passed. It is an exec-only test, not proof of daemon/TUI behavior.

Verified on Polytoken 0.9.4:

- The local OpenAI-compatible provider receives streaming Chat Completions.
- Exec completes with exit 0 when the provider calls `exec_structured_output`.
- Project hooks fire for session_start, pre_user_prompt, pre_model_turn, and
  pre_tool_use, with a consistent POLYTOKEN_SESSION_ID in the observed run.
- Custom endpoint environment variables reach those hooks.
- Model/tool hook payloads include prompt_id; tool hooks also include call_id.
- No stop hook was observed on this structured-output completion path.

Initial probes failed because the mock returned non-streaming JSON, then plain
text instead of exec's required completion tool. Those failures were corrected;
the final exec-with-hooks probe passed.

`python3 scripts/probe_polytoken.py --daemon` also passed with a scratch
`new --no-attach --prompt` session. Its session_start, pre_user_prompt,
pre_model_turn, and stop hooks inherited routing variables and reported the same
session ID. The test waits for a stop-hook callback rather than screen text.
Cleanup uses only the scratch sessions registry. No acceptance flag was needed
for this headless path. This does not establish TUI startup, reattachment,
prompt-open/close behavior, or that stop means an irrevocably completed turn.

The `--daemon --question` variant also passed: the mock requested
`ask_user_question`, and the probe observed `interrogative_wants_open` with a
string `interrogative_id`, session identity, and inherited routing environment.
No answer was sent. This verifies the open payload only; close delivery and
permission-specific prompts are still unverified.

Both daemon variants now also load the production adapter hooks and private
Unix-socket relay. They passed with observed OSC `working` output and final
relay states `idle` (normal turn) and `blocked` (unanswered question). This joins
stock Polytoken hooks to the production relay; it does not substitute for the
combined hc/TUI probe below.

## Interactive launcher probe: human-gated

`python3 scripts/probe_integration.py` launched the real adapter inside a
scratch hc core and reached Polytoken's legal-acceptance dialog. No choice was
made, no approval keys were sent, and the scratch terminal/core were cleaned up.
Before acceptance, hc reported no status. This is not a passing end-to-end test.
The initial probe also mishandled `status: null`; its diagnostic assertion now
handles null explicitly. Human acceptance is required to validate the full TUI
flow. Do not automate that choice or copy acceptance records into scratch HOME.

## Human-assisted failure and hook-discovery correction

The operator ran the interactive probe and reached the mock OK reply, but hc
reported `status: null`, `turn: 0`. The probe failed. A headless reproduction
using `--daemon --separate-config` likewise called the provider but timed out
waiting for hooks when they lived at `adapter-config` instead of `.polytoken`.
The model config was loaded; hook discovery was not redirected as assumed.

The launcher now rejects config paths other than `<cwd>/.polytoken`, and the
interactive probe prepares that location. A regression test and the corrected
headless production-relay probe pass (25 unit/subprocess tests total). The
corrected interactive probe still needs a human rerun; the original combined
failure must not be treated as resolved end-to-end yet.

## Shutdown question-close observation

A production-hook `--daemon --question` run observed a real
`interrogative_has_closed` during private-registry reaping. It carried a string
interrogative_id and the original session identity. The subsequent live-session
listing was `[]`. No answer was supplied. The relay returned from blocked to
working, its pre-question activity; no stop was observed during this shutdown.
The wrapper must clear status explicitly after ending its managed session.
This does not verify all in-turn cancellation or permission outcomes.

## Proposed next experiment (not an implemented design)

Test a session-scoped local relay owned by a launcher attached to the hc PTY.
Hooks would send minimal event facts to that relay rather than emit OSC on
stdout or open a remembered `/dev/tty` path. Only the launcher would write OSC
to its terminal. Avoid forwarding prompt text, tool arguments, or credentials.

Before implementing a usable adapter, prove:

1. A scratch-config Polytoken session loads the expected hooks and supplies the
   actual payload fields on the installed version, without copying user secrets.
2. Hooks can reach the launcher through an explicitly provisioned, private local
   endpoint, with session identity checked and bounded handler timeouts.
3. A replacement attachment can establish ownership while the previous relay
   loses authority. Stale terminal paths and inherited environment alone cannot
   safely identify a session's current display.
4. Close-before-open delivery cannot resurrect a closed prompt. Keep closed-ID
   knowledge for the session or use an authoritative snapshot; a lock alone
   orders arrival, not the original events.
5. The adapter does not report `done` merely because a `stop` hook ran: later hooks
   can continue the turn. Cancellation, shutdown, and active goals also need
   explicit verified behavior.

Do not install live global hooks until these tests establish the contract.
