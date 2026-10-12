# Design QA — VERUM mobile registration

- Source visual truth: `C:\Users\user\.codex\generated_images\01a12f85-1a05-77a0-9727-5665cdb07adb\exec-f48d7a7e-a185-4fbd-bc1e-a44d070a04a8.png`
- Browser-rendered implementation: `G:\Макс\VERUM-Competitions\implementation-home.png`
- Browser URL/state: `http://localhost:4173/?demo=1`, returning participant, open event, no existing registration
- Browser viewport: 1265 × 712; app surface is centered and capped at 520 CSS px
- Source pixels: 853 × 1844; implementation capture: 1265 × 712 at device scale 1
- Normalization: both artifacts were displayed side-by-side at equal column width in the in-app browser. The source is a tall concept board; the implementation remains a responsive scrolling mobile surface rather than compressing the complete concept into one viewport.

## Full-view comparison evidence

The implementation preserves the selected direction's black/orange campaign atmosphere, oversized VERUM wordmark, four-step journey, prominent event title, three essential event facts, sports photography and single orange action. The live layout is intentionally denser so the event identity and first action are reached sooner on a real Telegram viewport.

## Focused comparison evidence

The event panel and profile-form state were inspected separately in the in-app browser. The hero asset has the intended subject, orange rim light, dark crop and right-side focal point. Form labels, 52px controls, segmented gender control, sticky primary action, focus styling and validation affordances are readable and consistent.

## Required fidelity surfaces

- Fonts and typography: Inter provides a close geometric grotesk match. Display weights, line height and wrapping preserve the source hierarchy.
- Spacing and layout rhythm: compact 18px mobile gutters and consistent 10–28px section rhythm avoid the source concept's excessive vertical length.
- Colors and visual tokens: black base, #ff7300 action color, restrained warm glow, neutral borders and green success state match the visual direction with accessible contrast.
- Image quality and asset fidelity: a dedicated high-resolution generated breakdance photograph is used; no placeholder or CSS-drawn illustration replaces it.
- Copy and content: Russian labels are action-oriented and explicitly explain saved profiles and duplicate prevention.

## Interaction checks

- Home → profile navigation passed.
- Responsive scrolling and fixed primary action passed.
- Required-field validation and error surface are wired.
- Nomination selection, review and submission states are wired.
- Empty, loading, authentication error and existing-registration states are implemented.
- No visible browser console/runtime error occurred during the tested flow.

## Comparison history

- Initial pass: implementation rendered smaller inside the desktop browser canvas than the tall source board. This is an expected frame difference; the app-owned surface keeps its intended 520px maximum and responsive mobile behavior.
- Post-check: no actionable P0/P1/P2 visual mismatch remained. No fidelity fix was required after the normalized side-by-side comparison.

## Follow-up polish

- P3: add event-specific photography when organizers provide real campaign assets.

final result: passed
