# Task center acceptance contract

## Scope

- Route: authenticated `/tasks` inside the existing `BaseLayout`.
- Entry: add one stable sidebar navigation item named `任务中心`.
- API: consume the existing `GET /tasks`, `GET /tasks/{task_id}` and
  `POST /tasks/{task_id}/cancel` contracts without changing backend behavior.

## Required states

- Initial loading with stable page geometry.
- Populated list containing queued, running, retrying, succeeded, failed and
  cancelled tasks.
- Empty state that explains which actions create tasks.
- API error state with an explicit retry action.
- Long error text and long successful research result.
- Cancel confirmation, submitting state, accepted feedback and non-cancellable
  terminal/running-document states.
- Background polling while any task is non-terminal; no permanent spinner and
  no overlapping polling requests.

## Viewports

- Desktop: 1440 x 900.
- Tablet: 1024 x 768.
- Mobile: 390 x 844.

The page must not overflow horizontally. Primary controls remain keyboard
reachable with visible focus, and touch targets remain usable on mobile.

## Preserved behavior

- Preserve authentication, request interceptors, API paths, global navigation,
  industry selection and all existing pages.
- Do not introduce remote fonts, a new state-management library, or new backend
  fields.
- Do not imply percent progress: the backend exposes execution states, not a
  numeric progress contract.

## Visual direction

The task center is an operations ledger for semiconductor research work, not a
generic analytics dashboard.

- Palette: ink `#101828`, research blue `#2861E7`, wafer teal `#0E9384`,
  packaging amber `#D97706`, failure red `#D92D20`, surface `#F7F9FC`.
- Type: existing system sans for Chinese/Latin interface text; existing system
  monospace stack for task IDs, timestamps and execution metadata.
- Layout: compact page thesis and controls above a single task ledger; status
  counts form one restrained calibration strip rather than separate floating
  statistic cards.
- Signature: each task row carries a subtle four-node process trace
  `入队 → 执行 → 校验 → 终态`, visually derived from wafer process routing.
- Motion: only state/refresh transitions; respect `prefers-reduced-motion`.

## Quality gate

- `npm run lint` and `npm run build` pass.
- No console errors or failed task API requests in the inspected success state.
- Visual critic score is at least 8.5, every applicable dimension is at least
  8.0, and the final verdict is `PASS`.
