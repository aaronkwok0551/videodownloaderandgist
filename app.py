# app.py
# -*- coding: utf-8 -*-

import os
import re
import shutil
import tempfile
import datetime
from typing import Optional, Dict, Any, Tuple

import pytz
import streamlit as st

# yt-dlp python module
from yt_dlp import YoutubeDL


HK_TZ = pytz.timezone("Asia/Hong_Kong")

st.set_page_config(page_title="Now Gist 生成器", layout="wide", page_icon="🗞️")
st.title("🗞️ Now 連結 → Gist（伺服器端處理）")
st.caption("貼上 Now 新聞 / 節目連結，伺服器端用 yt-dlp + ffmpeg 抽音訊並產出 gist。")


# -------------------------
# Helpers
# -------------------------
def now_hk_str() -> str:
    return datetime.datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")

def normalize_now_url(url: str) -> str:
    url = (url or "").strip()
    # 容忍用戶貼到帶 query
    return url

def is_now_url(url: str) -> bool:
    if not url:
        return False
    return ("news.now.com" in url) or ("now.com" in url)

def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    return name[:120].strip() or "audio"

def fmt_publish_time(info: Dict[str, Any]) -> str:
    """
    yt-dlp info 可能有：
    - timestamp (unix seconds)
    - upload_date (YYYYMMDD)
    - release_timestamp
    """
    ts = info.get("timestamp") or info.get("release_timestamp")
    if isinstance(ts, (int, float)):
        dt = datetime.datetime.fromtimestamp(int(ts), tz=pytz.utc).astimezone(HK_TZ)
        return dt.strftime("%Y-%m-%d %H:%M")

    ud = info.get("upload_date")
    if isinstance(ud, str) and len(ud) == 8 and ud.isdigit():
        dt = HK_TZ.localize(datetime.datetime.strptime(ud, "%Y%m%d"))
        return dt.strftime("%Y-%m-%d")

    return "—"

def build_gist(
    media_name: str,
    title: str,
    publish_time: str,
    content: str,
    url: str
) -> str:
    # 你指定的格式
    return (
        f"{media_name}：{title}\n"
        f"[{publish_time}]\n\n"
        f"{content.strip() if content.strip() else '（暫未加入內文；如需要自動轉文字，請啟用「語音轉文字」功能。）'}\n\n"
        f"{url}\n\n"
        f"Ends"
    )


# -------------------------
# Core: Download audio via yt-dlp
# -------------------------
def download_audio_mp3(url: str, workdir: str) -> Tuple[Optional[str], Dict[str, Any], Optional[str]]:
    """
    伺服器端下載音訊並轉 mp3。
    回傳：(mp3_path, info_dict, error_message)
    """
    outtmpl = os.path.join(workdir, "%(id)s.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 2,
        "socket_timeout": 20,
        # 轉 mp3（需要 ffmpeg）
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # 轉檔後，yt-dlp 通常會在 info 裡寫入 _filename（但未必係 mp3）
            # 最穩陣係掃 workdir 找 mp3
            mp3 = None
            for fn in os.listdir(workdir):
                if fn.lower().endswith(".mp3"):
                    mp3 = os.path.join(workdir, fn)
                    break

            if not mp3 or not os.path.exists(mp3):
                return None, info or {}, "已下載，但找不到 mp3 檔（請確認 Railway 有安裝 ffmpeg）"
            return mp3, info or {}, None

    except Exception as e:
        return None, {}, f"{type(e).__name__}: {e}"


# -------------------------
# Optional: Speech-to-text (OFF by default)
# - 這一步會增加 CPU / RAM / 時間
# - 如你要「真·自動內文」，我建議下一步改成獨立 API service + queue
# -------------------------
def transcribe_with_faster_whisper(mp3_path: str) -> Tuple[str, Optional[str]]:
    """
    需要 requirements 內加 faster-whisper + ctranslate2
    注意：Railway 小機器可能較慢；建議先唔開。
    """
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except Exception:
        return "", "未安裝 faster-whisper（如要自動轉文字，請先在 requirements 加入 faster-whisper）"

    try:
        # tiny 模型最輕；你可改 base/small 但會更慢
        model = WhisperModel("tiny", device="cpu", compute_type="int8")
        segments, info = model.transcribe(mp3_path, language="zh", vad_filter=True)
        text = "".join([seg.text for seg in segments]).strip()
        return text, None
    except Exception as e:
        return "", f"{type(e).__name__}: {e}"


# -------------------------
# UI
# -------------------------
with st.sidebar:
    st.markdown("## Action Panel（固定左邊）")
    st.write(f"香港時間：{now_hk_str()}")
    st.divider()

    enable_stt = st.toggle("語音轉文字（較慢）", value=False, help="會增加處理時間與資源消耗；建議先關閉。")
    st.caption("提示：先用『抽 mp3 + 生成 gist』跑通；再開語音轉文字。")

    st.divider()
    st.markdown("### 一鍵清除（頁面狀態）")
    if st.button("清除本頁結果", use_container_width=True):
        for k in ["gist_text", "last_info", "last_mp3_name", "last_err", "transcript"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

st.markdown("### 1) 貼上 Now 連結")
url = st.text_input(
    "Now 連結",
    value="https://news.now.com/home/local/player?newsId=632067",
    placeholder="https://news.now.com/home/local/player?newsId=xxxxxx",
)

colA, colB = st.columns([1, 1])
with colA:
    run = st.button("生成 Gist", type="primary", use_container_width=True)
with colB:
    st.write("")

st.divider()

if run:
    u = normalize_now_url(url)
    if not is_now_url(u):
        st.error("呢條連結睇落唔似 Now（news.now.com / now.com）。如果你確定係 Now，照貼都可以再試。")
        st.stop()

    st.info("開始處理（伺服器端跑 yt-dlp + ffmpeg）…")

    workdir = tempfile.mkdtemp(prefix="now_gist_")
    try:
        mp3_path, info, err = download_audio_mp3(u, workdir)
        st.session_state["last_info"] = info
        st.session_state["last_err"] = err

        if err:
            st.error(f"處理失敗：{err}")
            # 給你一個 debug hint
            st.caption("若提示 ffmpeg 相關，請確認你已用 nixpacks 安裝 ffmpeg（見下方 nixpacks.toml）。")
            st.stop()

        title = (info.get("title") or "").strip() or "（無標題）"
        publish_time = fmt_publish_time(info)
        media_name = "Now"

        transcript = ""
        if enable_stt and mp3_path:
            with st.spinner("語音轉文字中（可能較慢）…"):
                transcript, stt_err = transcribe_with_faster_whisper(mp3_path)
            if stt_err:
                st.warning(f"轉文字未完成：{stt_err}")

        gist = build_gist(
            media_name=media_name,
            title=title,
            publish_time=publish_time,
            content=transcript,
            url=u,
        )

        st.session_state["gist_text"] = gist
        st.session_state["transcript"] = transcript
        st.session_state["last_mp3_name"] = safe_filename(title) + ".mp3"

        st.success("完成。你可以直接複製 gist，或下載 mp3。")

    finally:
        # 保留 workdir 內 mp3 以供下載：做法係先讀入 bytes 再刪
        # 我哋喺下面下載區會再掃一次 mp3
        st.session_state["__workdir__"] = workdir


# -------------------------
# Results
# -------------------------
gist_text = st.session_state.get("gist_text", "")
workdir = st.session_state.get("__workdir__")

if gist_text:
    st.markdown("### 2) Gist（可一鍵複製）")

    # Streamlit 本身冇「真正 clipboard」API；最穩係用 text_area + 內置 copy（瀏覽器）
    st.text_area("Gist", value=gist_text, height=320)

    # 下載 mp3（可選）
    if workdir and os.path.isdir(workdir):
        mp3_file = None
        for fn in os.listdir(workdir):
            if fn.lower().endswith(".mp3"):
                mp3_file = os.path.join(workdir, fn)
                break

        if mp3_file and os.path.exists(mp3_file):
            with open(mp3_file, "rb") as f:
                data = f.read()
            st.download_button(
                "下載 mp3（可選）",
                data=data,
                file_name=st.session_state.get("last_mp3_name", "audio.mp3"),
                mime="audio/mpeg",
                use_container_width=True,
            )

    st.divider()

    # 顯示部分 meta 方便你核對
    info = st.session_state.get("last_info", {}) or {}
    with st.expander("Debug（可收起）"):
        st.json(
            {
                "title": info.get("title"),
                "id": info.get("id"),
                "uploader": info.get("uploader"),
                "timestamp": info.get("timestamp"),
                "upload_date": info.get("upload_date"),
                "webpage_url": info.get("webpage_url"),
                "duration": info.get("duration"),
            }
        )
