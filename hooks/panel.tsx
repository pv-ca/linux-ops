// The linux-ops panel: what agents changed on this machine, said as a sentence, with its undo.
// One content, four places the person picks from: a chip in the prompt footer (default), a bar
// above the prompt, a side panel, or off. It runs `state.py status` on the host and draws the
// answer; no model turn is spent.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Change, Host, Layout, Status, View } from '../types'

const PANE = 'linux-ops'
const COMMAND = 'linux-ops-panel'
const LAYOUTS: readonly Layout[] = ['chip', 'bar', 'side', 'off']
// $.store keys. HIDDEN is what 0.3.0 drafts wrote: read once, so a hidden panel stays hidden.
const LAYOUT = 'panel-layout'
const HIDDEN = 'panel-hidden'
const SHOWN = 30
const SCRIPT = 'skills/linux-ops/scripts/state.py'
const DETECT = 'skills/linux-ops/scripts/detect_host.py'

const status = atom({ plugin: 'linux-ops', key: 'status' } as const, null, {
  shape: 'status-1',
})
const view = atom({ plugin: 'linux-ops', key: 'view' } as const, { layout: 'chip' } as View)
const host = atom({ plugin: 'linux-ops', key: 'host' } as const, null as Host | null)

const capital = (word: string) => word.charAt(0).toUpperCase() + word.slice(1)

// How the names the profile uses are written for a person.
const NAMES: Record<string, string> = {
  wayland: 'Wayland',
  x11: 'X11',
  selinux: 'SELinux',
  apparmor: 'AppArmor',
  none: 'no sudo',
}
const named = (word: string | null | undefined) => (word ? (NAMES[word] ?? word) : '')
const FULL = 90

/** `df -P` and `systemctl --failed` output as what is wrong now; nothing when all is well. */
export function alertsFrom(df: string, failed: string): Host['alerts'] {
  const alerts: Host['alerts'] = []
  const seen = new Set<string>()
  for (const line of df.split('\n').slice(1)) {
    const [device, , , , used, mount] = line.trim().split(/\s+/)
    const percent = Number.parseInt(used ?? '', 10)
    // `/` and `/home` on one filesystem are one full disk, not two.
    if (!device || !mount || seen.has(device) || !(percent >= FULL)) continue
    seen.add(device)
    alerts.push({
      text: `${mount} is ${percent}% full`,
      ask: `The filesystem at ${mount} is ${percent}% full. Find what is using the space and propose what can be freed safely. Change nothing before I agree.`,
    })
  }
  const units = failed.split('\n').filter(line => line.trim() !== '').length
  if (units > 0) {
    alerts.push({
      text: `${plural(units, 'service')} failed`,
      ask: 'systemctl --failed lists failed units on this machine. Diagnose each one and tell me what it means before changing anything.',
    })
  }

  return alerts
}

/** What `detect_host.py` and `uname` printed, as the panel shows the machine. */
export function hostFrom(profile: string, kernel: string, arch: string): Host | null {
  try {
    const p = JSON.parse(profile) as {
      os?: { id?: string; pretty_name?: string; version_id?: string }
      session?: { desktop?: string | null; type?: string | null }
      mac?: { system?: string | null; state?: string | null }
      init?: string
      package_manager?: string
      environment?: string
      privilege?: string
      notes?: string[]
    }
    const short = [capital(p.os?.id ?? 'Linux'), p.os?.version_id].filter(Boolean).join(' ')
    const machine = arch.trim()
    const tags = [
      machine,
      [p.session?.desktop, named(p.session?.type)].filter(Boolean).join(' on '),
      p.package_manager,
      p.init,
      [named(p.mac?.system), p.mac?.state].filter(Boolean).join(' '),
      named(p.privilege),
      // Bare metal is the unremarkable case; a container or a VM is worth a word.
      p.environment === 'physical' ? '' : p.environment,
    ]

    return {
      system: p.os?.pretty_name ?? short,
      short,
      // Fedora appends the architecture to the release; the tag beside it already says it.
      kernel: machine ? kernel.trim().replace(`.${machine}`, '') : kernel.trim(),
      // A fact the machine has no answer for (no desktop on a server) is left out.
      tags: tags.filter((tag): tag is string => Boolean(tag)),
      notes: p.notes ?? [],
      alerts: [],
    }
  } catch {
    return null
  }
}

async function profile($: EngineInterface): Promise<void> {
  const run = (argv: string[]) =>
    $.process.run(argv, { timeoutMs: 10000 }).then(
      ran => (ran.exitCode === 0 ? ran.stdout : ''),
      () => '',
    )
  const [detected, kernel, arch, df, failed] = await Promise.all([
    run(['python3', `${$.plugin.root}/${DETECT}`, '--compact']),
    run(['uname', '-r']),
    run(['uname', '-m']),
    run(['df', '-P', '/', '/home']),
    // Without systemd the command is missing and the line simply does not show.
    run(['systemctl', '--failed', '--no-legend', '--plain']),
  ])
  const found = hostFrom(detected, kernel, arch)
  await update($, host, () => found && { ...found, alerts: alertsFrom(df, failed) })
}

const isLayout = (value: unknown): value is Layout => LAYOUTS.includes(value as Layout)
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
const two = (n: number) => String(n).padStart(2, '0')

/** Milliseconds as "just now", "5 min ago", "3 h ago", "2 days ago". */
function ago(then: number): string {
  if (Number.isNaN(then)) return ''
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  if (minutes < 48 * 60) return `${Math.round(minutes / 60)} h ago`

  return `${Math.round(minutes / 1440)} days ago`
}

/** A snapshot's name, "20261111T160258" in local time, as milliseconds. */
function snapshotTime(stamp: string | null): number {
  const m = stamp?.match(/^(\d{4})(\d\d)(\d\d)T(\d\d)(\d\d)(\d\d)/)
  if (!m) return NaN
  const [year = 0, month = 1, day = 1, hour = 0, minute = 0, second = 0] = m.slice(1).map(Number)

  return new Date(year, month - 1, day, hour, minute, second).getTime()
}

/** "Today", "Yesterday", or "Nov 9": the heading a change is listed under. */
function dayOf(then: number): string {
  const date = new Date(then)
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const days = Math.round((start(new Date()) - start(date)) / 86400000)
  if (days <= 0) return 'Today'
  if (days === 1) return 'Yesterday'

  return `${date.toDateString().slice(4, 7)} ${date.getDate()}`
}

/** The changes under their day, newest day first, in the order the journal gave them. */
function byDay(changes: readonly Change[]): { day: string; rows: Change[] }[] {
  const days: { day: string; rows: Change[] }[] = []
  for (const change of changes) {
    const day = dayOf(Date.parse(change.ts))
    const open = days[days.length - 1]
    if (open?.day === day) open.rows.push(change)
    else days.push({ day, rows: [change] })
  }

  return days
}

/** The machine as kept in state; one kept by an older draft of the panel lacks the lists. */
async function machineOf($: EngineInterface): Promise<Host | null> {
  const kept = await read($, host)

  return kept && Array.isArray(kept.tags) && Array.isArray(kept.alerts) ? kept : null
}

async function layoutOf($: EngineInterface): Promise<Layout> {
  const { layout } = await read($, view)

  // State kept from an older draft of the panel has no layout.
  return isLayout(layout) ? layout : 'chip'
}

async function refresh($: EngineInterface): Promise<void> {
  let next: Status | null = null
  try {
    const ran = await $.process.run(['python3', `${$.plugin.root}/${SCRIPT}`, 'status'], {
      timeoutMs: 10000,
    })
    if (ran.exitCode === 0) next = JSON.parse(ran.stdout) as Status
  } catch {
    // No python3, no script: the panel says so instead of failing the session.
  }
  await update($, status, () => next)
  // Switched off, one status entry keeps the count in sight.
  $.ui.status(
    (await layoutOf($)) === 'off' && next && next.active.length > 0
      ? `linux-ops: ${plural(next.active.length, 'change')} to this machine`
      : undefined,
  )
}

/** Moves the panel to a layout and remembers it for later sessions. */
async function show($: EngineInterface, layout: Layout): Promise<void> {
  await $.store.set(LAYOUT, layout)
  await update($, view, () => ({ layout, isPeeking: false }))
  if (layout === 'side') await $.ui.open({ id: PANE, title: 'linux-ops' })
  else await $.ui.close({ id: PANE }).catch(() => undefined)
  await refresh($)
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: COMMAND,
      description:
        'Place the linux-ops panel (chip, bar, side or off): what agents changed on this machine',
    })
    void (async () => {
      const kept = await $.store.get(LAYOUT)
      const layout = isLayout(kept) ? kept : (await $.store.get(HIDDEN)) === true ? 'off' : 'chip'
      await update($, view, () => ({ layout }))
      await refresh($)
      if (layout === 'side') await $.ui.open({ id: PANE, title: 'linux-ops' })
      await profile($)
    })()

    return next(e)
  })

  // `/linux-ops-panel bar` places it; with no word it switches between off and the chip.
  on('command.run', { command: COMMAND }, async ($, e) => {
    const asked = e.args.trim().toLowerCase()
    if (asked !== '' && !isLayout(asked)) {
      return { text: `Unknown layout "${asked}". Use one of: ${LAYOUTS.join(', ')}.` }
    }
    const layout = isLayout(asked) ? asked : (await layoutOf($)) === 'off' ? 'chip' : 'off'
    await show($, layout)

    return {
      text:
        layout === 'off'
          ? `linux-ops panel off. /${COMMAND} brings it back.`
          : `linux-ops panel: ${layout}. Other layouts: /${COMMAND} ${LAYOUTS.filter(l => l !== layout).join(' | ')}.`,
    }
  })

  // A shell command may have changed the machine or the journal.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const ran = await next(e)
    void refresh($)

    return ran
  })

  // The side panel closed with the surface's own mark: fall back to the chip, the way back in.
  on('ui.close', async ($, e, next) => {
    if (e.id === PANE && e.origin.kind === 'person' && (await layoutOf($)) === 'side') {
      await $.store.set(LAYOUT, 'chip')
      await update($, view, () => ({ layout: 'chip' as const }))
    }

    return next(e)
  })

  // Chip: one quiet button beside the mode labels under the prompt. It opens a card above the
  // prompt, the nearest thing to a popover the surfaces have.
  on('ui.render', { component: 'SessionMode' }, async ($, e, next) => {
    if ((await layoutOf($)) !== 'chip') return next(e)
    const below = await next(e).catch(() => undefined)
    const { Box, Button } = $.ui.resolve(e)
    const now = (await read($, status)) as Status | null
    const machine = await machineOf($)
    const count = now?.active.length ?? 0
    const chip = (
      <Button
        key="chip"
        plain
        dimColor={count === 0}
        label={
          count > 0
            ? `linux-ops · ${plural(count, 'change')}`
            : machine
              ? `linux-ops · ${machine.short}`
              : 'linux-ops'
        }
        onPress={() => update($, view, v => ({ ...v, isPeeking: !v.isPeeking }))}
      />
    )

    return below ? (
      <Box flexDirection="row" gap={2}>
        {below}
        {chip}
      </Box>
    ) : (
      chip
    )
  })

  // Bar: the latest change as one sentence, its undo, and the way to the rest.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const layout = await layoutOf($)
    const isCard = layout === 'chip' && (await read($, view)).isPeeking === true
    if (e.props.hasSurvey || (layout !== 'bar' && !isCard)) return next(e)
    // Other mods share this slot: draw theirs below ours instead of replacing it.
    // next(e) rejects only when nothing answers beneath (the test harness).
    const below = await next(e).catch(() => undefined)
    const { Box, Text, Button } = $.ui.resolve(e)
    // bodyColumns counts terminal cells; other surfaces size the row themselves.
    const width = e.surface === 'terminal' ? e.props.bodyColumns : undefined
    const now = (await read($, status)) as Status | null
    const latest = now?.active[0]
    const count = now?.active.length ?? 0

    // The chip's card: the machine in one line, the latest change in the next.
    if (isCard) {
      const machine = await machineOf($)
      const kernel = machine?.kernel || undefined
      const close = () => update($, view, v => ({ ...v, isPeeking: false }))
      const card = (
        <Box flexDirection="column" width={width}>
          <Box flexDirection="row" alignItems="center" gap={2}>
            <Box flexGrow={1} flexShrink={1} minWidth={0}>
              <Text bold wrap="truncate-end">
                {machine?.system ?? 'This machine'}
              </Text>
            </Box>
            {kernel !== undefined && (
              <Box flexShrink={0}>
                <Text dimColor>kernel {kernel}</Text>
              </Box>
            )}
            <Button
              key="open"
              plain
              label="Open panel"
              onPress={async () => {
                await close()
                await $.ui.open({ id: PANE, title: 'linux-ops' })
              }}
            />
            <Button key="close" plain dimColor role="dismiss" label="Close" onPress={close} />
          </Box>
          <Box flexDirection="row" alignItems="center" gap={2}>
            <Box flexGrow={1} flexShrink={1} minWidth={0}>
              <Text wrap="truncate-end" dimColor={latest === undefined}>
                {latest === undefined
                  ? 'Nothing changed on this machine'
                  : `${latest.what} · ${ago(Date.parse(latest.ts))}`}
              </Text>
            </Box>
            {count > 1 && (
              <Box flexShrink={0}>
                <Text dimColor>+{count - 1} more</Text>
              </Box>
            )}
            {latest?.can_undo === true && (
              <Button
                key="undo-latest"
                label="Undo"
                onPress={() => $.prompt.fill({ text: `/linux-ops:undo ${latest.id}` })}
              />
            )}
          </Box>
        </Box>
      )

      return below ? (
        <Box flexDirection="column">
          {card}
          {below}
        </Box>
      ) : (
        card
      )
    }

    const bar = (
      <Box flexDirection="row" alignItems="center" gap={2} width={width}>
        <Box flexShrink={0}>
          <Text dimColor>linux-ops</Text>
        </Box>
        {/* The sentence is the one part that gives way: it shortens, the actions never wrap. */}
        <Box flexGrow={1} flexShrink={1} minWidth={0}>
          <Text wrap="truncate-end" dimColor={latest === undefined}>
            {now === null
              ? 'Could not read the journal (python3 is needed)'
              : (latest?.what ?? 'Nothing changed on this machine')}
          </Text>
        </Box>
        {latest !== undefined && (
          <Box flexShrink={0}>
            <Text dimColor>{ago(Date.parse(latest.ts))}</Text>
          </Box>
        )}
        {latest?.can_undo === true && (
          <Button
            key="undo-latest"
            label="Undo"
            onPress={() => $.prompt.fill({ text: `/linux-ops:undo ${latest.id}` })}
          />
        )}
        <Button
          key="all"
          plain
          label={count > 1 ? `All ${count}` : 'Open'}
          onPress={() => $.ui.open({ id: PANE, title: 'linux-ops' })}
        />
        <Button key="layout" plain dimColor label="Layout" onPress={() => show($, 'side')} />
        <Button key="hide" plain dimColor role="dismiss" label="Hide" onPress={() => show($, 'off')} />
      </Box>
    )

    return below ? (
      <Box flexDirection="column">
        {bar}
        {below}
      </Box>
    ) : (
      bar
    )
  })

  // Side panel: the latest change, then every change under its day, then the quiet facts.
  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text, Button } = $.ui.resolve(e)
    const now = (await read($, status)) as Status | null
    const layout = await layoutOf($)
    const fill = (text: string) => $.prompt.fill({ text })
    const snapshot = async () => {
      const ran = await $.process
        .run(['python3', `${$.plugin.root}/${SCRIPT}`, 'snapshot'], { timeoutMs: 60000 })
        .catch(() => undefined)
      $.ui.toast(ran?.exitCode === 0 ? 'Snapshot of this machine saved' : 'Snapshot failed')
      await refresh($)
    }
    // Where the panel lives: the three places, the current one marked, and off.
    const places = (
      <Box flexDirection="row" alignItems="center" gap={1}>
        <Text dimColor>Show as</Text>
        {(['chip', 'bar', 'side'] as const).map(place => (
          <Button
            key={`layout-${place}`}
            label={place}
            {...(place === layout
              ? { variant: 'secondary' as const }
              : { plain: true as const, dimColor: true })}
            onPress={() => show($, place)}
          />
        ))}
        <Box flexGrow={1} />
        <Button key="hide" plain dimColor role="dismiss" label="Hide" onPress={() => show($, 'off')} />
      </Box>
    )

    if (!now) {
      return (
        <Box flexDirection="column" gap={1}>
          <Text bold>linux-ops could not read its journal</Text>
          <Text dimColor>It needs python3 on this machine.</Text>
          <Button key="refresh" label="Try again" onPress={() => refresh($)} />
          {places}
        </Box>
      )
    }

    const latest = now.active[0]
    const older = now.active.length - SHOWN
    const machine = await machineOf($)
    const openDays = (await read($, view)).openDays ?? []

    return (
      <Box flexDirection="column" gap={1}>
        {machine && (
          <Box flexDirection="column">
            <Text bold>{machine.system}</Text>
            <Text dimColor>{[`Linux ${machine.kernel}`, ...machine.tags].join(' · ')}</Text>
            {machine.notes.map((note, index) => (
              <Text key={`note-${index}`} color="warning">
                {note}
              </Text>
            ))}
          </Box>
        )}
        {/* Only what is wrong now; a healthy machine shows nothing here. */}
        {machine !== null && machine.alerts.length > 0 && (
          <Box flexDirection="column">
            {machine.alerts.map((alert, index) => (
              <Box key={`alert-${index}`} flexDirection="row" alignItems="center" gap={2}>
                <Box flexGrow={1} flexShrink={1} minWidth={0}>
                  <Text color="warning">{alert.text}</Text>
                </Box>
                <Button
                  key={`look-${index}`}
                  plain
                  label="Look into it"
                  onPress={() => fill(alert.ask)}
                />
              </Box>
            ))}
          </Box>
        )}
        {latest === undefined ? (
          <Box flexDirection="column">
            <Text bold>Nothing changed on this machine</Text>
            <Text dimColor>When an agent changes something, it shows here with its undo.</Text>
          </Box>
        ) : (
          // The one framed thing in the panel: what a person most likely came to undo.
          <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1}>
            <Text dimColor>Latest change · {ago(Date.parse(latest.ts))}</Text>
            <Text bold>{latest.what}</Text>
            {latest.can_undo ? (
              <Box flexDirection="row" alignItems="center" gap={2}>
                <Button
                  key="undo-latest"
                  variant="primary"
                  label="Undo"
                  onPress={() => fill(`/linux-ops:undo ${latest.id}`)}
                />
                <Text dimColor>Fills the prompt; you send it.</Text>
              </Box>
            ) : (
              <Text dimColor>This one cannot be undone.</Text>
            )}
          </Box>
        )}

        {/* The latest change is in the frame above; the list is what came before it. */}
        {byDay(now.active.slice(1, SHOWN)).map(group => {
          const isOpen =
            group.day === 'Today' || group.day === 'Yesterday' || openDays.includes(group.day)
          if (!isOpen) {
            return (
              <Button
                key={`day-${group.day}`}
                plain
                dimColor
                label={`${group.day} · ${plural(group.rows.length, 'change')}`}
                onPress={() =>
                  update($, view, v => ({ ...v, openDays: [...(v.openDays ?? []), group.day] }))
                }
              />
            )
          }

          return (
          <Box key={`day-${group.day}`} flexDirection="column">
            <Text dimColor>{group.day}</Text>
            {group.rows.map(change => {
              const at = new Date(Date.parse(change.ts))

              return (
                <Box key={`row-${change.id}`} flexDirection="row" gap={2}>
                  <Box flexShrink={0}>
                    <Text dimColor>
                      {two(at.getHours())}:{two(at.getMinutes())}
                    </Text>
                  </Box>
                  {/* The full sentence: here it wraps, it is never cut. */}
                  <Box flexGrow={1} flexShrink={1} minWidth={0}>
                    <Text>{change.what}</Text>
                  </Box>
                  {change.can_undo ? (
                    <Button
                      key={`undo-${change.id}`}
                      plain
                      label="Undo"
                      onPress={() => fill(`/linux-ops:undo ${change.id}`)}
                    />
                  ) : (
                    <Text dimColor>no undo</Text>
                  )}
                </Box>
              )
            })}
          </Box>
          )
        })}
        {older > 0 && (
          <Button
            key="changes"
            plain
            label={`${older} older: ask for all`}
            onPress={() => fill('/linux-ops:changes')}
          />
        )}

        <Box flexDirection="column">
          <Box flexDirection="row" alignItems="center" gap={2}>
            <Text dimColor>
              {now.latest_snapshot === null
                ? 'No snapshot of this machine yet'
                : `Snapshot of this machine ${ago(snapshotTime(now.latest_snapshot))}`}
            </Text>
            <Button key="snapshot" plain label="Take one now" onPress={snapshot} />
          </Box>
          {now.unrecorded > 0 && (
            <Box flexDirection="row" alignItems="center" gap={2}>
              <Text dimColor>
                {plural(now.unrecorded, 'command')} ran since the last recorded change
              </Text>
              <Button
                key="review"
                plain
                label="Review"
                onPress={() =>
                  fill(
                    'Go through the commands linux-ops logged since the last recorded change and tell me which of them changed this machine. Record those with their undo; change nothing else.',
                  )
                }
              />
            </Box>
          )}
          {!now.logging && <Text color="warning">The command log is off.</Text>}
        </Box>
        <Box flexDirection="row">
          <Button
            key="improve"
            label="Improve this machine"
            onPress={() => fill('/linux-ops:improve')}
          />
        </Box>
        {places}
      </Box>
    )
  })
}
