# Project agent guidance

## Frontend visual work

For tasks that create, redesign, or polish files under `frontend/`, use `$frontend-design` for art direction and implementation, then use `$frontend-visual-critic` for the independent quality gate.

Keep the root agent as orchestrator. Run these phases sequentially:

1. Write a short acceptance contract covering routes, states, viewports, preserved behavior, and visual direction.
2. Read `.codex/visual-reviews/design-brief.md`. Use `$frontend-design` to produce a compact plan covering palette, typography roles, layout, and one semiconductor-specific signature element. Reject generic AI-dashboard defaults before editing.
3. Spawn the project `frontend-builder` custom agent for implementation of the approved plan.
4. When it finishes, spawn the read-only `frontend-critic` custom agent and use `$frontend-visual-critic` for independent browser-based inspection.
5. Send a `REWORK` verdict back to the builder and repeat, up to four review rounds.
6. Finish only on `PASS`, or ask the user to choose between unresolved aesthetic tradeoffs.

Never run builder and critic as concurrent writers. Preserve authentication, API contracts, and backend behavior during visual-only work.

The frontend workspace is `frontend/`. Use:

```bash
npm run build
npm run lint
npm run dev -- --host 127.0.0.1
```

The product is a full-value-chain semiconductor industry research assistant with four first-class research directions:

- chip design;
- semiconductor materials and equipment;
- semiconductor front-end manufacturing;
- packaging and testing, including both conventional and advanced packaging.

Shared capabilities may be technically general, but UI terminology, navigation, examples, and evidence presentation must remain credible for semiconductor research across the full value chain.
