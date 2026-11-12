export type Change = { id: number; ts: string; what: string; can_undo: boolean }

/** What `state.py status` prints. */
export type Status = {
  directory: string
  active: Change[]
  unrecorded: number
  latest_snapshot: string | null
  megabytes: number
  logging: boolean
}

/** Where the panel is drawn: prompt-footer chip, bar above the prompt, side panel, or nowhere. */
export type Layout = 'chip' | 'bar' | 'side' | 'off'

/** What the person chose for the panel; mirrored in `$.store` across sessions. */
export type View = {
  layout: Layout
  /** The chip's card above the prompt is open; this session only. */
  isPeeking?: boolean
  /** Older days the person opened in the side panel; this session only. */
  openDays?: string[]
}

/** The machine, from `detect_host.py` and `uname`, as the panel prints it. */
export type Host = {
  /** "Fedora Linux 44 (KDE Plasma Desktop Edition)" */
  system: string
  /** "Fedora 44", for the chip. */
  short: string
  /** "7.2.15-200.fc44", without the architecture. */
  kernel: string
  /** One short fact each: architecture, desktop, package manager, init, security, privilege. */
  tags: string[]
  /** What `detect_host.py` warns about: an image-based root, a declarative system. */
  notes: string[]
  /** Something wrong now (a full disk, a failed service), and the prompt that looks into it. */
  alerts: { text: string; ask: string }[]
}

declare module 'claude-code' {
  interface PluginState {
    'linux-ops': { status: Shaped<Status | null>; view: View; host: Host | null }
  }
}
