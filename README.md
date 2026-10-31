# polytoken-herdr-core

A standalone integration between stock Polytoken and herdr-core.

**Status: feasibility investigation. No working adapter or installer yet.**

## Intended behavior

- Report Polytoken activity and requests for human input to Herdr.
- Let Polytoken start, inspect, message, and wait for hc-managed terminals.
- Let users send work to Polytoken and respond to prompts through Herdr.

Polytoken is closed source. This project must use supported hooks,
configuration, CLI/API surfaces, and external processes; native changes are
not an option. It must not infer status from screen text or automatically
approve permission requests.

## Verified starting points

- herdr-core accepts program status through OSC 7501, not screen inference.
- Its JSON-RPC API supports terminal operations and event subscriptions.
- Polytoken documents hooks for model/tool activity, turn handback, subagents,
  and opening/closing human-input prompts.
- Hook stdout is a hook-result channel, not an ordinary terminal-output channel.
- `polytoken new` launches a daemon and attaches a TUI by default. It supports
  an initial `--prompt` and a `--no-attach` mode.

Installed versions inspected during setup: Polytoken 0.9.4 and hc 0.1.15.
Upstream documentation may describe a newer interface than these binaries.

## Questions to resolve before implementation

1. How can daemon hooks securely target the terminal displaying their session,
   including detach/reattach and multiple simultaneous sessions?
2. What exact OSC 7501 payload and lifecycle semantics does installed hc accept?
3. Which incoming operations can use documented interfaces, and which require
   a human attached to the terminal? Structured permission/question responses
   are not yet established as a supported external API.
4. How can concurrent hook events preserve accurate status without stale
   background callbacks overwriting newer state?

## Verification constraints

Runtime tests must use an isolated `HC_SESSION` and scratch XDG paths.
Never restart or stop the user's core, modify existing terminals, or install
live global Polytoken hooks as a side effect of tests. Permission decisions
remain with the user; blocked-terminal protections must not be bypassed.

## Sources

- [herdr-core](https://github.com/herdrdev/herdr-core)
- [herdr-core protocol](https://github.com/herdrdev/herdr-core/blob/master/schema/README.md)
- [Polytoken hooks](https://docs.polytoken.dev/harness-engineering/hooks/)
- Installed `hc --skill`, `hc --help`, and `polytoken new --help`
