# Alert Lifecycle & Persistence Design

**Status:** Approved design, implemented in Task 21b
**Applies to:** `src/database/alert_dao.py`, `alerts` table schema (Task 3, extended here)

---

## The Problem

`AlertEngine` (Task 20) decides *whether* a property's risk crosses a threshold, and
`Notifier` (Task 21) formats that decision for console/log output. Neither persists
alerts anywhere queryable, and neither has any concept of an alert's lifecycle over
time. Three concrete gaps this creates:

1. **No memory across cycles.** If the continuous monitoring loop (Task 23-24)
   re-evaluates every 5 minutes and a property stays critical for hours, a naive
   implementation would re-notify every single cycle - spamming any future delivery
   channel (email, dashboard) with dozens of duplicate notifications for the same
   ongoing condition.
2. **No way to know when danger has passed.** A risk score dropping back down is
   currently indistinguishable from a risk score that was never elevated - nothing
   marks an alert as resolved.
3. **No way to know when an alert can no longer be trusted.** If ingestion or
   scoring stalls, an alert raised hours ago would still read as "active" even
   though nothing has confirmed the underlying condition is still true.

---

## The Alert Lifecycle

```
                    +-------------+
   condition first  |             |  human acknowledges it
   crosses threshold|   ACTIVE    |------------------+
   ----------------->  (new)      |                  v
                    |             |           +--------------+
                    +------+------+           | ACKNOWLEDGED |
                           |                  +------+-------+
              re-evaluated | every cycle             |
              (still bad)  |                         | still re-evaluated
                           v                         v
                    +-------------+          (same checks apply,
                    |   ACTIVE    |           but notification stays
                    |  (ongoing)  |<----------quiet unless it escalates)
                    +------+------+
                           |
        +------------------+-------------------+
        |                  |                   |
   no fresh data      score dropped       score dropped
   for too long        a little          well below threshold
        v                  v                   v
  +-----------+    (stays ACTIVE,        +-----------+
  |   STALE   |     message says         | RESOLVED  |
  +-----------+     "improving,          +-----------+
                     not resolved")      lifecycle complete
```

### States

| Status | Meaning | Set by |
|---|---|---|
| `active` | Currently triggered, not yet acknowledged, condition confirmed by a recent assessment | `AlertDAO` on first trigger, or re-affirmed each cycle |
| `acknowledged` | A human has seen it and is handling it | Future consumer (dashboard/API) calling `acknowledge_alert()` |
| `stale` | No fresh risk assessment for this property within `stale_after_hours` - can no longer confirm the condition still holds | `AlertDAO` during re-evaluation, based on assessment recency |
| `resolved` | Score has dropped below the trigger threshold minus a hysteresis buffer, on a fresh assessment | `AlertDAO` during re-evaluation |

### Transition Rules

1. **New alert:** `AlertEngine` produces a trigger for a property/risk_type with no
   existing `active`/`acknowledged`/`stale` row -> `AlertDAO` inserts a new `active` row.
2. **Ongoing (same condition persists):** an `active` or `acknowledged` row already
   exists for this property/risk_type -> update its `risk_score`/message rather than
   inserting a duplicate row. Re-notify only if `renotify_interval_minutes` has
   elapsed since the last notification (see Config below), or if it escalates to a
   materially higher score even within the cooldown window.
3. **Improving, not resolved:** current score has dropped since the last
   notification but is still above `(trigger_threshold - resolution_hysteresis)` ->
   stays `active`, message explicitly says "decreasing but still elevated."
4. **Resolved:** current score is below `(trigger_threshold - resolution_hysteresis)`
   on a fresh assessment -> status becomes `resolved`, `resolved_at` is set, the
   alert's lifecycle is complete. A future trigger for the same property/risk_type
   starts a brand-new alert (new row), not a reopening of the resolved one - this
   preserves history cleanly.
5. **Stale:** the property's most recent risk assessment is older than
   `stale_after_hours` -> status becomes `stale` regardless of what the last known
   score was. If a fresh assessment arrives later, the alert is re-evaluated from
   scratch against rules 2-4 (it does not automatically revert to `active`).

### Why Hysteresis Matters

Without a buffer, a score oscillating right at the threshold (70.1, 69.9, 70.2...)
would flap open/closed every cycle, generating a resolved notification followed
immediately by a new-alert notification, repeatedly. Requiring the score to drop
meaningfully below the original trigger point before counting as resolved (the same
principle a thermostat uses) prevents this.

---

## Configuration

New parameters under `config/settings.json` -> `alerts`:

| Parameter | Default | Purpose |
|---|---|---|
| `renotify_interval_minutes` | 60 | Minimum gap between repeat notifications for an ongoing, unacknowledged alert |
| `resolution_hysteresis` | 10 | Points below the trigger threshold the score must fall to count as resolved |
| `stale_after_hours` | 6 | No fresh reassessment within this window -> mark `stale` |

All three follow the same config-driven principle applied to every threshold in this
project since Task 5 - tunable without code changes.

---

## Schema Change: Extending the `alerts` Table

Task 3's original `alerts` schema has `acknowledged_at` (nullable) but no way to
represent "the system determined this is resolved" versus "the system can no longer
confirm this is still true" - both are distinct facts from "a human looked at it."

**Additive change (no breaking migration needed):**

```sql
ALTER TABLE alerts ADD COLUMN status TEXT
  CHECK (status IN ('active', 'acknowledged', 'stale', 'resolved')) DEFAULT 'active';
ALTER TABLE alerts ADD COLUMN resolved_at TIMESTAMP;
ALTER TABLE alerts ADD COLUMN last_notified_at TIMESTAMP;
```

`last_notified_at` tracks when this alert was last actually sent to a notification
channel, independent of when the underlying row was last updated - this is what the
re-notification cooldown check compares against.

Every status transition is also recorded as a new row in `alert_history` (Task 3,
previously unused) - `old_status`, `new_status`, `timestamp` - giving a full audit
trail of an alert's life, not just its current state.

---

## Division of Responsibility (Unchanged Design, Now Extended)

| Component | Responsibility | Status |
|---|---|---|
| `AlertEngine` | Decide *if* a threshold is crossed (pure logic, no state) | Built (Task 20) |
| `AlertDAO` | Make it durable, deduplicated, lifecycle-aware, queryable | New (Task 21b) |
| `Notifier` | Format for a channel (console/log today; email/dashboard later) | Built (Task 21), unchanged |

**Why this still avoids future redesign:** a future delivery channel (email,
dashboard, Slack) only ever needs to call `AlertDAO.get_active_alerts()` (or
`get_alerts_for_property()`) and `AlertDAO.acknowledge_alert()`. Neither
`AlertEngine` nor `Notifier` need to change when that channel is built - the
lifecycle and deduplication logic already lives in one place.

---

## Portfolio-Level Alerts (Task 27 Extension)

**Status:** Approved design, implemented in Task 27
**Applies to:** `src/alerts/alert_engine.py`, `src/database/alert_dao.py`, `alerts` table schema

### The Problem

`AlertEngine`/`AlertDAO` as built in Tasks 20-21b only ever reason about a single
property's risk. The project's stated goal also includes catching *accumulation*
risk - too many properties elevated at once, even if no single one is worse than
usual (`portfolio_threshold_percent`, already in config since Task 5, unused until
now). This needed its own trigger condition, but explicitly **not** its own
lifecycle system - the state machine above (active -> acknowledged/stale ->
resolved, hysteresis, re-notification cooldown) applies exactly as-is; only what
counts as "the condition" changes.

### Design Decision: One Alerting System, Not Two

Rather than build a parallel portfolio-alert table/DAO, a portfolio-level alert is
persisted through the *same* `AlertDAO` and `alerts` table as property-level
alerts, using:

- `property_id = NULL` - a portfolio alert isn't about any one property
- `risk_type = 'portfolio_high_risk_pct'` - a reserved risk_type value that all the
  existing dedup/lifecycle logic keys on exactly like `'wildfire'`/`'flood'` do

**Who closes it?** Nobody manually, same answer as property alerts: the continuous
monitoring loop (`Monitor`, Task 23) recomputes the portfolio's high/critical
percentage every cycle via `PortfolioAggregator` (Task 25) and re-evaluates the
alert's lifecycle automatically. It resolves itself once the percentage drops
meaningfully below the threshold (hysteresis), goes stale if the portfolio hasn't
been reassessed recently, and can be acknowledged by a human via the same
`acknowledge_alert()` - there is no separate "who closes a portfolio alert"
mechanism to build.

### Schema Change: `property_id` Must Become Nullable

Unlike Task 21b's additive `ALTER TABLE ADD COLUMN` migration, this one is not
additive - `alerts.property_id` is `INTEGER NOT NULL` in the original schema
(Task 3), and SQLite has no `ALTER TABLE ... ALTER COLUMN` to drop a `NOT NULL`
constraint. The migration rebuilds the table:

```sql
CREATE TABLE alerts_new ( ... same schema, property_id INTEGER (nullable) ... );
INSERT INTO alerts_new SELECT * FROM alerts;
DROP TABLE alerts;
ALTER TABLE alerts_new RENAME TO alerts;
```

Done idempotently in `AlertDAO._ensure_schema()` (checked via
`PRAGMA table_info(alerts)`'s `notnull` flag on `property_id`, exactly like the
existing `status`/`resolved_at`/`last_notified_at` idempotency checks), with row
counts verified to match before and after.

**A sentinel value (e.g. `property_id = 0`) was considered and rejected.** It
would only "work" because this database never enables `PRAGMA foreign_keys`, so
the declared foreign key to `properties(property_id)` is currently unenforced - a
sentinel would be relying on that staying true, and would misrepresent the data to
anyone reading the table directly (a `0` that isn't a real property). `NULL` is
the honest representation of "this alert has no single property."

**A secondary fix this requires:** SQL's `column = ?` never matches when the bound
parameter is `NULL` (`NULL = NULL` is `NULL`, not `TRUE`, in SQL). Every
`property_id = ?` comparison inside `AlertDAO` (the dedup lookup in
`save_new_alerts()`, and the lookup in `evaluate_lifecycle()`) is changed to
`property_id IS ?`, which is SQLite's null-safe equality - behaves identically to
`=` for non-null values, and correctly matches `NULL` to `NULL` for portfolio
alerts.

### Configuration

Reuses `renotify_interval_minutes` and `stale_after_hours` from the existing
`alerts` config section (Task 21b) - same cadence reasoning applies whether the
condition is one property's score or the whole portfolio's percentage. Two new
parameters:

| Parameter | Default | Purpose |
|---|---|---|
| `portfolio_threshold_percent` | 10 | Already existed (Task 5, unused until now) - percentage of assessed properties in high/critical that triggers the alert |
| `portfolio_resolution_hysteresis_percent` | 2 | Percentage points below the threshold the figure must fall to count as resolved (e.g. threshold 10% -> resolves below 8%) |

A separate, smaller hysteresis value than the property-level `resolution_hysteresis`
(10 points) is used deliberately - `10 - 10 = 0%` would make the property-level
value degenerate for a percentage-based condition (nothing short of a 0%
high/critical portfolio would ever resolve it).

### Alert Level

Always `critical` - unlike property-level alerts (which independently flag a
`warning` for a sudden increase and a `critical` for crossing the absolute
threshold), a portfolio accumulation breach is inherently the more severe signal
regardless of how far past the threshold it is; there is no second, softer
condition to independently track here.

---

## Related Documentation

- [task-breakdown.md](task-breakdown.md) - Task 21b full spec
- [implementation-plan.md](implementation-plan.md) - Section 6 (Alert Thresholds)
- [reference-principles.md](reference-principles.md) - Principle 5 (Actionable Alerts Over Noise), Principle 10 (Data Quality as a First-Class Concern)
