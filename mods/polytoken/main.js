import { View, div } from "gpui-kit";
import { v_flex, h_flex, InputState, Input } from "gpui-base";
import { run, theme, focused, home, appHome, knownAgents, exec } from "herdr";

const LAUNCHER = "/.local/bin/polytoken-herdr";
const FALLBACK_ARGV = ["run", "--global"];
const INSTALL_FALLBACK = "./install.sh (run from your polytoken-herdr-core checkout)";
const RECENT_LIMIT = 12;

const shellQuote = (s) => `'${s.replace(/'/g, `'\\''`)}'`;

/** The one command that fixes every setup problem this mod reports:
 *  install.sh in the checkout this mod is linked from. The link lives in the
 *  app's config dir, so resolve it before deriving the checkout. */
async function installCommand() {
  const sh = await exec("sh", ["-c",
    'p=$(readlink -f "$1") && case "$p" in */mods/polytoken) d=$(dirname "$(dirname "$p")") && [ -f "$d/install.sh" ] && printf %s "$d";; esac',
    "sh", appHome() + "/mods/polytoken"]).catch(() => null);
  const checkout = sh && sh.code === 0 ? (sh.stdout || "").trim() : "";
  return checkout ? `cd ${shellQuote(checkout)} && ./install.sh` : INSTALL_FALLBACK;
}

/** Stored sessions, running ones included, newest first; null when Polytoken
 *  cannot list them. Subagent and legacy records are left out. */
async function recentSessions() {
  const out = await exec("polytoken", ["sessions", "--all", "--format", "json"]).catch(() => null);
  if (!out || out.code !== 0) return null;
  let list;
  try { list = JSON.parse(out.stdout); } catch { return null; }
  if (!Array.isArray(list)) return null;
  return list
    .filter((s) => s && typeof s.session_id === "string"
      && s.parent_session_id?.kind === "standalone")
    .sort((a, b) => String(b.last_activity_at ?? "").localeCompare(String(a.last_activity_at ?? "")))
    .slice(0, RECENT_LIMIT);
}

function ago(stamp) {
  const minutes = Math.floor((Date.now() - Date.parse(`${String(stamp).slice(0, 19)}Z`)) / 60000);
  if (!Number.isFinite(minutes)) return "";
  if (minutes < 60) return `${Math.max(minutes, 0)}m ago`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}h ago`;
  return `${Math.floor(minutes / (60 * 24))}d ago`;
}

export default class Polytoken extends View {
  init(_props, cx) {
    this.model = InputState.new({ placeholder: "default model" });
    this.model.on("submit", (_event, cx) => this.launch("tab", cx));
    this.menuArgv = null;
    this.problems = null;
    this.installCmd = "";
    this.recent = undefined;
    this.refresh(cx);
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
    const launcher = await exec("sh", ["-c", 'test -x "$1"', "sh", home() + LAUNCHER]).catch(() => null);
    if (!launcher || launcher.code !== 0) problems.push("launcher missing from ~/.local/bin");
    if (!menuEntry) problems.push("no polytoken entry in the Herdr app menu (programs.json)");
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

  refresh(cx) {
    cx.spawn(async (cx) => {
      this.recent = await recentSessions();
      cx.notify();
    });
  }

  launcherArgv() {
    return [...(this.menuArgv ?? [home() + LAUNCHER, ...FALLBACK_ARGV])];
  }

  open(where, argv) {
    const pane = focused()?.pane;
    if (where === "split" && pane) run("pane.split", { direction: "right", pane, argv });
    else run("tab.new", { name: "Polytoken", argv });
  }

  launch(where, _cx) {
    const argv = this.launcherArgv();
    const model = this.model.value().trim();
    if (model) argv.push("--model", model);
    this.open(where, argv);
  }

  /** Resumes through the launcher so status reporting stays on, from the
   *  session's own project folder when Polytoken recorded one. */
  resume(session, where) {
    const argv = [...this.launcherArgv(), "--continue", session.session_id];
    const folder = session.project_path;
    this.open(where, typeof folder === "string" && folder
      ? ["sh", "-c", 'cd -- "$1" && shift && exec "$@"', "sh", folder, ...argv]
      : argv);
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
    if (this.recent === undefined) {
      return div().px(8).py(6).text_size(12).text_color(t.muted).child("Reading stored sessions...");
    }
    if (this.recent === null) {
      return div().px(8).py(6).text_size(12).text_color(t.muted)
        .child("Polytoken could not list stored sessions (polytoken sessions --all).");
    }
    if (this.recent.length === 0) {
      return div().px(8).py(6).text_size(12).text_color(t.muted)
        .child("No stored Polytoken sessions to resume.");
    }
    const small = (id, label, onClick) => div().id(id).flex_none().h(22).px(8).flex().items_center()
      .rounded(5).text_size(11.5).border_1().border_color(t.border).bg(t.surface)
      .cursor_pointer().hover((s) => s.bg(t.hover)).on_click(onClick).child(label);
    const row = (s) => {
      const folder = typeof s.project_path === "string" ? s.project_path.split("/").filter(Boolean).pop() ?? "" : "";
      const detail = [folder, s.is_live ? "running" : ago(s.last_activity_at)].filter(Boolean).join(" · ");
      return h_flex().id(`r-${s.session_id}`).gap(8).px(8).h(30).items_center().rounded(6)
        .hover((st) => st.bg(t.hover))
        .child(div().flex_1().min_w(0).truncate().text_size(12.5).text_color(t.foreground)
          .child(s.effective_title || s.last_user_message_preview || s.session_id))
        .child(div().flex_none().text_size(11.5).text_color(t.dim).child(detail))
        .child(small(`rt-${s.session_id}`, "Tab", () => this.resume(s, "tab")))
        .child(small(`rs-${s.session_id}`, "Split", () => this.resume(s, "split")));
    };
    return v_flex().gap(2).children(this.recent.map(row));
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
        .child(h_flex().gap(8).items_center()
          .child(div().flex_1().text_size(11.5).text_color(t.dim).child("Resume a recent session"))
          .child(this.button(t, "refresh", "Refresh", (cx) => this.refresh(cx))))
        .child(this.sessions(t)));
  }
}
