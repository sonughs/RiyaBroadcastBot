import asyncio
import os
import re
import json
from typing import Union

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch

from AnonXMusic.utils.database import is_on_off
from AnonXMusic.utils.formatters import time_to_seconds

import glob
import random
import requests

from config import API_URL

def extract_video_id(link: str) -> str:
    patterns = [
        r'youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:playlist\?list=[^&]+&v=|v\/)([0-9A-Za-z_-]{11})',
        r'youtube\.com\/(?:.*\?v=|.*\/)([0-9A-Za-z_-]{11})'
    ]

    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.group(1)

    raise ValueError("Invalid YouTube link provided.")

def piped_api_dl(video_id: str, audio_only: bool = True) -> str:
    """Use Piped API instances to get audio/video stream URL"""
    # List of working Piped instances
    piped_instances = [
        "https://pipedapi.kavin.rocks",
        "https://pipedapi.adminforge.de", 
        "https://api.piped.yt",
        "https://pipedapi.in.projectsegfau.lt",
    ]
    
    for instance in piped_instances:
        try:
            api_url = f"{instance}/streams/{video_id}"
            response = requests.get(api_url, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if audio_only:
                    # Get best audio stream
                    audio_streams = data.get("audioStreams", [])
                    if audio_streams:
                        # Sort by bitrate and get highest quality
                        best = max(audio_streams, key=lambda x: x.get("bitrate", 0))
                        stream_url = best.get("url")
                        if stream_url:
                            print(f"Piped API success: {instance}")
                            return stream_url
                else:
                    # Get video stream
                    video_streams = data.get("videoStreams", [])
                    if video_streams:
                        # Get 720p or closest
                        for vs in video_streams:
                            if vs.get("quality") == "720p" and vs.get("url"):
                                return vs.get("url")
                        # Fallback to any video
                        if video_streams[0].get("url"):
                            return video_streams[0].get("url")
        except Exception as e:
            print(f"Piped instance {instance} failed: {e}")
            continue
    return None

def cobalt_api_dl(video_id: str, audio_only: bool = True) -> str:
    """Use cobalt.tools API to get audio/video stream URL"""
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        api_url = "https://api.cobalt.tools/api/json"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        payload = {
            "url": url,
            "isAudioOnly": audio_only,
            "aFormat": "mp3",
            "vQuality": "720",
            "filenamePattern": "basic",
        }
        response = requests.post(api_url, json=payload, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "stream" or data.get("status") == "redirect":
                return data.get("url")
    except Exception as e:
        print(f"Cobalt API error: {e}")
    return None

# Custom YouTube API - NO yt-dlp, NO cookies!
CUSTOM_API_URL = "http://94.232.247.215:7860"

def custom_api_dl(video_id: str) -> str:
    """Use Custom API to get direct YouTube audio stream URL"""
    try:
        api_url = f"{CUSTOM_API_URL}/api/audio/{video_id}"
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and data.get("url"):
                print(f"Custom API success: {video_id}")
                return data.get("url")  # Return direct YouTube URL
    except Exception as e:
        print(f"Custom API error: {e}")
    return None

def custom_video_api_dl(video_id: str) -> str:
    """Use Custom API to get direct YouTube video stream URL"""
    try:
        api_url = f"{CUSTOM_API_URL}/api/video/{video_id}"
        response = requests.get(api_url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and data.get("url"):
                print(f"Custom Video API success: {video_id}")
                return data.get("url")  # Return direct YouTube URL
    except Exception as e:
        print(f"Custom Video API error: {e}")
    return None

def apii_dl(video_id: str) -> str:
    # Try Custom API first (NO yt-dlp - direct stream URL)
    stream_url = custom_api_dl(video_id)
    if stream_url:
        return stream_url
    
    # Try Piped API as fallback
    stream_url = piped_api_dl(video_id)
    if stream_url:
        return stream_url
    
    # Try cobalt API as fallback
    stream_url = cobalt_api_dl(video_id)
    if stream_url:
        return stream_url
    
    # Fallback to original API
    api_url = f"{API_URL}/yt/id?vid={video_id}&format=mp3&direct"
    file_path = os.path.join("downloads", f"{video_id}.mp3")

    if os.path.exists(file_path):
        return file_path

    response = requests.get(api_url, stream=True, timeout=60)
    if response.status_code == 200 and len(response.content) > 1000:
        os.makedirs("downloads", exist_ok=True)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return file_path
    return None

def api_dl(video_id: str) -> str:
    # Use API for audio download
    return apii_dl(video_id)

def api_video_dl(video_id: str) -> str:
    # Skip API download - it's not working, use yt-dlp instead
    return None

def cookie_txt_file():
    folder_path = f"{os.getcwd()}/cookies"
    txt_files = glob.glob(os.path.join(folder_path, '*.txt'))
    if not txt_files:
        return None  # Return None instead of raising error
    cookie_file = random.choice(txt_files)
    return cookie_file

async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]

        try:
            video_id = extract_video_id(link)
            
            # Try Custom API (NO yt-dlp - direct stream URL)
            stream_url = custom_video_api_dl(video_id)
            if stream_url:
                return 1, stream_url
        except Exception:
            pass

        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()
        semaphore = asyncio.Semaphore(50)

        async def limited(task_func):
            async with semaphore:
                return await loop.run_in_executor(None, task_func)

        def audio_dl():
            # Try Custom API first (NO yt-dlp - direct stream URL)
            try:
                video_id = extract_video_id(link)
                if video_id:
                    stream_url = custom_api_dl(video_id)
                    if stream_url:
                        print(f"Using Custom API stream: {video_id}")
                        return stream_url
            except Exception as e:
                print(f"Custom API failed: {e}")
            
            # Try apii_dl as fallback (Piped, Cobalt)
            try:
                video_id = extract_video_id(link)
                if video_id:
                    api_url = apii_dl(video_id)
                    if api_url:
                        return api_url
            except Exception as e:
                print(f"API fallback failed: {e}")
            
            # Last resort: yt-dlp
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "extractor_args": {"youtube": {"player_client": ["android", "web"]}},
            }
            cookie_file = cookie_txt_file()
            if cookie_file:
                ydl_optssx["cookiefile"] = cookie_file
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            # Return direct stream URL instead of downloading
            if info and info.get('url'):
                return info['url']
            # Fallback: try to get URL from formats
            if info and info.get('formats'):
                for fmt in info['formats']:
                    if fmt.get('acodec') != 'none' and fmt.get('url'):
                        return fmt['url']
            # Last fallback: download file
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            # Try Custom API first (NO yt-dlp - direct stream URL)
            try:
                video_id = extract_video_id(link)
                if video_id:
                    stream_url = custom_video_api_dl(video_id)
                    if stream_url:
                        print(f"Using Custom API video stream: {video_id}")
                        return stream_url
            except Exception as e:
                print(f"Custom Video API failed: {e}")
            
            try:
                sexid = extract_video_id(link)
                path = api_video_dl(sexid)
                if path:
                    return path
            except:
                pass
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
            }
            cookie_file = cookie_txt_file()
            if cookie_file:
                ydl_optssx["cookiefile"] = cookie_file
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile": cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await limited(song_video_dl)
            fpath = f"downloads/{title}.mp4"
            return fpath
        elif songaudio:
            await limited(song_audio_dl)
            fpath = f"downloads/{title}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                direct = True
                downloaded_file = await limited(video_dl)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies", cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        return
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        return None
                    direct = True
                    downloaded_file = await limited(video_dl)
        else:
            direct = True
            downloaded_file = await limited(audio_dl)
        return downloaded_file, direct
