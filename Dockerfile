# Shopping Sessions: fast exact pipeline (Rust). Scorers are linux/amd64 Intel Xeon (AVX-512).
FROM rust:1.90-slim-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY .cargo ./.cargo
COPY vendor ./vendor
# Target the scorer's Cascade Lake+ CPUs.
ENV RUSTFLAGS="-C target-cpu=cascadelake"
RUN cargo build --release --locked --offline && strip target/release/sessions

FROM debian:bookworm-slim
RUN useradd --uid 1000 --no-create-home --home-dir /scratch app
COPY --from=build /src/target/release/sessions /app/sessions
USER 1000
CMD ["/app/sessions"]
