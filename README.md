# SOVEREIGN Agent

Autonomous agent: kasih task pakai bahasa natural, dia yang cari tau caranya —
install dependency, tulis file, jalanin & debug sendiri, baru konfirmasi kalau selesai.

## Setup di Termux

```bash
cd sovereign_agent
pip install --break-system-packages -r requirements.txt
cp .env.example .env
nano .env   # isi API key
```

Isi `.env`:
```
GROQ_API_KEY=gsk_xxx
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
TELEGRAM_BOT_TOKEN=xxx        # opsional, dari @BotFather
TELEGRAM_ALLOWED_CHAT_ID=xxx  # chat_id lo, dari @userinfobot
DEFAULT_PROVIDER=groq
```

## Pakai via CLI

```bash
python cli.py "buatkan script python cek harga BTC dari API publik" --auto
python cli.py "install ta-lib dan bikin indikator RSI sederhana" --provider claude
```

Default mode = `--confirm` (nanya dulu sebelum bash_exec/install/write_file).
Pakai `--auto` untuk full otomatis tanpa ditanya sama sekali.

## Pakai via Telegram

```bash
python telegram_bot.py
```

Lalu chat ke bot lo:
```
buatkan script cek harga BTC
/auto buatkan script cek harga BTC       -> mode auto
/provider claude bikinkan bot X          -> pilih provider sekali jalan
```

Kalau ada step risky, bot nanya balik di chat — balas `y`/`n`.

## Cara nambah provider baru

Tambah class di `providers.py` yang extend `BaseProvider`, implement `.chat(messages, tools)`,
lalu daftarin di `get_provider()`. Kalau API-nya OpenAI-compatible (kayak OpenRouter, DeepSeek,
Together, dll), tinggal reuse `OpenAICompatProvider` dengan base_url beda — gak perlu kode baru.

## Cara nambah tool baru

1. Tambah schema di `tools.py` -> `TOOLS_SCHEMA`
2. Implement fungsinya
3. Daftarin di `DISPATCH` dict
4. Kalau berbahaya (bisa ngerusak/boros resource), masukin ke `RISKY_TOOLS`

## Catatan keamanan

- Semua file operation dibatasi ke folder `workspace/` (gak bisa keluar via `../`)
- `bash_exec` TIDAK dibatasi — command shell apapun bisa dijalanin. Ini yang bikin agent
  powerful tapi juga risiko. Pakai mode `confirm` kalau kasih task ke sumber yang gak lo percaya
  penuh, atau kalau task-nya sensitif (hapus file, akses wallet/API trading beneran, dll).
- Jangan taro API key trading/exchange asli sebagai env var yang bisa dibaca `bash_exec`
  kalau agent lagi mode auto penuh — resikonya AI bisa "curious" jalanin sesuatu yang gak diminta.
