# Standalone djulia — design sketch (deferred)

Status: **design only, not built.** Core + tests come first. This captures the
"point djulia at an existing database and get a customized JSON:API" vision so it
isn't lost in chat.

## Two identities

1. **Django plugin** (what exists today): you have models, you `register()` them,
   you get a JSON:API. Robust, spec-compliant, this is cheap-core.
2. **Standalone DB→API tool**: point at an existing database and get to ~80% of a
   working, customizable API with a minimum of code — without really "thinking
   about Django." The `inspectdb`/introspection path.

The "80%" is not hand-wavy: it maps almost exactly onto Django's `inspectdb`,
which reads a schema but can't infer the last 20% (ambiguous/enum types, M2M
join-table intent, and — critically — *who is allowed to see what*).

## The config model: layered, deltas-only

The `Resource` class is already the per-model config interface. Effective config
resolves in layers, exactly like Django admin:

```
introspected defaults  ←  file/config overrides (deltas only)  ←  Resource subclass (for behavior)
```

- Bare `register_app("legacy")` → every model exposed with defaults, zero files.
- Overrides express *only* what differs (hidden columns, restricted filters/sort,
  perms). Defaults are always computed from `_meta` at runtime, so schema
  additions appear automatically.
- Drop to a full `Resource` subclass only when you need Python behavior
  (`get_queryset` joins, computed fields).

A future `register(Model, **overrides)` kwarg form lets deltas live as one-liners
without writing a class.

## The three rungs (a ladder, not rival modes)

| Rung | Models | Config surface | Best for |
|---|---|---|---|
| **1. Full ephemeral** | in-memory (introspected at boot) | none | instant demo; raw DB, no policy |
| **2. Ephemeral + config file** | in-memory | one generated, editable config file (deltas) | the standalone default — customized API, minimal code, no Django |
| **3. Materialized (eject)** | `inspectdb` files on disk | Resource classes / kwargs | full Python control, willing to maintain |

Natural progression: start at 1, `scaffold-config` → 2, `eject` → 3. Each step
trades auto-sync for control.

### Rung 2 detail — ephemeral models, persistent config (the "middle ground")

Introspect the DB and build models *transiently, just long enough to enumerate*
what's there, then emit a declarative config — **no `models.py`, no Resource
classes** — with everything as commented options:

```python
# djulia_config.py  (generated; uncomment/edit the bits you want)
DJULIA_RESOURCES = {
    "customers": {
        # "fields": ["name", "email"],       # otherwise all columns
        # "hidden": ["internal_notes"],
        # "filterset_fields": ["name", "status"],
        # "ordering_fields": ["created"],
        # "perms": "staff_only",
    },
    "orders": {
        # "hidden": ["cost_basis"],
    },
}
```

At `serve` time: introspect → build ephemeral models → apply this dict → serve.
You write *policy*, never structure. This is the best default for the target user
("I have a DB, I want a customized JSON:API, I'm not writing Django").

**Drift:** structure changes flow through automatically (models are live). The
config's *references* can still drift (hide a column that later gets renamed).
Mitigation — and an improvement over materialized files, which desync silently:
**validate the config against the introspected schema at boot** and fail/warn on
references to fields that no longer exist.

**Ceiling:** a config dict covers ~80% of overrides (hide, restrict filters/sort,
common perms). Custom `get_queryset` joins or computed fields need code — that
ceiling *is* the eject trigger. Rung 2 and rung 3 aren't competitors; eject is the
pressure valve.

## Ephemeral mechanism (rungs 1–2)

Django classes are runtime objects, so no files are required:

1. One placeholder app (`djulia.dynamic`) in `INSTALLED_APPS` to host the models.
2. Introspect via `connection.introspection` (the same API `inspectdb` uses:
   `get_table_list`, `get_table_description`, `get_relations`, `data_types_reverse`)
   — no need to shell out to `inspectdb` or generate text.
3. Build models with `type("Customer", (models.Model,), {... "Meta": Meta(app_label="djulia_dynamic", managed=False, db_table="customers"), "__module__": "djulia.dynamic"})`.
   Two passes: shells first, then wire FK/M2M.
4. `apps.clear_cache()`, then `register_app("djulia_dynamic")` — the **existing**
   registry produces views + filters + urls; the only new work is the models.
5. `clear_url_caches()`, then serve. Process ends → everything is gone.

This whole sequence is what a `djulia serve <db-url>` CLI would do with a
synthesized settings module it never writes to disk. The CLI *is* the mechanism.

### Honest hard parts

- **App-registry timing.** The registry is effectively frozen after
  `apps.populate()`. Injecting models afterward works but is lightly-supported and
  the most version-fragile piece; do it at bootstrap and clear caches.
- **Relations / M2M heuristics.** Two-pass wiring + detecting join tables
  (two FKs, little else) — `inspectdb`'s classic weak spot.
- **The 20%:** PK-less tables, odd/enum types, DB views. Silver lining: Django 6.1
  has `CompositePrimaryKey`, so composite keys — historically the dealbreaker —
  are now modelable.
- **Cost:** every worker / `runserver` reload re-introspects at boot.

## PostgREST comparison & positioning

This is essentially PostgREST's model (introspect-at-startup, in-memory,
DB-derived, no codegen). The key difference is *where policy lives*:

- **PostgREST** pushes policy into the database — roles + Row-Level Security for
  authz, views + `GRANT` for column shaping, SQL functions for computed/RPC. That's
  why it can be near config-free, but it's Postgres-only and bypasses the Django
  ecosystem.
- **djulia** keeps policy in **Python** (`has_permission`/`get_queryset`, Django
  auth) — portable across backends, familiar, and the deltas live in the rung-2
  config file. (DB-side RLS remains an option for Postgres users who want it.)

**Positioning:** *PostgREST for the Django + JSON:API world* — ephemeral
introspection, but Python-native policy, real JSON:API output (PostgREST has its
own REST dialect), multi-backend, and an eject-to-files hatch.

**Honest limitation:** PostgREST does live schema reload (`LISTEN/NOTIFY` /
`SIGUSR1`). djulia can't match that cheaply because Django's app registry isn't
built to hot-swap models — so standalone djulia is **re-introspect-at-boot /
restart-to-refresh**, not zero-downtime schema evolution. That's the cost of
riding Django instead of a bespoke server.

## Perms are the gate

Exposing a whole DB as CRUD is powerful and dangerous. Whatever rung, the
`Resource.has_permission` / `Resource.get_queryset` seams (or DB-side RLS) are the
thing to wire before pointing this at real data.
