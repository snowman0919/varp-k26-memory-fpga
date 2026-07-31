# Analytical model versus RTL contract

The Python event model is a policy exploration tool; it is not a behavioral or
cycle-accurate reference for `TileScheduler`.

| Topic | Python analytical model | Current RTL |
|---|---|---|
| Home queue | explicit `TileJob.home_cluster` | `jobId % clusterCount` |
| S2/S3 victim choice | searches every eligible job in victim queues | inspects victim queue heads only, preserving per-queue FCFS |
| Locality cost | byte/service-dependent floating-point penalties | fixed integer channel, bundle, activation, and reduction penalties |
| Dispatch width | multiple idle clusters may dispatch at one event time | at most one job per clock edge |
| Compute rate | default abstract 64 MAC/cycle | 16×4 demo performs 64 MACs in 65 request-to-done cycles |
| Memory/link | analytical resource service and overlap assumptions | independent command/routing planes; no compute data return |

Consequences:

- Python S0–S3 rankings are candidate-policy evidence only.
- Python cycle counts are not predictions of RTL latency or throughput.
- Exact RTL equivalence requires a separate cycle-stepped reference model or a
  common trace contract; neither is claimed here.
- The current RTL tests establish bounded functionality and exact-once
  ownership, not analytical-result reproduction.
