# ZERO Dev Container

This container is the no-install path for contributors and coding agents. It
installs Python, Rust, `just`, the editable `zero-engine` package, and the Rust
CLI dependency graph without requiring exchange credentials or cloud access.

After the container opens:

```bash
just demo
just paper-api-smoke
just public-proof
```

To inspect the paper API manually:

```bash
just paper-api
```

Then open a second terminal:

```bash
cd cli
cargo run -q -p zero -- --api http://127.0.0.1:8765 doctor
```
