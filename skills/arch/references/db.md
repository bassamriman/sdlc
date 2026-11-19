# Database lens (16 questions)

D = answerable from the diff (models, migrations, queries, transaction blocks). S = needs the real database (plans, sizes, settings). Short pass: 1, 2, 4, 6, 9, 11.

1. D Transaction boundaries: every multi-row or multi-table write in one transaction; no network call, queue publish or sleep inside it; short and bounded.
   Why: a write split across transactions leaves half a change on failure; a slow call inside one holds locks and connections for everyone else.
2. D Isolation: which anomaly can this code hit? Lost update (read, modify, write back), write skew (two rows checked, one written), phantom (count or range then insert). Fix with a version check, `SELECT ... FOR UPDATE`, a constraint, or serializable plus retry.
   Why: the default isolation level (read committed) prevents dirty reads only; the classic money bugs are lost updates that pass every single-user test.
3. D Locks: what rows or tables each transaction locks, in what order; two code paths locking the same rows in different orders deadlock. Lock timeout set; `SKIP LOCKED` for work queues.
   Why: deadlocks and lock waits appear only under concurrency, as random slow requests and aborted transactions.
4. D Integrity lives in the database: `NOT NULL`, unique, check and foreign-key constraints for every invariant the app relies on; the app check is a friendly error, the constraint is the guarantee.
   Why: two concurrent requests both pass an app-level "does it exist?" check; only a constraint stops the duplicate.
5. D Foreign keys: every reference is one, its delete rule is chosen on purpose (restrict, cascade, set null), and it is indexed.
   Why: an unindexed foreign key makes every parent delete scan the child table; an accidental cascade deletes history.
6. D Indexes: every filter, join and order-by column on a hot path is indexed; composite indexes ordered by equality columns first, then range or sort; partial indexes for skewed predicates; no new index on a write-heavy table without a reader.
   Why: a missing index is invisible on test data and a full scan at production size; every index also slows every write.
7. D Query shape: no query in a loop (N+1), aggregation and filtering in SQL not in app memory, keyset pagination with a deterministic order (`ORDER BY created_at, id`), bounded result sets.
   Why: app-side filtering loads every row; OFFSET pagination gets slower per page and skips or repeats rows when data changes.
8. D Migrations are online: no table rewrite or long lock on a large table (add nullable columns, then backfill, then constrain); indexes built concurrently; constraints added `NOT VALID` then validated.
   Why: a migration that locks a hot table for minutes is an outage that happens during the deploy, with nobody looking at errors.
9. D Migrations are reversible and expand/contract: old and new code both work during the deploy; schema changes and data backfills are separate steps; a rollback works after new-shape rows exist.
   Why: deploys are not atomic, and the rollback you never ran is the one that fails when you need it.
10. D Backfills: batched, idempotent, resumable, rate-limited, outside the schema migration.
   Why: one giant UPDATE holds locks, bloats the log and cannot be stopped halfway safely.
11. D Retries: serialization failures and deadlocks are retried with the whole transaction, a bounded number of times; non-idempotent side effects are not repeated by the retry.
   Why: serializable isolation and lock conflicts are expected to abort transactions; code that does not retry turns them into user errors.
12. D Idempotent writes: inserts keyed by a natural or idempotency key with a unique constraint; `INSERT ... ON CONFLICT` (upsert) instead of check-then-insert.
   Why: retries, double clicks and redelivered messages all write twice unless the database refuses the second one.
13. D Types: money as integer minor units or `NUMERIC`, never float; timestamps with time zone stored in UTC; enums constrained; soft delete only with a filtered unique index and a reason.
   Why: wrong types corrupt data silently: rounded cents, shifted times, duplicate "deleted" rows.
14. S Read replicas and caches: reads that must see the caller's own write go to the primary; replica lag is measured.
   Why: a user who saves and refreshes onto a lagging replica sees their change disappear.
15. S Connections: pool sized to the database's limit across all instances; no transaction left open across requests; statement timeouts set.
   Why: connection exhaustion takes every endpoint down at once, including the ones that never touch the slow query.
16. S Plans and growth: `EXPLAIN ANALYZE` on the new queries at production-like size; table and index growth; vacuum or compaction load from heavy update or delete.
   Why: the planner's choice changes with data size; a plan that is fine at ten thousand rows is a sequential scan at ten million.

For a write path always ask 1, 2, 4 and 12; add 8 and 9 for any migration, 6 and 7 for any new query.
