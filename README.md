# meeting-agent

本機會議轉錄 + Claude 摘要工具，專為 Apple Silicon 最佳化。輸出**繁體中文（台灣慣用語）**並同時產出 **Markdown + PDF**。

## 流程

```
audio (.m4a/.mp3/.mp4/.wav/...)
   │  ffmpeg → 16 kHz mono WAV
   │  mlx-whisper large-v3-turbo（M 系列 Metal 加速）
   │  OpenCC s2twp（簡→繁，台灣慣用語）
   ▼
outputs/<basename>/
   ├── transcript.md     繁體逐字稿（含時間戳）
   ├── transcript.pdf    A4 PDF（PingFang TC）
   └── segments.json
   │
   ▼  Claude Code /meeting 接手
   ├── summary.md        結構化會議摘要
   └── summary.pdf
```

中英混雜友善；轉錄與摘要皆本機處理。

## Setup（只跑一次）

```bash
# 系統依賴
brew install ffmpeg

# 取得程式碼
git clone https://github.com/changshoufeng0609-cmd/meeting-agent.git
cd meeting-agent

# Python 環境
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium       # PDF 渲染引擎（~180 MB，一次性）
```

首次轉錄會自動下載 `mlx-community/whisper-large-v3-turbo` 模型（~1.5 GB）。

## Manual usage

```bash
source .venv/bin/activate
python pipeline.py /path/to/meeting.m4a
```

若不需要 PDF 可加 `--no-pdf` 略過。

單獨把任意 Markdown 轉 PDF：

```bash
python render_pdf.py path/to/file.md
```

## Claude Code usage

repo 內附 `/meeting` slash command（`.claude/commands/meeting.md`），在 repo 根目錄開 Claude Code 即可使用：

```
/meeting /path/to/meeting.m4a
```

Claude 會：
1. 跑 `pipeline.py` → `outputs/<basename>/transcript.{md,pdf}`
2. 讀逐字稿
3. 產出結構化摘要 → `outputs/<basename>/summary.md`
4. 自動 render PDF → `outputs/<basename>/summary.pdf`
5. 把重點貼給你

之後可以追問細節、改寫 email、翻譯。

## 實測效能（M4 / 16GB / large-v3-turbo）

| 音檔長度 | 轉錄時間 | 倍速 |
| --- | --- | --- |
| 19 秒（測試） | 1.6 秒 | 4.6× |
| 41 分鐘（實測） | 2 分 16 秒 | 18.2× |
| 預估 2 小時 | ~7 分鐘 | ~17× |

## Notes

- 預設不做講者辨識（pyannote）。若要加，把 `pipeline.py` 的轉錄段換成 WhisperX + pyannote。
- 超過 90 分鐘的音檔會自動切 30 分鐘 chunk，用 offset 還原時間戳。
- 模型 cache 在 `~/.cache/huggingface/hub/`。
- PDF 渲染使用 headless Chromium（Playwright），字型優先：PingFang TC → Heiti TC → Hiragino Sans CNS → Noto Sans CJK TC。Chromium 會把實際使用的字型 subset 完整內嵌進 PDF，在 Preview / Adobe Acrobat / 其他閱讀器都不會缺字。
- 早期版本曾用 WeasyPrint，在 macOS 上會踩到 PingFang.ttc 字型子集嵌入的問題（PDF 在某些閱讀器顯示成缺字），已改用 Chromium 解決。

## License

MIT
