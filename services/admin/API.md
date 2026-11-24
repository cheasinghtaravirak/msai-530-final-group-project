# Admin API

Who works for the company, where, and with what rights. Issues login tokens (design doc §4.1, §5.1, §6.2 S1, §6.3 E1).

Conventions from `docs/implementation-plan.md` §3 apply to every endpoint:

- Through the gateway the prefix is `/api/admin`. The service itself serves `/branches`, with no trailing slash.
- JSON is `snake_case`. Errors are `{"error": {"code": "...", "message": "...", "details": {}}}`.
- Writes are for `HQ_ADMIN`. A new role grant takes effect at the user's next login, when the token is issued.

| Method and path | Phase | Roles |
|---|---|---|
| `GET /health` | 1 (built) | none |
| `POST /auth/login`, `GET /auth/me` | 1 (built) | none, any |
| `GET /branches?status=` | 1 (built) | any staff; HQ sees all, others their own |
| `POST /branches`, `PATCH /branches/{branch_id}` | 1 (built) | HQ |
| `POST /branches/{branch_id}/close` | 2 (built) | HQ |
| `GET /users?q=`, `POST /users` | 2 (built) | HQ |
| `GET /users/{user_id}`, `PATCH /users/{user_id}` | 2 (built) | HQ |
| `POST /users/{user_id}/roles` | 2 (built) | HQ |
| `DELETE /users/{user_id}/roles/{grant_id}` | 2 (built) | HQ |

## Branches

A branch is `{"branch_id": "BR-01", "name", "address", "region", "timezone", "status", "opened_on"}`. `branch_id` is set on create and never changes. `PATCH` takes any of the other fields except `status`.

`timezone` is always the business time zone, `Asia/Phnom_Penh` (design doc §1 leaves multiple time zones out of scope). Any other value returns 400 `VALIDATION_ERROR`. The field stays in the branch and in `branch.upserted` because the contract names it.

`POST /branches/{branch_id}/close` sets `status` to `CLOSED`, revokes every active role grant on the branch, and returns the branch. Branches are never deleted.

Create, patch and close each publish `branch.upserted` with `branch_id, name, region, timezone, status`, keyed by `branch_id`.

## Users and role grants

A user is `{"user_id", "email", "full_name", "status", "roles", "created_at"}`, where `roles` lists the active grants `{"grant_id", "role_code", "branch_id", "granted_at"}`.

- `POST /users {"email", "full_name", "password"}` creates an `ACTIVE` user. Emails are stored lower-case and must be unique. Passwords have at least 8 characters.
- `PATCH /users/{id}` takes any of `full_name`, `status` (`ACTIVE` or `DISABLED`) and `password`. The email never changes.
- `POST /users/{id}/roles {"role_code": "CASHIER", "branch_id": "BR-01"}` grants a role. `BRANCH_MANAGER` and `CASHIER` need an open branch; `HQ_ADMIN` takes `branch_id: null`. Granting a role the user already holds returns the existing grant with 200 instead of 201, so the seed can re-run.
- `DELETE /users/{id}/roles/{grant_id}` revokes the grant (sets `revoked_at`) and returns 204.
