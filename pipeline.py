#!/usr/bin/env python3
"""
Meeting transcription pipeline.

Usage:
    python pipeline.py <audio_file>

Outputs (all under outputs/<basename>/):
    - transcript.md     繁體中文逐字稿（含時間戳）
    - transcript.pdf    繁體 PDF
    - segments.json     原始 Whisper segment 資料（已轉繁）

Requires DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib (for WeasyPrint).
Designed for Apple Silicon (mlx-whisper large-v3-turbo).
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
AUDIO_DIR = ROOT / "audio"
OUTPUTS_DIR = ROOT / "outputs"
MODEL_REPO = "mlx-community/whisper-large-v3-turbo"
CHUNK_THRESHOLD_SEC = 90 * 60
CHUNK_SIZE_SEC = 30 * 60
# 不強制輸出語言：強制中文會把英文段落幻覺成中文亂碼（雙語會議）。
# 讓 whisper 依各段實際語言輸出（中文逐字稿仍由 OpenCC s2twp 轉繁體）。
INITIAL_PROMPT = "This is a bilingual meeting recording in Mandarin Chinese and English. Transcribe each speaker in the language actually spoken: keep English as English and Chinese as Chinese. Preserve proper nouns and acronyms."


def fmt_ts(seconds: float) -> str:
    td = timedelta(seconds=int(seconds))
    h, rem = divmod(td.seconds + td.days * 86400, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def ffprobe_duration(path: Path) -> float:
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ])
    return float(out.decode().strip())


def normalize_audio(src: Path, dst: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le",
        str(dst),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def split_chunks(wav: Path, chunk_sec: int) -> list[Path]:
    chunk_dir = wav.parent / f"{wav.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)
    pattern = str(chunk_dir / "chunk_%03d.wav")
    subprocess.run([
        "ffmpeg", "-y", "-i", str(wav),
        "-f", "segment", "-segment_time", str(chunk_sec),
        "-c", "copy", pattern,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(chunk_dir.glob("chunk_*.wav"))


def transcribe(wav: Path, offset: float = 0.0) -> dict:
    import mlx_whisper
    result = mlx_whisper.transcribe(
        str(wav),
        path_or_hf_repo=MODEL_REPO,
        initial_prompt=INITIAL_PROMPT,
        condition_on_previous_text=False,
        verbose=False,
    )
    if offset:
        for seg in result.get("segments", []):
            seg["start"] += offset
            seg["end"] += offset
    return result


def s2tw(segments: list[dict], full_text: str) -> tuple[list[dict], str]:
    """Convert simplified Chinese → Traditional Chinese (Taiwan idiom)."""
    from opencc import OpenCC
    cc = OpenCC("s2twp")
    converted_segments = []
    for seg in segments:
        seg = dict(seg)
        seg["text"] = cc.convert(seg.get("text", ""))
        converted_segments.append(seg)
    return converted_segments, cc.convert(full_text)


def render_markdown(src_path: Path, duration: float, segments: list[dict], language: str) -> str:
    lines = [
        f"# 會議逐字稿",
        f"",
        f"- **檔案**：`{src_path.name}`",
        f"- **時長**：{fmt_ts(duration)}",
        f"- **語言**：{language}（已轉繁體中文 / 台灣慣用語）",
        f"- **模型**：whisper-large-v3-turbo (mlx)",
        f"- **生成時間**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"---",
        f"",
        f"## 逐字稿",
        f"",
    ]
    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        lines.append(f"`[{fmt_ts(seg['start'])}]` {text}")
        lines.append("")
    return "\n".join(lines)


def render_pdf(md_path: Path, pdf_path: Path) -> None:
    from render_pdf import render
    render(md_path, pdf_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio", type=Path, help="Path to audio file")
    parser.add_argument("--keep-wav", action="store_true", help="Keep normalized wav after run")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    args = parser.parse_args()

    src: Path = args.audio.expanduser().resolve()
    if not src.exists():
        print(f"[ERROR] file not found: {src}", file=sys.stderr)
        return 1

    out_dir = OUTPUTS_DIR / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    AUDIO_DIR.mkdir(exist_ok=True)

    started = time.time()
    print(f"[1/4] 正規化音檔 → 16kHz mono WAV ...")
    wav = AUDIO_DIR / f"{src.stem}.norm.wav"
    normalize_audio(src, wav)
    duration = ffprobe_duration(wav)
    print(f"      時長 {fmt_ts(duration)}")

    print(f"[2/4] 載入模型並轉錄（首次會下載 ~1.5GB）...")
    all_segments: list[dict] = []
    full_text = ""
    language = "auto"

    if duration > CHUNK_THRESHOLD_SEC:
        print(f"      > {CHUNK_THRESHOLD_SEC // 60} 分鐘，自動切 {CHUNK_SIZE_SEC // 60} 分鐘 chunk")
        chunks = split_chunks(wav, CHUNK_SIZE_SEC)
        for i, chunk in enumerate(chunks):
            offset = i * CHUNK_SIZE_SEC
            print(f"      chunk {i + 1}/{len(chunks)}  offset={fmt_ts(offset)}")
            result = transcribe(chunk, offset=offset)
            all_segments.extend(result.get("segments", []))
            full_text += result.get("text", "")
            if i == 0:
                language = result.get("language", language)
        shutil.rmtree(chunks[0].parent, ignore_errors=True)
    else:
        result = transcribe(wav)
        all_segments = result.get("segments", [])
        full_text = result.get("text", "")
        language = result.get("language", language)

    print(f"[3/4] 簡→繁轉換（OpenCC s2twp，台灣慣用語）...")
    all_segments, full_text = s2tw(all_segments, full_text)

    print(f"[4/4] 輸出檔案到 {out_dir} ...")
    md = render_markdown(src, duration, all_segments, language)
    out_md = out_dir / "transcript.md"
    out_md.write_text(md, encoding="utf-8")

    out_json = out_dir / "segments.json"
    out_json.write_text(json.dumps({
        "source": str(src),
        "duration_sec": duration,
        "language": language,
        "segments": all_segments,
        "full_text": full_text,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    out_pdf = None
    if not args.no_pdf:
        out_pdf = out_dir / "transcript.pdf"
        render_pdf(out_md, out_pdf)

    if not args.keep_wav:
        wav.unlink(missing_ok=True)

    elapsed = time.time() - started
    rtf = elapsed / duration if duration else 0
    print()
    print(f"✓ 完成")
    print(f"  資料夾：{out_dir}")
    print(f"  逐字稿（MD）：{out_md}")
    if out_pdf:
        print(f"  逐字稿（PDF）：{out_pdf}")
    print(f"  片段資料：{out_json}")
    print(f"  耗時：{elapsed:.1f}s（{1 / rtf:.1f}× realtime）" if rtf else f"  耗時：{elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
