# Text layout refinement contract

## Scope

- Route: `/` home page.
- States: four-domain default view and empty search result.
- Viewports: 1440 × 900, 1024 × 768, and 390 × 844.

## Preserve

- Existing colors, domain cards, icons, navigation, authentication, routes, and click behavior.
- Existing four research-domain data and API contracts.

## Typography plan

- Display role: strong Chinese title with a compact 1.2–1.3 line height.
- Body role: 14–16px with 1.65–1.8 line height and controlled measure.
- Utility role: 10–12px uppercase or compact labels for domain codes and metadata.
- Replace sequence-like `01–04` labels with meaningful domain codes because the four domains are peers.

## Layout plan

```text
[subject image]  [eyebrow]
                 [product title]
                 [one concise product sentence]
                 [capability labels]

[4-domain heading]                 [search]
[domain title + readable summary + tags + action]
```

Reduce the empty gap between the hero and domain heading. Keep readable line lengths and prevent awkward mobile word wrapping or horizontal overflow.

## Quality gate

- No clipping or horizontal overflow.
- Card body and tag text remain legible at 390px.
- The empty state explains what to search next.
- Build and lint pass; visual rubric total at least 8.5 with typography/spacing at least 8.0.
