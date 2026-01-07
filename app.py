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
from yt_dlp import YoutubeDL


HK_TZ = pytz.timezone("Asia/Hong_Kong")

st.set_page_config(page_title="Now → MP3", layout="wide", page_icon="🎧")
st.title("🎧 Now 連結 → MP3（伺服器端）")
st.caption("貼上 Now 新聞 / 節目連結，伺服器端用 yt-dlp + ffmpeg 抽音訊並輸出 mp3。")


# -------------------------
# Helpers
# -------------------------
def now_hk_str() -> str:
    return datetime.datetime.now(HK_TZ).strftime("%Y-%m-%d %H:%M:%S")

def is_now_url(url: str) -> bool:
    url = (url or "").strip()
    return ("news.now.com" in url) or ("now.com" in url)

def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name or "")
    name = name.strip()[:120]
    return name if name else "now_audio"

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
        "socket_timeout": 25,
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

        # 掃資料夾找 mp3（最穩）
        mp3 = None
        for fn in os.listdir(workdir):
            if fn.lower().endswith(".mp3"):
                mp3 = os.path.join(workdir, fn)
                break

        if not mp3 or not os.path.exists(mp3):
            return None, info or {}, "已下載，但找不到 mp3 檔（請確認已安裝 ffmpeg）"

        return mp3, info or {}, None

    except Exception as e:
        return None, {}, f"{type(e).__name__}: {e}"


# -------------------------
# Sidebar
# -------------------------
with st.sidebar:
    st.markdown("## Action Panel（左邊）")
    st.write(f"香港時間：{now_hk_str()}")
    st.divider()

    if st.button("清除本頁結果", use_container_width=True):
        for k in ["mp3_bytes", "mp3_name", "last_info", "last_err", "last_url"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# -------------------------
# Main UI
# -------------------------
url = st.text_input(
    "Now 連結",
    value="https://news.now.com/home/local/player?newsId=632067",
    placeholder="https://news.now.com/home/local/player?newsId=xxxxxx",
)

run = st.button("生成 MP3", type="primary", use_container_width=True)

if run:
    u = (url or "").strip()
    st.session_state["last_url"] = u

    if not is_now_url(u):
        st.warning("呢條連結睇落唔似 Now（news.now.com / now.com）。如果你確定係 Now，可照樣再試。")

    st.info("開始處理（伺服器端跑 yt-dlp + ffmpeg）…")

    workdir = tempfile.mkdtemp(prefix="now_mp3_")
    try:
        mp3_path, info, err = download_audio_mp3(u, workdir)
        st.session_state["last_info"] = info
        st.session_state["last_err"] = err

        if err:
            st.error(f"失敗：{err}")
            st.caption("若見到 ffmpeg 相關錯誤，請確認 Railway 用 nixpacks 安裝 ffmpeg（見 nixpacks.toml）。")
        else:
            title = (info.get("title") or "").strip()
            fname = safe_filename(title) + ".mp3"

            with open(mp3_path, "rb") as f:
                mp3_bytes = f.read()

            st.session_state["mp3_bytes"] = mp3_bytes
            st.session_state["mp3_name"] = fname

            st.success("完成。你可以直接下載 MP3。")

    finally:
        shutil.rmtree(workdir, ignore_errors=True)

# -------------------------
# Result area
# -------------------------
mp3_bytes = st.session_state.get("mp3_bytes")
mp3_name = st.session_state.get("mp3_name")

if mp3_bytes and mp3_name:
    st.download_button(
        "⬇️ 下載 MP3",
        data=mp3_bytes,
        file_name=mp3_name,
        mime="audio/mpeg",
        use_container_width=True,
    )

    with st.expander("Debug（可收起）"):
        info = st.session_state.get("last_info", {}) or {}
        st.json(
            {
                "title": info.get("title"),
                "id": info.get("id"),
                "webpage_url": info.get("webpage_url"),
                "duration": info.get("duration"),
                "extractor": info.get("extractor"),
            }
        )
