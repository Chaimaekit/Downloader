from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import json
import os
from fastapi.staticfiles import StaticFiles
import uvicorn
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles



app = FastAPI()
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"], 
)

@app.get("/", response_class=HTMLResponse)
def root():
    with open("static/home.html", encoding='utf-8') as f:
        return f.read()

@app.get("/search")
def get_search_results(song_name: str, num_results: int):
    print(f"Searching for : {song_name} Getting {num_results} results")
    search_query = f"ytsearch{num_results}:{song_name}"
    
    cmd = [
        "yt-dlp",
        "--dump-json",
        search_query
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        videos = [json.loads(line) for line in lines]
        
        return JSONResponse([
            {
                "title": v["title"],
                "url": v["webpage_url"]
            } for v in videos
        ])
    except subprocess.CalledProcessError as e:
        return JSONResponse(status_code=500, content={"error": "Search failed", "details": str(e)})

@app.get("/download")
def download_audio(video_url: str):
    download_dir = "downloads"
    os.makedirs(download_dir, exist_ok=True)  #create the folder if not

    output_template = os.path.join(download_dir, "%(title)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--extract-audio",
        "--audio-format", "mp3",
        "--output", output_template,
        video_url
    ]

    try:
        subprocess.run(cmd, check=True)
        mp3_files = [f for f in os.listdir(download_dir) if f.endswith(".mp3")]
        if not mp3_files:
            raise HTTPException(status_code=500, detail="No MP3 file found after download.")

        mp3_files.sort(key=lambda f: os.path.getmtime(os.path.join(download_dir, f)), reverse=True)
        latest_file = mp3_files[0]
        file_path = os.path.join(download_dir, latest_file)

        return FileResponse(path=file_path, filename=latest_file, media_type="audio/mpeg")

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")
    

@app.get("/download_playlist")
def download_playlist(playlist_url: str = Query(..., description="YouTube playlist URL")):

    base_dir = "downloads/playlists"
    os.makedirs(base_dir, exist_ok=True)

    try:
        title_proc = subprocess.run(
            ["yt-dlp", "--print", "%(playlist_title)s", "--skip-download", playlist_url],
            capture_output=True, text=True, check=True
        )
        playlist_title = title_proc.stdout.strip().splitlines()[0] or "playlist"
    except subprocess.CalledProcessError as e:
        raise HTTPException(400, f"Cannot read playlist title: {e.stderr}")

    playlist_folder = os.path.join(base_dir, playlist_title)
    os.makedirs(playlist_folder, exist_ok=True)

    cmd = [
        "yt-dlp",
        "--yes-playlist",
        "--extract-audio", "--audio-format", "mp3",
        "--output", os.path.join(playlist_folder, "%(playlist_index)03d - %(title)s.%(ext)s"),
        playlist_url
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"Download failed:\n{e.stderr}")

    return JSONResponse({"message": f"Playlist downloaded to folder: {playlist_folder}"})
        
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)