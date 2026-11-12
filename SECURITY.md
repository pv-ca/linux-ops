# Security

linux-ops runs inside your agent on your own machine, and its hook sees every shell command the agent runs. Please report anything that could expose your data or let it run something you did not ask for.

## Reporting a vulnerability

Use [private vulnerability reporting](https://github.com/pv-ca/linux-ops/security/advisories/new) (the repository's **Security** tab, then **Report a vulnerability**). Please do not open a public issue for it.

Say which version you use (`claude plugin list` shows it), your distribution, and the steps that show the problem. You will get an answer within a week.

Only the latest release gets fixes.

## What the plugin does and does not do

- **No network.** The scripts send nothing anywhere. What your agent reads from the journal goes to your model provider, like any other tool output.
- **No privilege of its own.** The scripts never call `sudo` or `doas`. They run as whoever the agent runs them as. When run under `sudo`, they hand the journal and snapshots back to you, but only for paths inside your home directory.
- **Local files only you can read.** The journal and snapshots live in `~/.local/state/linux-ops/`. They are created readable only by you and opened without following symlinks.
- **Credentials are masked, best effort.** Common forms of passwords, tokens and keys are masked before a command is written to the journal (see [Your data](README.md#your-data)). A secret in a form the mask does not know is stored as typed.
- **Undo runs commands.** `/linux-ops:undo` shows each command before running it. A recorded undo command is only as safe as the change it reverses, so read it first.

## In scope

- A secret the mask should catch that ends up in the journal.
- Journal or snapshot files readable by other users, or written through a symlink.
- A hook or script that can be made to run a command, through a crafted file name, package name or command line.
- An undo that runs something other than what it showed.
