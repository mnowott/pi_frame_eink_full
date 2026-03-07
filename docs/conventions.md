# Documentation Conventions

Last updated: 2026-03-07

## Status Values

All tickets and bugs use one of these statuses:

| Status | Meaning |
|--------|---------|
| **Open** | Identified, not yet started |
| **In Progress** | Actively being worked on |
| **Under Review** | Implementation done, awaiting review/testing |
| **Closed** | Resolved and verified |
| **Rejected** | Will not fix; documented reason required |

## Document Format

Every document has a metadata header:

```
# Title
Status: Open | In Progress | Under Review | Closed | Rejected
Last updated: YYYY-MM-DD
```

## ID Schemes

- Tickets: `T-NNN` (e.g., T-001)
- Bugs: `B-NNN` (e.g., B-001)

## Index Tables

Each subfolder has an `index.md` with a summary table linking to all documents in that folder. Tables include: ID, title, status, last updated.

## Updating Rules

- Update `Last updated` on every change
- Update the parent `index.md` when adding/removing/changing status of a document
- Keep descriptions concise and actionable
