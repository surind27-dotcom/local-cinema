import os
import json
import uvicorn
import requests
import subprocess
import time
import sys
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

VIDEO_DIR = "movies"
GO_SERVER_URL = "http://localhost:8001/api/files"

if not os.path.exists(VIDEO_DIR):
    os.makedirs(VIDEO_DIR)

# --- Логика работы с историей ---

def get_history_path(username: str):
    return f"history_{username}.json"

def load_history(username: str):
    path = get_history_path(username)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_history(username: str, history: dict):
    path = get_history_path(username)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

# --- Маршруты ---

app.mount("/stream", StaticFiles(directory=VIDEO_DIR), name="stream")

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return """
    <html>
        <head>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Вход в систему</title>
        </head>
        <body style="background:#141414;color:white;font-family:sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;">
            <form action="/login" method="post" style="background:#222;padding:40px;border-radius:15px;border:1px solid #e50914;text-align:center;max-width:400px;width:90%;">
                <h1 style="color:#e50914;margin-bottom:10px;text-transform:uppercase;">Кто смотрит?</h1>
                <p style="color:#aaa;font-size:14px;margin-bottom:25px;line-height:1.4;">
                    Имя вводите на английском или используя латиницу
                </p>
                <input type="text" name="username" placeholder="Ваше имя (Latin)" required 
                    style="padding:12px;border-radius:5px;border:none;width:100%;margin-bottom:20px;box-sizing:border-box;background:#333;color:white;outline:none;">
                <br>
                <button type="submit" style="background:#e50914;color:white;padding:12px;border:none;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;font-size:16px;">ВОЙТИ</button>
            </form>
        </body>
    </html>
    """

@app.post("/login")
async def login(username: str = Form(...)):
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="username", value=username)
    return response

@app.post("/toggle_watched")
async def toggle_watched(request: Request):
    username = request.cookies.get("username")
    if not username:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
        
    data = await request.json()
    file_path = data.get("file_path")
    history = load_history(username)
    
    if file_path in history:
        del history[file_path]
        status = False
    else:
        history[file_path] = True
        status = True
        
    save_history(username, history)
    return JSONResponse({"status": status})

@app.get("/", response_class=HTMLResponse)
@app.get("/browse/{path:path}", response_class=HTMLResponse)
async def browse(request: Request, path: str = ""):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/login")

    try:
        response = requests.get(GO_SERVER_URL)
        all_videos = response.json()
    except Exception as e:
        return HTMLResponse(content=f"<h1 style='color:red;'>Ошибка: Go-сканер не запущен!</h1>", status_code=500)

    history = load_history(username)
    html_content = ""
    seen_subdirs = set()
    
    back_button = ""
    if path:
        parent_path = os.path.dirname(path.rstrip("/")).replace("\\", "/")
        back_link = f"/browse/{parent_path}" if parent_path else "/"
        back_button = f'<div style="width:100%;text-align:left;margin-bottom:20px;"><a href="{back_link}" style="background:#333;color:white;padding:10px 20px;text-decoration:none;border-radius:8px;border:1px solid #444;"><i class="fa-solid fa-arrow-left"></i> НАЗАД</a></div>'

    current_path_prefix = path.strip("/")
    
    for video in all_videos:
        v_path = video['path'].strip("/")
        if v_path.startswith(current_path_prefix) or not current_path_prefix:
            rel_path = v_path[len(current_path_prefix):].lstrip("/")
            parts = rel_path.split("/")
            
            if len(parts) > 1:
                subdir_name = parts[0]
                if subdir_name not in seen_subdirs:
                    full_subdir_path = os.path.join(path, subdir_name).replace("\\", "/")
                    html_content += f' <a href="/browse/{full_subdir_path}" style="text-decoration:none; color:inherit;"><div class="card" data-name="{subdir_name.lower()}" style="background:#222;width:190px;padding:20px;margin:10px;border-radius:15px;text-align:center;border:1px solid #333;cursor:pointer;"><div style="font-size:55px;margin-bottom:10px;"><i class="fa-solid fa-folder" style="color:#f8d775;"></i></div><div class="card-title" style="font-size:13px;color:#ccc;height:35px;overflow:hidden;margin-bottom:15px;">{subdir_name}</div><div style="background:#444;color:white;padding:8px;border-radius:5px;font-weight:bold;font-size:12px;">ОТКРЫТЬ</div></div></a>'
                    seen_subdirs.add(subdir_name)
            else:
                file_name = video['name']
                full_rel_path = video['path']
                is_watched = full_rel_path in history
                eye_icon = "fa-eye" if is_watched else "fa-eye-slash"
                eye_color = "#e50914" if is_watched else "#555"
                border_color = "#e50914" if is_watched else "#333"
                
                # Передаем параметр folder для корректной работы кнопки назад в плеере
                html_content += f"""
                <div class="card" data-name="{file_name.lower()}" style="background:#222;width:190px;padding:20px;margin:10px;border-radius:15px;text-align:center;position:relative;border:1px solid {border_color};cursor:pointer;">
                    <div onclick="event.preventDefault(); event.stopPropagation(); toggleManual('{full_rel_path}')" style="position:absolute;top:12px;right:12px;cursor:pointer;color:{eye_color};font-size:18px;z-index:10;">
                        <i class="fa-solid {eye_icon}"></i>
                    </div>
                    <a href="/watch?file={full_rel_path}&folder={path}" style="text-decoration:none; color:inherit; display:block;">
                        <div style="font-size:55px;margin-bottom:10px;"><i class="fa-solid fa-circle-play" style="color:#e50914;"></i></div>
                        <div class="card-title" style="font-size:13px;color:white;height:35px;overflow:hidden;margin-bottom:5px;">{file_name}</div>
                        <div style="background:#e50914;color:white;padding:8px;border-radius:5px;font-weight:bold;font-size:12px;">СМОТРЕТЬ</div>
                    </a>
                </div>"""

    return f"""
    <html>
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                .card {{ transition: transform 0.2s, background 0.2s; }}
                .card:hover {{ transform: translateY(-5px); background: #2a2a2a !important; }}
                #searchInput::placeholder {{ color: #666; }}
            </style>
            <script>
                async function toggleManual(path) {{
                    await fetch('/toggle_watched', {{method: 'POST', body: JSON.stringify({{file_path: path}}), headers: {{'Content-Type': 'application/json'}}}});
                    location.reload();
                }}

                function filterMovies() {{
                    let input = document.getElementById('searchInput').value.toLowerCase();
                    let cards = document.getElementsByClassName('card');
                    for (let card of cards) {{
                        let name = card.getAttribute('data-name');
                        if (name.includes(input)) {{
                            card.style.display = "";
                        }} else {{
                            card.style.display = "none";
                        }}
                    }}
                }}
            </script>
        </head>
        <body style="background:#141414;color:white;font-family:sans-serif;padding:30px;text-align:center;">
            <div style="position:absolute; top:10px; right:20px; color:#aaa;">Привет, <b>{username}</b>! <a href="/login" style="color:#e50914; text-decoration:none; margin-left:10px;">Сменить профиль</a></div>
            
            <h1 style="color:#e50914; margin-bottom:10px;">MY CINEMA <small style="color:white; font-size:12px;">(User Mode)</small></h1>
            
            <div style="margin-bottom:30px;">
                <input type="text" id="searchInput" onkeyup="filterMovies()" placeholder="Поиск фильма или папки..." 
                    style="padding:12px 20px; border-radius:25px; border:1px solid #333; background:#222; color:white; width:100%; max-width:400px; outline:none; font-size:16px; border-color:#e50914;">
            </div>

            <div style="display:flex;flex-wrap:wrap;justify-content:center;max-width:1200px;margin:0 auto;">{back_button}{html_content}</div>
        </body>
    </html>"""

@app.get("/watch", response_class=HTMLResponse)
async def watch(request: Request, file: str, folder: str = ""):
    username = request.cookies.get("username")
    if not username:
        return RedirectResponse(url="/login")

    # Формируем прямую ссылку назад в папку
    back_link = f"/browse/{folder}" if folder else "/"
        
    next_file_link = ""
    try:
        response = requests.get(GO_SERVER_URL)
        all_videos = response.json()
        
        current_index = -1
        for i, v in enumerate(all_videos):
            if v['path'] == file:
                current_index = i
                break
        
        if current_index != -1 and current_index + 1 < len(all_videos):
            next_video = all_videos[current_index + 1]
            if os.path.dirname(next_video['path']) == os.path.dirname(file):
                # Прокидываем параметр folder дальше в следующую серию
                next_file_link = f'<a id="nextSeries" href="/watch?file={next_video["path"]}&folder={folder}" style="background:#e50914; color:white; padding:10px 20px; text-decoration:none; border-radius:8px; font-weight:bold; margin-left:20px;">СЛЕДУЮЩАЯ СЕРИЯ →</a>'
    except:
        pass

    return f"""
    <html>
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="background:#000;color:white;text-align:center;padding:20px;font-family:sans-serif;">
            <div style="margin-bottom:20px; display:flex; justify-content:center; align-items:center;">
                <a href="{back_link}" style="color:#aaa;text-decoration:none;font-weight:bold;font-size:18px;">← НАЗАД</a>
                {next_file_link}
            </div>
            <h2 style="margin-bottom:20px;">{os.path.basename(file)}</h2>
            <div style="max-width:1000px; margin:0 auto; padding:10px; background:#1a1a1a; border:4px solid #e50914; border-radius:20px;">
                <video id="vPlayer" width="100%" controls autoplay playsinline><source src="/stream/{file}" type="video/mp4"></video>
            </div>
            <script>
                const v = document.getElementById('vPlayer');
                const storageKey = 'time_{username}_{file}';
                v.onloadedmetadata = () => {{
                    const t = localStorage.getItem(storageKey);
                    if (t) v.currentTime = parseFloat(t);
                }};
                v.ontimeupdate = () => {{
                    localStorage.setItem(storageKey, v.currentTime);
                }};
                v.onended = () => {{
                    localStorage.removeItem(storageKey);
                    const nextBtn = document.getElementById('nextSeries');
                    if (nextBtn) window.location.href = nextBtn.href;
                }};
            </script>
        </body>
    </html>"""

if __name__ == "__main__":
    print("--- Инициализация MY CINEMA ---")
    
    go_process = None
    try:
        print("Попытка запуска Go-движка...")
        if os.name == 'nt':
            go_cmd = 'start "Go Engine" go run Cinema.go'
            go_process = subprocess.Popen(go_cmd, shell=True)
        else:
            go_cmd = ["go", "run", "Cinema.go"]
            go_process = subprocess.Popen(go_cmd)
            
    except Exception as e:
        print(f"Критическая ошибка при запуске Go: {e}")
        sys.exit(1)

    print("Ожидание запуска сканера (3 сек)...")
    time.sleep(3) 

    print(f"Python-интерфейс: http://localhost:8000")
    
    try:
        uvicorn.run(app, host="0.0.0.0", port=8000)
    finally:
        if go_process:
            print("Остановка процессов...")
            go_process.terminate()