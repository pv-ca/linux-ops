---
description: Make this Linux machine better for what you do with it - the agent asks what you want, measures the machine, recommends changes for this hardware and distribution, applies the ones you pick with their undo, and measures again.
disable-model-invocation: true
argument-hint: "[what you want: faster, battery, games, more software, free space...]"
allowed-tools: Bash(python3 *linux-ops/scripts/detect_host.py*)
---

Help me improve this machine. $ARGUMENTS

The machine, as `detect_host.py` sees it:

!`python3 "${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/detect_host.py" --compact 2>&1 || true`

Follow `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/references/improve.md`: ask me first, look at the machine, measure, then give me a short list to pick from. Change nothing before I pick. Every change you make is recorded with its undo, and you measure again at the end and tell me plainly what got better and what did not.
