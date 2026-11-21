# Shopping Sessions: fast exact pipeline

Rust, single binary. Reads `$DATA_DIR` (default `/data`), writes `$OUTPUT_DIR/user_daily/` and `$OUTPUT_DIR/campaign_daily/` as Parquet, uses `$NCPU` threads. Logs stage timings to stderr.

How it works:
1. Every CSV is read into memory in parallel and cut into chunks on line boundaries.
2. Chunks are parsed in parallel by hand-written parsers that follow `rules.md` exactly: quoting, `\r` as data, ASCII-only digits, three timestamp forms with full calendar checks.
3. Events are sharded by `event_id` for dedup (smallest `ingest_ts`, before validation).
4. Surviving events and clicks are sharded by person (union-find over `links/`, named by the byte-wise smallest ID).
5. Each shard is sessionized and attributed independently, with a sliding 7-day click window per person.

Correctness: it passes all 36 fixtures and matches the published dev answer exactly. It also matches an independent Python reference implementation on generated seeds.
