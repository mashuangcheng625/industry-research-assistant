# Task center visual review — round 1

- Decision: `REWORK`
- Score: `8.4 / 10`
- Blocker: at 390 x 844 the last mobile navigation item ended at x=400 while
  the document client width was 375, so labels crowded and the final target was
  clipped.
- Runtime evidence: six task rows and six statuses rendered; desktop and tablet
  layouts, long content, cancellation modal, console, and network checks passed.
- Required change: replace positional `nth-child` hiding with stable semantic
  mobile navigation visibility while keeping the task center available.

The associated screenshots preserve the inspected desktop, tablet, mobile,
expanded-result, and cancellation states.
