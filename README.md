# Shopping Sessions (Databricks), Builders Buildathon

The scorer builds the `Dockerfile` at the top of this repo. It's a Rust pipeline that turns the raw click-stream into the two exact daily tables.

- **Build:** offline, from vendored crates (`vendor/`, `.cargo/config.toml`). No network needed.
- **Run:** reads `$DATA_DIR`, writes Parquet to `$OUTPUT_DIR/user_daily/` and `$OUTPUT_DIR/campaign_daily/`, and uses `$NCPU` threads.
- **How it works:**
  1. Reads files in parallel and parses them with hand-written parsers that follow `rules.md` exactly.
  2. Hash-shards events by `event_id` for dedup.
  3. Shards events and clicks by person (union-find over linked IDs).
  4. Sessionizes and attributes each person's events, using a sliding 7-day click window.
  5. Writes Parquet with a minimal writer (`src/pq.rs`).
- **Correctness:**
  - It passes all 36 official fixtures and matches the published 1M-event dev answer exactly.
  - It also matches `shopping-tools/reference.py`, a separate slow Python reference written straight from the rules, on generated seeds.
- `shopping-tools/` isn't part of the image.
