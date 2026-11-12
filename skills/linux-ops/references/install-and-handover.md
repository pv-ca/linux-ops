# Installing software, and steps only the person can do

## Installing software

Pick the first source that has the software at a usable version, and name the source in `--what`:

1. the distribution's own repositories;
2. Flatpak, for desktop applications;
3. the vendor's package repository;
4. a downloaded script or binary, only when nothing above exists, read before it runs.

Prefer a drop-in file (`*.d/`) or a user unit to editing a file the package owns, so the change survives updates and its undo is deleting one file. For a language's packages, use its own isolation (a virtual environment, `pipx`) instead of overriding the system's protection.

## Steps only the person can do

A password prompt, a reboot and a firmware screen are out of your reach. Hand them over so they cannot be misread:

- Give the privileged step as one command or script that prints its own verification and saves the output to a file you can read afterwards.
- Before a reboot, record the change, and tell the user what to expect on the next boot and how to get back: which kernel entry to pick, where the backup is.
- When Secure Boot will ask to enroll a key, say so before the reboot: the screen appears once, and skipping it leaves the driver unloaded.
