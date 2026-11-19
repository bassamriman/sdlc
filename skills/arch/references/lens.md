# Architecture lens (18 questions)

D = answerable from the diff and the code. S = needs system context (dashboards, capacity, runbooks, tenancy). State first the number the change is held to (p99, RPS, durability, consistency window) and the trade-off as `chose X, gave up Y, because Z`; no number, no verdict. Under a timebox or for a small diff, take the D questions the change touches; the S ones are follow-ups.

1. D Failure mode of each dependency: down, slow, wrong. What degrades, what fails closed? Name the isolation: deadline, circuit breaker, bulkhead, cached fallback, explicit degraded mode.
   Why: every outage is a dependency doing one of three things; a design that names its answer for each is the one that stays up.
2. D Which operations are retried and are they idempotent? Key scoped per caller and operation, stored with the response under a unique constraint (never check-then-insert); same key with a different payload rejected; concurrent duplicate waits or gets 409; bounded retention; a local commit before each external mutation so a retry resumes rather than restarts.
   Why: retries are how distributed systems survive, and a retry without idempotency is how money moves twice.
3. D What ordering is assumed (per key, global)? What breaks on reorder, duplicate or replay? What is the partition key?
   Why: queues and networks promise order per key at best; code that silently assumes more corrupts state when the assumption fails.
4. D Consistency per read and write: what can be stale, for how long, who observes it? Dual write (DB plus queue): is it an outbox? Two writers on one row: version check, `SELECT FOR UPDATE` or serializable; a stale worker is rejected by a fencing token, never merged.
   Why: a write to two places without a transaction will diverge on the first crash between them; two writers without a check lose updates.
5. D Every network call has a deadline; is the budget propagated? Retries bounded by a budget (about 10 percent of traffic) with jittered backoff.
   Why: a call with no deadline holds a thread forever; retries at every layer multiply into a storm that finishes off a struggling dependency.
6. D Backpressure and limits: bounded queues, load shedding, admission control; caps on payload, batch and fan-out size; the dependencies' own quotas at 2x and 10x load; at the limit answer 429 with Retry-After, never a timeout.
   Why: an unbounded queue turns overload into memory exhaustion; a clear rejection lets callers back off, a timeout makes them retry.
7. D Fan-out amplification: N parallel calls at p99 give `1-(0.99)^N` slow requests. Hedge, timeout or partial result?
   Why: ten parallel calls each slow 1 percent of the time make the request slow 10 percent of the time; tails compound.
8. D N+1 and chatty calls: round trips per request, and does that grow with data size?
   Why: latency is round trips times network time; a loop that queries per item is fast in tests and slow in production.
9. D Hot keys and partitions: skew, and what happens when one shard is slow.
   Why: a single hot account or tenant lands on one shard, and the whole system runs at that shard's speed.
10. D Data growth at 1x, 10x, 100x: indexes, retention per table and topic, archival, unbounded tables; where sensitive data lives and its erasure path.
   Why: tables only grow; a query that is fine today without an index or a retention rule becomes the incident next year.
11. D when the diff has a migration or changes an API or event shape, else S. Expand/contract, both code versions read both shapes, rollback that still works after new-shape writes; released responses and events are additive-only (never remove, rename or retype a field, change a default or reuse a number); deprecate, then delete a release later.
   Why: deploys are not atomic; old and new code run together, and clients you do not control keep the old shape.
12. S Observability and SLO: the target and error budget per endpoint (D: state it); RED metrics, p50/p99 per dependency, trace propagation, burn-rate alerts on symptoms. How is silent divergence detected?
   Why: what is not measured per dependency cannot be debugged at 3 am, and a system can be wrong for weeks without being down.
13. D Authz at the handler for every write, object-level (whose record is this?); no secrets, PII or card data in logs, errors, idempotency keys, URLs or traces; card data only as tokens. S: tenant isolation, confused deputy.
   Why: authentication says who you are; the common breach is a valid user reaching someone else's record, or a secret copied into a log.
14. D Cost: cost per request at scale, dominant driver, the cheaper design that meets the SLO.
   Why: the design that meets the target at a tenth of the cost is the better design; the dominant driver is usually visible in the code shape.
15. S Reversibility and blast radius: flag or canary with the abort metric agreed in advance, a kill switch, old and new serving at once; single points of failure, cell isolation, runbook, on-call; recovery paths exercised (dependency failure injected, rollback and restore rehearsed), not assumed.
   Why: the question is not whether the change can fail but how far the failure reaches and how fast it is undone; an untested rollback is a hope.
16. D Money and state records: each movement is one atomic set of entries with debits equal to credits; ledger, payment and audit rows append-only with actor, cause and idempotency key (corrections are reversing rows, never UPDATE or DELETE); pending vs posted explicit; balances derived or written with a version check; event instants kept apart from business dates, cut-offs name their zone.
   Why: an append-only record that always balances can be audited and replayed; an updated row loses the history that explains the balance.
17. D Multi-step writes across services: one owner of the workflow state (an explicit state machine), a compensating action per committed step, one writer per record, no distributed transaction; for each side effect name the authoritative external record (bank, PSP, network file) and advance state only on confirmation against it. S: what later reconciles the two, and who owns a break.
   Why: a workflow that spans services will be interrupted midway; only an explicit state and a way back from each step make that survivable.
18. D Poison messages: retry cap then dead-letter with the original payload and cause, a named owner who drains it, replay and backfill through the same idempotent path, rate-limited so a backfill cannot starve live traffic.
   Why: one bad message retried forever blocks everything behind it; a dead-letter nobody owns is a silent data loss.

## By property
- Correctness (the right result under failure, retry and concurrency): 1, 2, 3, 5, 17, 18.
- Consistency (what is observed, when, by whom): 4, 9, 11, 16.
- Integrity (money and records provably whole): 2, 4, 13, 16, 17.
- Operability (seen, limited, reversible): 6, 7, 8, 10, 12, 14, 15.

Database detail (isolation anomalies, locks, constraints, indexes, online migrations) is in `db.md`.

For a data-modification endpoint always ask 2, 3, 4 and 13 first; add 16 when a balance or transfer is touched, 17 when the write has an external side effect, 18 for any queue consumer.
