# Agent Quickstart (Short)

Use this for very fast orientation.

1. Run `python bot.py` after setting `DISCORD_TOKEN`.
2. Core modules:
   - commands: `noodswap/commands.py`
   - storage: `noodswap/storage.py`
   - views: `noodswap/views.py`
   - cards/catalog: `noodswap/cards.py`
3. All responses should be embeds:
   - general: `italy_embed`
   - marriage/divorce: `italy_marry_embed`
4. Inventory is **instance-based** with per-copy generations (`G-####`).
5. Validate with:
   - `/opt/homebrew/bin/python3.14 -m py_compile bot.py noodswap/*.py`

For full details, read `AGENTS.md` and `docs/README.md`.
