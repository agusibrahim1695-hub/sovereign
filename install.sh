#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "🚀 SOVEREIGN Agent Installer"
echo "================================"

REPO_URL="https://github.com/agusibrahim1695-hub/sovereign.git"
TARGET_DIR="$HOME/sovereign_agent"

echo "[1/5] Update & install package dasar (python, git, termux-api)..."
yes | pkg update
yes | pkg install python git termux-api

echo "[2/5] Clone/update repo SOVEREIGN..."
if [ -d "$TARGET_DIR/.git" ]; then
    cd "$TARGET_DIR"
    git pull origin main
else
    git clone "$REPO_URL" "$TARGET_DIR"
    cd "$TARGET_DIR"
fi

echo "[3/5] Install library Python..."
pip install --break-system-packages -r requirements.txt
pip install --break-system-packages beautifulsoup4

echo "[4/5] Setup .env..."
if [ ! -f "$TARGET_DIR/.env" ]; then
    cp "$TARGET_DIR/.env.example" "$TARGET_DIR/.env"
    echo "    -> .env dibuat dari template (masih kosong, WAJIB diisi manual)"
else
    echo "    -> .env sudah ada, tidak ditimpa"
fi

echo "[5/5] Pasang command global SOVEREIGN..."
mkdir -p "$PREFIX/bin"
cat > "$PREFIX/bin/SOVEREIGN" << 'LAUNCHER'
#!/data/data/com.termux/files/usr/bin/bash
cd ~/sovereign_agent && python chat.py "$@"
LAUNCHER
chmod +x "$PREFIX/bin/SOVEREIGN"
cp "$PREFIX/bin/SOVEREIGN" "$PREFIX/bin/sovereign"
chmod +x "$PREFIX/bin/sovereign"

echo ""
echo "================================"
echo "✅ SOVEREIGN Agent terpasang di $TARGET_DIR"
echo ""
echo "LANGKAH TERAKHIR (wajib, manual demi keamanan):"
echo "  nano ~/sovereign_agent/.env"
echo "  -> isi GROQ_API_KEY / ANTHROPIC_API_KEY / MIMO_API_KEY dll"
echo ""
echo "Setelah .env diisi, jalankan:"
echo "  SOVEREIGN"
echo "================================"
