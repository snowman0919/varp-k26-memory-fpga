# Toolchain contract

The lock file is `configs/toolchains/versions.json`. `make doctor` probes the
current host and writes a non-versioned report to `build/doctor/`; no absolute
host path is committed.

| Capability | Required for | Missing-tool consequence |
|---|---|---|
| Python 3.11 and `requirements.txt` | model, evidence, publication | target fails |
| Java 21, sbt, SpinalHDL, Verilator | RTL tests | RTL evidence cannot be regenerated |
| KiCad 9 CLI | native proposal gate | ERC/limited DRC cannot be regenerated |
| Pandoc, Chromium, Poppler | paper PDFs | canonical paper source remains readable |
| ffmpeg and Noto CJK fonts | animations/presentation | publication package incomplete |
| Vivado, device files, license | physical FPGA implementation | synthesis, P&R, timing, MIG, power remain blocked |
| DRAMsim3 adapter | coupled memory timing | absent from the public repository |

Tool availability proves only that a command was observed. It does not prove
design compatibility, successful model execution, timing closure, measured
power, or fabrication readiness.
