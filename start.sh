#!/bin/bash

# --- 0. LM Studio AppImage GUI olarak çalıştır ---
APPIMAGE=/home/tm/Applications/LM-Studio-0.3.23-3-x64.AppImage
echo "LM-Studio GUI başlatılıyor..."
chmod +x "$APPIMAGE"
nohup "$APPIMAGE" --no-sandbox >/dev/null 2>&1 &

# --- 0.5. 5 saniye bekle ---
echo "LM Studio açılması için 5 saniye bekleniyor..."
sleep 5

# --- 1. LM Studio CLI yolu ---
LMS=/home/tm/.lmstudio/bin/lms

echo "Tüm LM Studio modelleri unload ediliyor..."
$LMS ps | grep 'Identifier:' | awk '{print $2}' | xargs -r -I {} $LMS unload {}

echo "OpenAI GPT-OSS-20B yükleniyor..."
$LMS load openai/gpt-oss-20b

# --- 2. Docker container'ını başlat ---
echo "Docker container başlatılıyor..."
sudo docker start ragdb

# --- 3. Conda environment'ı aktif et ---
echo "Conda environment aktif ediliyor..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate testenv

# --- 4. Uvicorn server'ı çalıştır ---
echo "Uvicorn server başlatılıyor..."
uvicorn main:app --reload --host 0.0.0.0 --port 8000

echo "Start script tamamlandı!"
