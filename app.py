import re
import subprocess
import streamlit as st
import tempfile
import os

st.set_page_config(page_title="Now → MP3", layout="centered")

st.title("🎧 Now 新聞 → MP3")

# 1️⃣ 輸入 Now URL
url = st.text_input(
    "貼入 Now 新聞連結",
    placeholder="https://news.now.com/home/local/player?newsId=632067",
)

def now_url_to_m3u8(url: str):
    m = re.search(r"newsId=(\d+)", url)
    if not m:
        return None
    nid = m.group(1)
    return f"https://news-videos.now.com/nownews/{nid}/hls/{nid}.m3u8", nid

if url:
    result = now_url_to_m3u8(url)

    if not result:
        st.error("❌ 未能識別 newsId")
        st.stop()

    m3u8_url, news_id = result

    st.success("✅ 已自動識別 m3u8")
    st.code(m3u8_url)

    if st.button("🎵 生成 MP3"):
        with st.spinner("轉換中，請稍等…"):
            with tempfile.TemporaryDirectory() as tmpdir:
                mp3_path = os.path.join(tmpdir, f"{news_id}.mp3")

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i", m3u8_url,
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-ab", "128k",
                    mp3_path
                ]

                try:
                    subprocess.run(
                        cmd,
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    st.error("❌ ffmpeg 轉換失敗")
                    st.stop()

                with open(mp3_path, "rb") as f:
                    st.success("🎉 MP3 已生成")
                    st.download_button(
                        "⬇️ 下載 MP3",
                        data=f,
                        file_name=f"now_{news_id}.mp3",
                        mime="audio/mpeg"
                    )
