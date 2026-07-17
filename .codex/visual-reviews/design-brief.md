# Semiconductor research assistant design brief

## Subject and audience

Build a professional semiconductor research workspace for industry analysts, chip and process engineers, graduate candidates, and technical interviewers evaluating the project.

## Page job

Help a user select one of four research domains, ask a technically credible question, and inspect traceable evidence without losing context.

## Product character

- Professional, precise, evidence-led, and technically calm.
- Information-dense where useful, but never cramped.
- More like an engineering research console than a consumer chatbot or marketing landing page.

## Token direction

- Ink: `#101828` for primary content.
- Research blue: `#2861E7` for primary actions and selected states.
- Wafer teal: `#0E9384` for process and measurement signals.
- Materials violet: `#7A5AF8` for controlled domain distinction.
- Packaging amber: `#D97706` for controlled domain distinction.
- Surface: `#F7F9FC` with white working panels and low-contrast borders.

Use one interface sans family for Chinese/Latin text and a compact monospaced role only for recipe names, device IDs, process values, citations, and timestamps. Do not add a remote font dependency without checking availability and licensing.

## Layout direction

- Keep global navigation stable and compact.
- Let the current research domain, query, sources, and result hierarchy dominate working pages.
- Use cards only for bounded objects such as a research domain, source, dataset, or task—not as decoration around every section.
- Treat the four domains as peers, not a numbered sequence.

## Signature element

Use a restrained semiconductor evidence trace: subtle wafer-grid/process-path geometry that visually connects a question to sources and conclusions. It must support provenance and orientation rather than act as generic neon decoration.

## Avoid

- Purple-on-white AI gradients, excessive glow, glass cards, and floating decorative blobs.
- Generic robot imagery as the primary identity.
- Unexplained `01/02/03/04` numbering for unordered research domains.
- Marketing slogans inside operational research screens.
- Animations that slow scanning or ignore reduced-motion preferences.
