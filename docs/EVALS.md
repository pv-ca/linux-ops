# How linux-ops is measured

Each case is a short story played out in a fresh Fedora 44 container (Podman). The same prompts run twice: once with the plugin installed (arm **with**) and once without it (arm **without**). A script then checks the machine and the answer. Both arms use the same model, effort and tools, and run as root inside the container, never on a real machine.

The harness itself is not published; this page describes what it does so the numbers below can be judged.

## Rules

- **Three rounds per cell** (case × arm × model) before any conclusion.
- **PASS** only when the case's own check passes and the machine has no more leftover differences than the case allows (see each case). A run cut off by a usage limit, or one where an earlier session did not do its part, is **INVALID** and does not count as a round.
- **When both arms pass**, the comparison is turns, cost and leftovers.
- **No memory between sessions.** Before a later session starts, the agent's own transcripts and logs from the earlier one are deleted, as when a different agent or a new conversation picks up the machine. The plugin's journal and snapshots stay: keeping them is what the plugin is for.
- The plugin takes its first snapshot when the container is set up, before anything is changed. That is the premise (installed before the trouble started), and it also makes the snapshot a perfect baseline, which a real machine would not always have.

## Cases

### undo-yesterday

Two sessions.

1. The agent installs nginx, moves it to port 8080, writes a `net.core.somaxconn` setting under `/etc/sysctl.d`, starts nginx and checks it answers. A check confirms the work was really done.
2. The person then installs `tree` and adds a line to `/etc/hosts`. A new session is asked: undo everything the agent did and nothing the person did, and say exactly what the agent changed.

PASS: nginx is gone (package, process, `/etc/nginx`), the somaxconn setting is gone, `tree` and the `/etc/hosts` line are still there, and at most 7 differences remain against the machine before session 1. Those 7 were measured on a clean undo: the person's two changes, a `systemd-libs` upgrade the repositories offer no way back from, and four account-file backups (`/etc/passwd-` and the like).

The package manager's history alone cannot tell the agent's install from the person's: both are `dnf install` minutes apart.

### what-changed

One session. Four changes are made without telling the agent: a package installed, a new file under `/etc/sysctl.d`, an edit to a configuration file whose date is then set back 30 days, and a deleted configuration file. Neither configuration file belongs to a package, so `rpm -Va` cannot vouch for them.

The agent is asked what changed in the last hour, one change per line in a file, without changing anything.

PASS: all four changes are named, the deletion as a deletion; the answer has at most eight lines; and nothing was reverted.

### slash-commands (smoke test, plugin only)

The undo-yesterday install, then `/linux-ops:changes`, an undo of only the somaxconn setting, and `/linux-ops:improve` for a small web server. It checks that the commands run end to end and leave the right state. There is no arm without the plugin, because the commands come from it.

## Results

Claude Code, `claude-opus-5-5` at high effort, 2026-11-11, plugin 0.3.0. Turns and cost are medians over the three rounds, all sessions of a round added together.

| Case | Arm | Passes | Median turns | Median cost (USD) |
| --- | --- | --- | --- | --- |
| undo-yesterday | with | 3 of 3 | 29 | 0.84 |
| undo-yesterday | without | 0 of 4 | 23 | 0.75 |
| what-changed | with | 3 of 3 | 9 | 0.27 |
| what-changed | without | 0 of 3 | 21 | 0.82 |
| slash-commands | with | 1 of 1 | 29 | 0.91 |

Without the plugin, undo-yesterday failed the same way each time: the new session could not tell the agent's nginx install from the person's own changes, so it left the install in place (105 or 106 differences). Three more rounds without the plugin passed, and were discarded: a newer Claude Code writes session logs under `~/.cache`, which the harness did not yet delete, and in two of them the agent read the earlier session's start and end times there. The third told the two apart by an 11-second gap between them. The harness now deletes those logs too, and the fourth valid round failed like the first three.

Without the plugin, what-changed failed the same way each time: the answer never said the configuration file had been deleted. Nothing on the machine records a deleted file that no package owns; only an earlier snapshot does.

## What these numbers do not show

- Three rounds per cell is enough to see a pattern, not to give a rate.
- Everything in a case happens within a few minutes, so time stamps help less than on a real machine where "yesterday" is a day away. In the other direction, a gap of a few seconds between the agent's work and the person's can itself give the answer away.
- Only Fedora, only Claude Code, only one model. Codex, Antigravity, smaller models and other distributions are not measured yet.
- Cases about diagnosis and refusing dangerous requests exist but have no valid rounds yet.
