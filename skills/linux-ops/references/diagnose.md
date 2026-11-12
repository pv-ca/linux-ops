# Diagnosing a fault

State what you observed on this host in this session, and label the rest as expected or unknown. Each pair below looks alike and fails differently, so prove the right-hand side:

```text
installed ≠ loaded or running      configured ≠ in effect      enabled ≠ active
mounted ≠ writable ≠ visible to the application      link up ≠ route ≠ DNS
command exited 0 ≠ the outcome the user wanted      snapshot ≠ backup
```

- **Find the layer before touching it.** A denied access may come from mode bits, ownership, an ACL, a mount option, a sandbox (Flatpak, Snap) or SELinux/AppArmor. Read which one refuses; widening permissions on the wrong layer fixes nothing and weakens the machine.
- **Start from what changed.** When something used to work, run `state.py diff <snapshot from before>` or `state.py history` first and test the changed component before anything else.
- **Stop circling.** After two attempts of the same kind with no new evidence, stop changing things, list what has been proven, and collect the one fact that separates the remaining causes.
- **Say when it is not this machine.** When the configuration is correct and the fault is a known regression, a vendor's refusal or missing hardware support, say so early. Search the distribution's tracker for the exact kernel, driver and device before a third attempt, and offer the last working version as a fallback rather than more local changes.
