//! Laudas — Rust port (scaffold)
//!
//! This is a placeholder. The Python implementation in ../laudas.py is
//! the reference; this crate exists to stake out the layout and to make
//! the Volume I (v1.0) target concrete.
//!
//! See ../rust/PORT_PLAN.md for the staged port from Python → Rust.

use std::env;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    eprintln!("laudas (rust port — not yet implemented)");
    eprintln!();
    eprintln!("This crate is a scaffold for the v1.0 Rust rewrite.");
    eprintln!("The working implementation is currently the Python prototype.");
    eprintln!();
    eprintln!("From this directory, use:");
    eprintln!("  python ../laudas.py {}", args.get(1).map_or("FILE.laud", String::as_str));
    eprintln!();
    eprintln!("Or install via pip and use the `laudas` command:");
    eprintln!("  pip install -e ..");
    eprintln!("  laudas FILE.laud");
    eprintln!();
    eprintln!("Port progress is tracked in PORT_PLAN.md.");
    ExitCode::from(64)
}
