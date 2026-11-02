import * as fs from "fs/promises";
import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input } from "gpui-base";
import { run, theme, agents, focused, home, appHome, knownAgents, exec } from "herdr";

const LAUNCHER = "/.local/bin/polytoken-herdr";
const FALLBACK_ARGV = ["run", "--global"];
const INSTALL_FALLBACK = "./install.sh (run from your polytoken-herdr-core checkout)";

/** The one command that fixes every setup problem this mod reports:
 *  install.sh in the checkout this mod is linked from. The link lives in the
 *  app's config dir, so resolve it before deriving the checkout. */
async function installCommand() {
  const sh = await exec("sh", ["-c",
    'p=$(readlink -f "$1") && case "$p" in */mods/polytoken) dirname "$(dirname "$p")";; esac',
    "sh", appHome() + "/mods/polytoken"]).catch(() => null);
  const checkout = sh && sh.code === 0 ? (sh.stdout || "").trim() : "";
  return checkout ? `cd ${checkout} && ./install.sh` : INSTALL_FALLBACK;
}

export default class Polytoken extends View {
  init(_props, cx) {
    this.model = InputState.new({ placeholder: "default model" });
    this.model.on("submit", (_event, cx) => this.launch("tab", cx));
    this.menuArgv = null;
    this.problems = null;
    this.installCmd = "";
    cx.spawn(async (cx) => {
      this.installCmd = await installCommand();
      const known = await knownAgents().catch(() => []);
      const entry = known.find((agent) => agent.key === "polytoken");
      this.menuArgv = entry?.run ?? null;
      this.problems = await this.setupProblems(entry);
      cx.notify();
    });
  }

  /** Read-only checks; the pane never repairs or installs anything itself. */
  async setupProblems(menuEntry) {
    const problems = [];
    try {
      await fs.stat(home() + LAUNCHER);
    } catch {
      problems.push("launcher missing from ~/.local/bin");
    }
    if (!menuEntry) problems.push("no polytoken entry in the Herdr app menu (programs.json)");
    let hooks = false;
    const cat = await exec("sh", ["-c", 'cat "${XDG_CONFIG_HOME:-$HOME/.config}/polytoken/hooks.json"']).catch(() => null);
    if (cat && cat.code === 0 && cat.stdout) {
      try {
        hooks = JSON.parse(cat.stdout).some((e) => e && typeof e.name === "string" && e.name.startsWith("herdr-"));
      } catch { /* unparseable hooks.json counts as not installed */ }
    }
    if (!hooks) problems.push("global status hooks not installed (prepare --global)");
    return problems;
  }

  recheck(cx) {
    cx.spawn(async (cx) => {
      this.installCmd = await installCommand();
      const known = await knownAgents().catch(() => []);
      this.problems = await this.setupProblems(known.find((agent) => agent.key === "polytoken"));
      cx.notify();
    });
  }

  launch(where, cx) {
    const base = this.menuArgv ?? [home() + LAUNCHER, ...FALLBACK_ARGV];
    const argv = [...base];
    const model = this.model.value().trim();
    if (model) argv.push("--model", model);
    const pane = focused()?.pane;
    if (where === "split" && pane) run("pane.split", { direction: "right", pane, argv });
    else run("tab.new", { name: "Polytoken", argv });
  }

  button(t, id, label, onClick, { primary = false, disabled = false } = {}) {
    return div().id(id).h(28).px(12).flex().items_center().rounded(6).text_size(12.5)
      .border_1().border_color(primary ? t.solid : t.border).bg(primary ? t.solid : t.surface)
      .text_color(primary ? t.solid_foreground : t.foreground)
      .when(disabled, (el) => el.opacity(0.5))
      .when(!disabled, (el) => el.cursor_pointer().hover((s) => s.bg(primary ? t.solid : t.hover)).on_click((_e, cx) => onClick(cx)))
      .child(label);
  }

  setupCard(t) {
    if (this.problems === null || this.problems.length === 0) return null;
    return v_flex().id("setup").gap(6).p(10).rounded(8).bg(t.surface).border_1().border_color(t.border)
      .child(div().text_size(12.5).font_semibold().text_color(t.blocked).child("Setup incomplete"))
      .children(this.problems.map((p) => div().text_size(12).text_color(t.muted).child(`- ${p}`)))
      .child(div().text_size(12).text_color(t.foreground)
        .child("Status reporting needs one command:"))
      .child(div().text_size(12).text_color(t.accent).font_semibold()
        .child(this.installCmd || INSTALL_FALLBACK))
      .child(this.button(t, "recheck", "Check again", (cx) => this.recheck(cx)));
  }

  sessions(t) {
    const live = agents().filter((a) => a.app === "polytoken");
    const dot = (a) => div().size(8).flex_none().rounded(4).bg(t[a.status] ?? t.dim);
    const row = (a) => h_flex().id(`s-${a.address}`).gap(8).px(8).h(30).items_center().rounded(6)
      .cursor_pointer().hover((s) => s.bg(t.hover))
      .on_click(() => run("agent.focus", { terminal: a.address }))
      .child(dot(a))
      .child(div().flex_1().min_w(0).truncate().text_size(12.5).text_color(t.foreground)
        .child(a.title || a.tab_name || a.address))
      .child(div().flex_none().text_size(11.5).text_color(t.dim).child(a.space_name || ""));
    if (live.length === 0) {
      return div().px(8).py(6).text_size(12).text_color(t.muted)
        .child("No Polytoken sessions are running. Start one above.");
    }
    return v_flex().gap(2).children(live.map(row));
  }

  render(_cx) {
    const t = theme();
    return v_flex().id("polytoken-root").size_full().bg(t.background).p(12).gap(10)
      .text_color(t.foreground).overflow_y_scrollbar()
      .child(h_flex().gap(8).items_center()
        .child(div().text_size(13).font_semibold().child("Polytoken"))
        .child(div().flex_1().text_size(11.5).text_color(t.dim).child("launch and resume")))
      .when(this.setupCard(t) !== null, (el) => el.child(this.setupCard(t)))
      .child(v_flex().gap(6)
        .child(div().text_size(11.5).text_color(t.dim).child("Start a session (status reported to Herdr)"))
        .child(h_flex().gap(8).items_center()
          .child(h_flex().flex_1().h(28).items_center().px(8).rounded(6).bg(t.surface)
            .border_1().border_color(t.input).child(Input.new(this.model).flex_1()))
          .child(this.button(t, "new-tab", "New tab", (cx) => this.launch("tab", cx), { primary: true }))
          .child(this.button(t, "split", "Split right", (cx) => this.launch("split", cx)))))
      .child(v_flex().gap(6)
        .child(div().text_size(11.5).text_color(t.dim).child("Running sessions"))
        .child(this.sessions(t)));
  }
}
