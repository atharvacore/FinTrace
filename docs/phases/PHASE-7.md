# Extra after Phase 6: Admin Screens

Date: 2026-10-13 · Branch `wip/phase-7` (built on Phase 6, pull request #3)

## Result

| | |
|---|---|
| Frontend | `npm run typecheck`, `npm run lint`, `npm test` (**19 passed**, 5 new) and `npm run build` all clean |
| Backend | No backend change; the pages use existing endpoints (`/imports`, `/scoring/run`, `/users`) |
| Click-through | Against the 200,000-row PaySim dev database as an admin: upload a 4-row CSV with one bad row (3 inserted, 1 rejected with "amount: Input should be greater than 0" on line 5), upload it again (0 inserted, 3 duplicates), score the new rows, create a user, change their role, deactivate them, reset their password, and see `import.completed` and `user.updated` in the audit log. No console errors or failed API calls |

## Complete

- **Imports page** (`/imports`, every role can see it): senior analysts and admins upload a PaySim-format
  CSV. The result shows rows read, inserted, duplicates skipped and rejected, with each rejected
  row's line number and problem. Files over 50 MB are refused in the browser before uploading.
  The history lists every import with its file hash; "Show problems" opens an import's rejected rows.
  A "Score next 5,000" button scores the new transactions with the active model.
- **Users page** (`/users`, admins only): create a user with a role and an initial password
  (12+ characters), change roles, deactivate and reactivate, and reset passwords. The page will not
  let admins change their own role or deactivate themselves (the API refuses it too). Every change
  is in the audit log.
- Navigation shows Imports to everyone and Users to admins.
- `npm run screenshots` now also captures the two pages (12-imports, 13-users).

## Incomplete

- Everything else in [docs/LIMITATIONS.md](../LIMITATIONS.md).
