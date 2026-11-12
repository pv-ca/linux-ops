---
description: Write down what has been set up on this Linux machine, from the linux-ops journal, so it can be reproduced on another one.
disable-model-invocation: true
argument-hint: "[output file]"
---

Write a document of what makes this machine this machine. $ARGUMENTS

The scripts are in `${CLAUDE_PLUGIN_ROOT}/skills/linux-ops/scripts/`.

1. Run `journal.py list --active` for the recorded changes still in effect.
2. Check each against the machine: leave out what is no longer true, and say that you did.
3. Write Markdown grouped as software installed and from which source, services, configuration files, and everything else. Give each item the command that reproduces it.

Save it to the file named above, or print it when none is named. Leave out secrets, and say what the journal cannot know: anything set up before it existed or by hand.
