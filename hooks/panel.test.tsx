import { expect, test } from 'claude-code/testing'

// The mod's tsconfig has no DOM or Node types; the test runner has the timer.
declare const setTimeout: (run: () => void, ms: number) => unknown

const SITE = { scroll: { offset: 0, bodyRows: 30 }, view: {} } as const
const CHIP = { plugin: 'linux-ops', component: 'SessionMode', props: { modes: [] } } as const
const BAR = {
  plugin: 'linux-ops',
  component: 'AbovePrompt',
  props: { hasSurvey: false, isCollapsed: false, isWorking: false, maxRows: 12, bodyColumns: 100, ...SITE },
} as const
const PANE = {
  plugin: 'linux-ops',
  component: 'Pane',
  requestId: 'linux-ops',
  props: { title: 'linux-ops', isFocused: false, bodyColumns: 60, placement: 'dock', ...SITE },
} as const

const STATUS = {
  directory: '/home/u/.local/state/linux-ops/abc',
  active: [
    { id: 5, ts: '2026-11-11T16:03:32+0000', what: 'nginx serves on port 8080', can_undo: true },
    { id: 3, ts: '2026-11-11T16:03:19+0000', what: 'Installed nginx', can_undo: false },
  ],
  unrecorded: 2,
  latest_snapshot: '20261111T160258',
  megabytes: 1.2,
  logging: true,
}

const PROFILE = {
  os: { id: 'fedora', pretty_name: 'Fedora Linux 44 (KDE Plasma Desktop Edition)', version_id: '44' },
  session: { desktop: 'KDE', type: 'wayland' },
  mac: { system: 'selinux', state: 'enforcing' },
  init: 'systemd',
  package_manager: 'dnf',
  environment: 'physical',
  privilege: 'sudo',
  notes: [],
}
// `/` and `/home` on one device, 93% full: one alert, not two.
const DF = `Filesystem 1024-blocks Used Available Capacity Mounted on
/dev/nvme0n1p3 100 93 7 93% /
/dev/nvme0n1p3 100 93 7 93% /home
`

test('chip by default; the command and the panel move it; undo only fills the prompt', async ($, on) => {
  const stored: Record<string, unknown> = {}
  const opened: string[] = []
  const filled: string[] = []
  on('command.register', () => ({ value: { command: 'linux-ops-panel' } }))
  on('ui.open', (_, e) => {
    opened.push(e.id)

    return { value: { isPlaced: true } }
  })
  on('ui.close', () => ({ value: undefined }))
  on('ui.status', () => ({ value: undefined }))
  on('store.get', (_, e) => ({ value: stored[e.key] }))
  on('store.set', (_, e) => {
    stored[e.key] = e.value

    return { value: undefined }
  })
  on('prompt.fill', (_, e) => {
    filled.push(e.text)

    return { isFilled: true }
  })
  on('process.run', (_, e) => ({
    value: {
      exitCode: 0,
      stdout:
        e.argv[0] === 'uname'
          ? e.argv[1] === '-m'
            ? 'x86_64\n'
            : '7.2.15-200.fc44.x86_64\n'
          : e.argv[0] === 'df'
            ? DF
            : e.argv[0] === 'systemctl'
              ? ''
              : e.argv.includes('--compact')
                ? JSON.stringify(PROFILE)
                : JSON.stringify(STATUS),
      stderr: '',
      isStdoutTruncated: false,
      isStderrTruncated: false,
    },
  }))
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  // What Claude Code draws without the panel.
  on('ui.render', ($, e) => {
    const { Text } = $.ui.resolve(e)

    return <Text>engine only</Text>
  })

  await $.session.start({ cwd: '/', surface: 'desktop', isInteractive: true })
  // The start refreshes in the background: give it a turn to land.
  await new Promise<void>(done => setTimeout(done, 50))

  // Default: a chip, no bar. The chip opens a card above the prompt without moving the layout.
  const chip = await $.ui.mount({ ...CHIP, surface: 'desktop' })
  expect((await chip.find({ key: 'chip' }))?.props.label).toBe('linux-ops · 2 changes')
  await chip.press({ key: 'chip' })
  expect(stored['panel-layout']).toBeUndefined()
  await chip.unmount()

  // The card: the machine, the latest change, and the way to the full panel.
  const card = await $.ui.mount({ ...BAR, surface: 'desktop' })
  expect(await card.find({ type: 'Text', text: /^Fedora Linux 44/ })).toBeTruthy()
  expect(await card.find({ type: 'Text', text: /^kernel 7\.2\.15-200\.fc44$/ })).toBeTruthy()
  await card.press({ key: 'open' })
  expect(opened).toEqual(['linux-ops'])
  expect(await card.find({ key: 'open' })).toBeUndefined()
  await card.unmount()

  // The side panel: the machine, the latest change with its undo, the rest by day, the places.
  const pane = await $.ui.mount({ ...PANE, surface: 'desktop' })
  expect((await pane.find({ type: 'Text', text: /^Linux 7/ }))?.text).toBe(
    'Linux 7.2.15-200.fc44 · x86_64 · KDE on Wayland · dnf · systemd · SELinux enforcing · sudo',
  )
  expect(await pane.find({ type: 'Text', text: /^\/ is 93% full$/ })).toBeTruthy()
  expect(await pane.find({ type: 'Text', text: /\/home is/ })).toBeUndefined()
  await pane.press({ key: 'improve' })
  expect(filled.splice(0)).toEqual(['/linux-ops:improve'])
  expect(await pane.find({ type: 'Text', text: /^nginx serves on port 8080$/ })).toBeTruthy()
  expect(await pane.find({ type: 'Text', text: /^no undo$/ })).toBeTruthy()
  expect(await pane.find({ type: 'Text', text: /2 commands ran since/ })).toBeTruthy()
  await pane.press({ key: 'undo-latest' })
  expect(filled).toEqual(['/linux-ops:undo 5'])
  expect(opened).toEqual(['linux-ops'])
  await pane.press({ key: 'layout-bar' })
  expect(stored['panel-layout']).toBe('bar')
  await pane.unmount()

  // The bar: the sentence and its undo; Hide switches the panel off.
  const bar = await $.ui.mount({ ...BAR, surface: 'desktop' })
  expect(await bar.find({ type: 'Text', text: /^nginx serves on port 8080$/ })).toBeTruthy()
  await bar.press({ key: 'undo-latest' })
  expect(filled).toEqual(['/linux-ops:undo 5', '/linux-ops:undo 5'])
  await bar.press({ key: 'hide' })
  expect(stored['panel-layout']).toBe('off')
  expect(await bar.find({ key: 'undo-latest' })).toBeUndefined()
  await bar.unmount()

  // The command is the way back, and takes a layout by name.
  const typed = (args: string) =>
    $.command.run({
      command: 'linux-ops-panel',
      args,
      origin: { kind: 'composer' },
      presentation: { isFullscreen: false, columns: 100 },
    })
  await typed('side')
  expect(stored['panel-layout']).toBe('side')
  expect((await typed('corner')).text).toMatch(/Unknown layout/)
  expect(stored['panel-layout']).toBe('side')
})
