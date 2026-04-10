# BaseProjects Reference Notes

This document records how `BaseProjects/*` informed design decisions while preserving the rule that ProjectHearthApp is independent runtime code.

- Used Claw-style orchestration and lifecycle ideas, not Rust implementation.
- Used MemPalace-style memory taxonomy and local-first approach, not storage implementation.
- Used Gemma repo as target model runtime inspiration, not as app structure.
- Used MCP spec/reference servers for contract and tool ergonomics, not production server code.
