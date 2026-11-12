# Improve this machine

Read this when the person asks to make the machine better: faster, quieter, longer on battery, ready for games, more software to choose from, a smoother day at work. It is an interview, then measurements, then a short list they pick from. Nothing changes before they pick.

## 1. Ask first

One round, at most five questions, in plain words. Skip any the conversation already answered.

- What do you use this machine for most? (work, study, games, programming, media)
- What bothers you today? (slow, loud, hot, battery, disk full, a program you cannot get, something that keeps breaking)
- How will you know it got better? Their own words are the goal you measure against.
- How much risk is fine? Offer three: only changes that undo cleanly; also changes that need a reboot or log-out; also drivers and kernels.
- Anything you do not want touched?

A person who answers "just make it faster" gets the first level of risk and the measurements below; do not press for more.

## 2. Look at the machine

Read-only. Start from the host profile, then look only at what the answers point to:

- Hardware: CPU, memory, disks and their type, GPU and the driver in use, laptop or desktop, battery health when there is one.
- What is already tuned: power daemon and profile, swap and zram, I/O scheduler, enabled services, startup applications, package sources already configured.
- What is wrong now: failed units, a full disk, errors repeating in the journal, thermal throttling.

A fault found here comes before any tuning. Say so, and fix it first if they agree (`diagnose.md`).

## 3. Measure before

Pick the numbers that match what bothers them, and write each down with the command that produced it. Take a number three times when it varies and keep the middle one.

| Complaint | Measure |
| --- | --- |
| Slow to start | `systemd-analyze` and `systemd-analyze blame`; time to a usable desktop if they will time it |
| Slow in use | memory and swap in use, pressure in `/proc/pressure/`, what the top processes are |
| Disk full | free space per filesystem, and what the largest reclaimable items are |
| Battery | drain in watts on battery from `/sys/class/power_supply/`, idle, screen on |
| Hot or loud | temperatures and fan speed at idle and under the load they named |
| Games | frames per second and frame times in the game they named, with the overlay they already have |

When nothing measurable matches the complaint, say so now: the result will be their judgement, not a number.

## 4. Recommend

A list of at most seven, best first. For each: what it changes, what it should improve and by roughly how much, what it costs (battery for speed, noise for temperature), whether it undoes cleanly, and whether it needs a reboot. Leave out anything that does not apply to this hardware and distribution, and anything already in place.

Confirm every setting against the distribution's own documentation or the upstream project before recommending it; a value remembered from a forum post is not a source. Say which recommendations you could not confirm.

Then ask which ones to apply. Do not apply the list as a whole on a bare "yes" when it holds anything above their risk level.

## 5. Apply, one at a time

Each recommendation is one transaction (SKILL.md section 2): snapshot if the last is old, apply, verify, record with its undo. Stop at the first one that fails to verify and say so before going on.

## 6. Measure after, and say it straight

Repeat the same measurements the same way. Put before and after side by side in the receipt. "No measurable change" is a result: say it, and offer to undo that change, because a tweak that buys nothing is one more thing to break later.

## What not to recommend

These trade the machine's protection or stability for a gain that is small or imaginary. Leave them out of the list, and when the person asks for one, explain the cost once:

- Weakening protections for speed: CPU vulnerability mitigations, the mandatory access control system, the firewall.
- Scripts that empty the page cache on a timer: cached memory is memory working for the person.
- A kernel setting changed to a folklore value with no measurement that shows a problem.
- Two tools managing the same thing (two power daemons, two display managers, two firewalls).
- A kernel, driver or package from outside the enabled repositories, unless they asked for that source and accept that updates become theirs to watch.
- An "optimizer" script fetched from the network and run unread.

If they still want one after hearing the cost, it is their machine: apply it as any other change, recorded with its undo.

## Areas

**More software to choose from.** Adding a source is the usual wish: Flatpak with Flathub, the distribution's community repositories, Nix or Homebrew in the home directory, or another distribution in a container with distrobox when they want that distribution's package manager. Check what is already configured, prefer the source the distribution documents, and say which sources mix badly on this family. Replacing the system package manager is not a tweak: it means another distribution. Say so, and offer the container.

**Disk space.** Report what can be reclaimed before removing anything: package caches, old kernels the distribution's own tool would remove, the journal beyond its limit, unused Flatpak runtimes, container images, the trash. Removing files does not undo; say that for each item and get a yes per group.

**Battery.** Laptops only. One power daemon, the one the distribution ships; charge limits when the hardware exposes them; what keeps the machine awake in suspend. Measure idle drain before and after.

**Speed and responsiveness.** Usually a fault or a shortage, not a missing tweak: a failed service delaying boot, memory pressure, a disk that is nearly full, the wrong GPU driver. Fix those first. Compressed swap and an out-of-memory daemon help machines that freeze under load; measure pressure before recommending them.

**Games.** The GPU driver the distribution packages, 32-bit libraries where the platform needs them, the compatibility layer the store ships, and the settings its documentation asks for. A proprietary driver with Secure Boot on needs the person at the keyboard (`install-and-handover.md`).

**The working day.** Ask what they repeat: backups, sync, printing and scanning, clipboard history, shortcuts, what starts with the session. Propose the smallest thing that removes a repeated step. There is rarely a number here; the result is theirs to judge after a few days.
