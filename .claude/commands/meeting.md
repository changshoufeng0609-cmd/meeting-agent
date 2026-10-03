---
description: 會議音檔 → 繁體中文逐字稿 + 結構化摘要（MD + PDF），每場會議獨立資料夾
argument-hint: <音檔路徑，支援 .m4a/.mp3/.mp4/.wav 等>
---

請依下列流程處理會議音檔，全程使用繁體中文（台灣慣用語）。

音檔路徑：$ARGUMENTS

## 流程

### 1. 前置檢查
- 若 `$ARGUMENTS` 為空，直接回覆「請給我音檔路徑，例如：`/meeting ~/Downloads/2026-05-22.m4a`」並停止
- 用 Bash 確認檔案存在；不存在則回報後停止

### 2. 轉錄（呼叫 pipeline.py）
在本 repo 根目錄啟動 venv 並執行 pipeline（請在 repo 根目錄開 Claude Code）。**必須**：
- `dangerouslyDisableSandbox: true`（Metal GPU + Chromium PDF 渲染）
- timeout 視音檔長度設定（>2 小時設 900000 ms）

```bash
source .venv/bin/activate && \
  python pipeline.py "<音檔絕對路徑>"
```

Pipeline 會：
1. 用 ffmpeg 正規化音檔
2. mlx-whisper large-v3-turbo 轉錄（首次下載 ~1.5GB 模型）
3. OpenCC s2twp 轉繁體（台灣慣用語：网络→網路、软件→軟體）
4. 輸出到 `outputs/<basename>/`：
   - `transcript.md`（含時間戳）
   - `transcript.pdf`（A4，headless Chromium 渲染，字型完整內嵌）
   - `segments.json`

失敗就把 stderr 報給使用者並停止，不要硬猜。

### 3. 讀逐字稿
用 Read 讀進 `outputs/<basename>/transcript.md`。

### 4. 寫結構化摘要
寫到 `outputs/<basename>/summary.md`，遵循以下結構（**繁體中文**）：

```markdown
# 會議摘要：<推測的會議主題>

- **原音檔**：`<basename>`
- **時長**：<h:mm:ss>
- **錄製日**：<從檔名或內容推斷>
- **摘要生成**：<today>

## 與會角色
（從逐字稿推斷可辨識的角色 / 單位）

## 一頁摘要
（3-5 句，回答「這場會議在幹嘛、結論是什麼」）

## 決議事項
- ...
- ...

## Action Items
| 負責人 | 任務 | 期限 |
| --- | --- | --- |
| ... | ... | ... |

（若逐字稿沒提到負責人或期限，就寫「未指定」，不要硬編。）

## 重點討論
### 1. <主題>
- 關鍵論點
- 反對/支持意見
- 引用：`[時間戳]` 原句節錄（只在原句很關鍵時引用）

### 2. <主題>
...

## 待釐清 / 風險
- ...

## 時間軸索引
- `[00:00]` 開場
- `[mm:ss]` <關鍵段落標題>
- ...
```

### 5. 產出 summary.pdf
用 render_pdf.py（headless Chromium）把 summary.md 轉成 PDF：

```bash
source .venv/bin/activate && \
  python render_pdf.py "outputs/<basename>/summary.md"
```

`dangerouslyDisableSandbox: true`。

### 6. 收尾回覆
回覆使用者：
- 一頁摘要（直接貼）
- 決議與 Action items 條列
- 四個檔案路徑（transcript.md / transcript.pdf / summary.md / summary.pdf）
- 一行提示：「想追問細節、改寫成 email、翻成英文，直接告訴我就好」

## 注意事項

- **不要在摘要裡編造**逐字稿沒講的人名、數字、日期
- 中英混雜段落原樣保留（OpenCC 已處理簡繁，不會誤轉英文）
- 量化資訊（金額、百分比、日期）優先放進決議或 Action items
- 若整段音檔長度 < 60 秒，跳過分區，直接給一段話的紀要
- 同音字錯字（例如「部署」→「不屬」、「儀表板」→「儀表版」）若明顯，**可在摘要中以括號標註正確版本**並標 `(轉錄推測)`
