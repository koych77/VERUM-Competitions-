# VERUM cloud handoff

Current production branch: `cloudflare-workers`.

Live Worker: https://verum-competitions.koych77.workers.dev

## Infrastructure status inherited from earlier work

These points were reported in the previous handoff. Infrastructure was not re-verified during the 13 October design-only task.

- Cloudflare Worker and D1 database are connected.
- Telegram webhook points to Cloudflare.
- The participant registration flow was redesigned and deployed.
- A D1 unique index prevents more than one registration for the same event, user and registration type.
- Three revised multi-role visual directions are saved under `design/concepts/`.

## Design handoff — 13 October 2026

The complete new design package is in [`atlas/README.md`](atlas/README.md): 89 detailed offline HTML screens, six generated image boards, role/permission and duplicate-handling specifications, generation prompts and a validation script. Open `atlas/index.html` after downloading the folder with its relative assets.

The design task does not change production code, the database, Telegram settings or deployments. All examples are synthetic. Original generated boards may have text discrepancies; the HTML screens and SPEC.md govern implementation.

Important implementation gap confirmed in local code: participant profile endpoint is a placeholder; directory endpoints return empty results. The current unique index is event + user + registration type, not event + physical person. Full roles, saved profiles/drafts, representative links and cross-account duplicate protection remain to implement. Do not describe them as already shipped based on screenshots or UI labels.

## Product model to implement next

Telegram accounts may have several roles:

- participant;
- parent;
- coach;
- event organizer;
- administrator.

Registration uniqueness must be based on the physical participant, not the Telegram account that submitted the form. A parent and a coach must never create two registrations for the same child and event.

Planned core entities:

- `accounts` — Telegram identities;
- `people` — physical participants;
- `account_roles` — enabled modes for an account;
- `person_links` — participant/self, parent/child and coach/student relationships;
- `events` and `nominations`;
- `registrations` — unique by `event_id + person_id`;
- `organizer_event_access` — organizer permissions scoped to events;
- `audit_log` — administrative changes and merge history.

## Duplicate policy

1. Exact `event_id + person_id` match opens or updates the existing application.
2. Possible matches by normalized full name and date of birth create a conflict for authorized review; they are signals, not proof of identity, and must not expose unrelated children's data.
3. Profiles submitted by different adults are never merged silently.
4. The planned administrator flow merges confirmed duplicates while preserving an audit trail and separately validating inherited access rights. It is not implemented yet.

## Visual concepts

1. Parent mode with a role switcher, children list and event poster using the VERUM logo.
2. Coach mode with a selectable team roster and locked existing registrations.
3. Organizer mode with a conflict-review queue.

All concepts intentionally avoid generated people in event posters and use the VERUM logo with orange stage lighting instead.
