# FILE INDEX — Jangan baca file, baca ini dulu

## Project SMC
- `smc_core.py` (170 baris) — Engine: API rotation 4 key, market structure, OB, FVG, liquidity, 5 layer scoring
- `smc_scanner.py` (260 baris) — Scanner: 6 pair + synthetic DXY, confluence ranking, strategy entry
- `smc_run.py` (110 baris) — Runner: single pair analysis + formatted report
- `smc_analysis.py` (280 baris) — XAUUSD analysis lama (deprecated, pakai smc_scanner)

## Project Sovereign Bot
- `config.py` (63 baris) — Env loader: semua API keys + settings dari .env
- `tools.py` (307 baris) — Tool schema + dispatcher: bash_exec, read_file, write_file, dll
- `providers.py` (354 baris) — LLM provider: Groq/Claude/OpenAI/Mimo, retry + streaming

## Utility
- `gold_price.py` — Cek harga XAUUSD sekali jalan
- `gold_ws.py` — WebSocket real-time XAUUSD streaming
- `SMC_ROADMAP.md` — Todo list project

## Analysis
- `analysis/USDJPY_20260707.md` — USD/JPY full analysis
- `analysis/MULTI_PAIR_20260707.md` — Multi-pair ranking

## API Keys (Twelve Data)
- Key 1: `...bcfb5eee` ✅
- Key 2: `...848a628d` ✅
- Key 3: `...d178b9f7` ✅
- Key 4: `...f25433e3` ✅

## Pair List
XAU/USD, EUR/USD, GBP/USD, USD/JPY, USD/CAD, USD/CHF
