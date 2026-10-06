# Roadmap

What's next for djulia, kept in the repo so it changes alongside the code.

**How to use this file:** each item is a checkbox with a one-line reason. Move
items between sections as priorities change. When one is done, tick it, move it
to [Done](#done) with the date, and mention it in the commit that finishes it.
Bigger designs get their own doc (like [standalone.md](standalone.md)) and a
link from here.

## Now

- [ ] **Docs controls.** A setting to disable or protect `openapi.json` and
  `/docs/`, which are public whatever the permission policy. Optionally
  self-host the Swagger UI assets, which currently load from a CDN.
- [ ] **`?include=` (compound documents).** Return related records in the same
  response. The main JSON:API feature still missing.
- [ ] **Bound to-many linkage.** Every response lists *all* related ids (e.g.
  an author with 10,000 articles). Cap it, or offer links instead of linkage.
- [ ] **Python 3.10 end of life (October 2026).** Decide when to drop it from
  `requires-python`, tox and CI.

## Next

- [ ] **Relationship endpoints.** `/articles/1/relationships/tags` for reading
  and changing links on their own.
- [ ] **Richer OpenAPI.** Error responses (400/401/403/409/415/422), security
  schemes for token auth, and required fields on create.
- [ ] **`read_only_fields` on `Resource`.** Mark a field read-only without
  changing the model.
- [ ] **Reject unknown filters.** `?filter[...]` on a column that doesn't exist
  or is hidden is silently ignored, so a typo returns unfiltered results.
  Return `400` instead, as `?sort=` already does.
- [ ] **Policies can say "never".** Anonymous callers get `401` even when no one
  may perform the action; let a policy raise its own error so that's a `403`.
- [ ] **Startup checks.** Warn when `allow_all` is active, or when a model from
  `django.contrib.auth` is registered.
- [ ] **Full-text search.** e.g. `?filter[search]=...`.
- [ ] **JSON columns (`JSONField`, e.g. PostgreSQL `jsonb`).** Values serialize
  as nested JSON, but nothing tests that end to end yet. Known issues:
  - The OpenAPI schema calls them strings: `_attribute_schema` has no
    `JSONField` case and falls back to `{"type": "string"}`. They should be
    "any JSON value".
  - They're sortable by default like every column, though the order is rarely
    meaningful (and not all databases can order them). Probably exclude them
    from default sorting.
  - Default filters skip them, which seems right; decide whether any lookups
    (e.g. key containment) are worth offering.
  - Add a `JSONField` model to the test app.

## Later

- [ ] **Standalone mode.** Serve an existing database with no Django project;
  see [standalone.md](standalone.md).
- [ ] **`id_field` option.** Use a unique field other than the primary key as
  the public `id`, so sequential keys aren't exposed. Mainly for existing
  databases, where the primary key can't change; projects with their own
  models can use a UUID primary key instead. Where the conversions happen:
  - `serialization._ident`: read `obj.<id_field>` instead of `obj.pk`
    (related objects are already loaded, so no extra queries).
  - `views.existing_pks`: look up by the field
    (`in_bulk(ids, field_name=id_field)`) and return primary keys.
  - Single related records: look up the primary key first instead of setting
    `<name>_id` directly (one query, same as lists).
  - `get_object` and `apply_client_id`: look up by the field instead of `pk`.
  - Filtering by relationship (`?filter[author]=...`) currently uses primary
    keys via django-filter; make it accept public ids. The fiddliest part.
  - Also: the OpenAPI schema, and a startup check that the field is unique and
    non-null.
- [ ] **`model_perms` policy.** Writes need Django's `add_`/`change_`/`delete_`
  permissions, for Django-native projects.
- [ ] **CSRF for session cookies.** Enforce CSRF only for cookie-authenticated
  requests, for projects serving their own browser frontend.
- [ ] **Binary columns, opt-in.** Hidden by default today, and exposing one is an
  error (`djulia.E001`). Could serve them base64-encoded.
- [ ] **Configurable `WWW-Authenticate`.** It's always `Bearer` today.
- [ ] **`register(Model, **overrides)`.** One-line overrides without a subclass.
- [ ] **Client-id conflicts and hidden rows.** The "id already exists" check
  sees rows `get_queryset` hides, so a `409` can reveal that one exists.

## Housekeeping

- [ ] **License.** Choose one before announcing djulia or publishing it.
- [ ] **PyPI release.** Packaging metadata and a first published version.
- [ ] **`example/smoke.py` writes to the demo database.** Its docstring says it
  uses an in-memory database; make that true.

## Done

- [x] Hide binary and credential-like columns by default; `exclude`; filters and sorting cover visible columns only (2026-10-05)
- [x] Checked the CI run for the v7 action bump: all Pythons pass, 3.10 included (2026-10-05)
- [x] Pinned the CI runner to `ubuntu-24.04` and moved actions to v7 (2026-10-05)
- [x] tox matrix and GitHub Actions CI (2026-10-05)
- [x] Validated, transactional writes; read-only fields; client ids by primary key type (2026-10-05)
- [x] Pluggable identity and permission policies; writes off by default (2026-10-04)
- [x] Lenient JSON:API 1.1 content negotiation (2026-10-04)
- [x] `register_app` for bulk registration (2026-10-04)
