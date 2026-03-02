from flask import Flask, render_template_string, request, redirect, session, jsonify
import json
import os
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET", "Xr9$mK2@qP7#nL5vZ")

ADMIN_LOGIN = "mamurbek"
ADMIN_PASSWORD = "Qw!9xM#3pL@7rT$2"  # сложный пароль

def load_stats():
    try:
        with open("stats.json") as f:
            data = json.load(f)
            data["total_users_count"] = len(data.get("total_users", []))
            return data
    except:
        return {"total_users": [], "total_users_count": 0, "total_downloads": 0, "download_history": []}

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/admin/login")
        return f(*args, **kwargs)
    return decorated

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MamurbekSavebot — Admin</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', sans-serif;
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 20px;
    padding: 40px;
    width: 380px;
    box-shadow: 0 25px 50px rgba(0,0,0,0.5);
  }
  .logo {
    text-align: center;
    margin-bottom: 30px;
  }
  .logo h1 { color: #fff; font-size: 22px; margin-top: 10px; }
  .logo p { color: rgba(255,255,255,0.5); font-size: 13px; }
  .bot-icon { font-size: 50px; }
  input {
    width: 100%;
    padding: 14px 18px;
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 12px;
    background: rgba(255,255,255,0.08);
    color: #fff;
    font-size: 15px;
    margin-bottom: 15px;
    outline: none;
    transition: border 0.3s;
  }
  input:focus { border-color: #7c6df7; }
  input::placeholder { color: rgba(255,255,255,0.35); }
  button {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, #7c6df7, #5b4ae8);
    color: #fff;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  button:hover { opacity: 0.85; }
  .error {
    background: rgba(255, 80, 80, 0.15);
    border: 1px solid rgba(255,80,80,0.3);
    color: #ff8080;
    padding: 12px;
    border-radius: 10px;
    margin-bottom: 15px;
    font-size: 14px;
    text-align: center;
  }
</style>
</head>
<body>
<div class="card">
  <div class="logo">
    <div class="bot-icon">🤖</div>
    <h1>MamurbekSavebot</h1>
    <p>Admin Panel</p>
  </div>
  {% if error %}
  <div class="error">❌ {{ error }}</div>
  {% endif %}
  <form method="POST">
    <input type="text" name="username" placeholder="Login" required>
    <input type="password" name="password" placeholder="Parol" required>
    <button type="submit">🔐 Kirish</button>
  </form>
</div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MamurbekSavebot — Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', sans-serif;
    background: #0d1117;
    color: #e6edf3;
    min-height: 100vh;
  }
  .sidebar {
    width: 240px;
    background: #161b22;
    border-right: 1px solid #30363d;
    height: 100vh;
    position: fixed;
    top: 0; left: 0;
    padding: 25px 20px;
    display: flex;
    flex-direction: column;
  }
  .sidebar .brand {
    font-size: 18px;
    font-weight: 700;
    color: #7c6df7;
    margin-bottom: 30px;
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .nav-item {
    padding: 12px 15px;
    border-radius: 10px;
    color: #8b949e;
    cursor: pointer;
    margin-bottom: 5px;
    transition: all 0.2s;
    font-size: 14px;
  }
  .nav-item:hover, .nav-item.active {
    background: rgba(124,109,247,0.15);
    color: #7c6df7;
  }
  .logout {
    margin-top: auto;
    padding: 12px 15px;
    border-radius: 10px;
    color: #ff6b6b;
    cursor: pointer;
    font-size: 14px;
    text-decoration: none;
    display: block;
  }
  .logout:hover { background: rgba(255,107,107,0.1); }
  .main {
    margin-left: 240px;
    padding: 30px;
  }
  .header {
    margin-bottom: 30px;
  }
  .header h2 { font-size: 24px; font-weight: 700; }
  .header p { color: #8b949e; font-size: 14px; margin-top: 5px; }
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
  }
  .stat-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 16px;
    padding: 25px;
  }
  .stat-card .icon { font-size: 32px; margin-bottom: 15px; }
  .stat-card .value { font-size: 36px; font-weight: 700; color: #7c6df7; }
  .stat-card .label { color: #8b949e; font-size: 13px; margin-top: 5px; }
  .table-section {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 16px;
    overflow: hidden;
  }
  .table-header {
    padding: 20px 25px;
    border-bottom: 1px solid #30363d;
    font-weight: 600;
  }
  table { width: 100%; border-collapse: collapse; }
  th {
    background: #0d1117;
    padding: 12px 20px;
    text-align: left;
    font-size: 12px;
    color: #8b949e;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  td {
    padding: 14px 20px;
    border-bottom: 1px solid #21262d;
    font-size: 13px;
  }
  tr:last-child td { border-bottom: none; }
  tr:hover td { background: rgba(124,109,247,0.05); }
  .badge {
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
  }
  .badge-yt { background: rgba(255,0,0,0.15); color: #ff6b6b; }
  .badge-ig { background: rgba(193,53,132,0.15); color: #e1306c; }
  .badge-tt { background: rgba(255,255,255,0.1); color: #e0e0e0; }
  .url-cell {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: #7c6df7;
  }
  .refresh-btn {
    padding: 8px 16px;
    background: rgba(124,109,247,0.15);
    border: 1px solid rgba(124,109,247,0.3);
    color: #7c6df7;
    border-radius: 8px;
    cursor: pointer;
    font-size: 13px;
    float: right;
    margin-top: -5px;
  }
</style>
</head>
<body>
<div class="sidebar">
  <div class="brand">🤖 SaveBot</div>
  <div class="nav-item active">📊 Dashboard</div>
  <div class="nav-item">📥 Yuklashlar</div>
  <div class="nav-item">👥 Foydalanuvchilar</div>
  <a href="/admin/logout" class="logout">🚪 Chiqish</a>
</div>

<div class="main">
  <div class="header">
    <h2>📊 Dashboard</h2>
    <p>MamurbekSavebot — Admin Panel | {{ now }}</p>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="icon">👥</div>
      <div class="value">{{ users }}</div>
      <div class="label">Jami foydalanuvchilar</div>
    </div>
    <div class="stat-card">
      <div class="icon">📥</div>
      <div class="value">{{ downloads }}</div>
      <div class="label">Jami yuklashlar</div>
    </div>
    <div class="stat-card">
      <div class="icon">📅</div>
      <div class="value">{{ today_downloads }}</div>
      <div class="label">Bugungi yuklashlar</div>
    </div>
    <div class="stat-card">
      <div class="icon">🎬</div>
      <div class="value">{{ history_count }}</div>
      <div class="label">Tarix yozuvlari</div>
    </div>
  </div>

  <div class="table-section">
    <div class="table-header">
      📋 So'nggi yuklashlar
      <button class="refresh-btn" onclick="location.reload()">🔄 Yangilash</button>
    </div>
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>Foydalanuvchi</th>
          <th>Platforma</th>
          <th>Video nomi</th>
          <th>Havola</th>
          <th>Hajm</th>
          <th>Vaqt</th>
        </tr>
      </thead>
      <tbody>
        {% for i, item in history %}
        <tr>
          <td>{{ i }}</td>
          <td>{{ item.username }}</td>
          <td>
            {% if 'youtube' in item.url or 'youtu.be' in item.url %}
              <span class="badge badge-yt">YouTube</span>
            {% elif 'instagram' in item.url %}
              <span class="badge badge-ig">Instagram</span>
            {% else %}
              <span class="badge badge-tt">TikTok</span>
            {% endif %}
          </td>
          <td>{{ item.title[:40] }}...</td>
          <td><div class="url-cell"><a href="{{ item.url }}" target="_blank" style="color:#7c6df7">Link</a></div></td>
          <td>{{ item.get('size_mb', '—') }} MB</td>
          <td>{{ item.time }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
</div>
</body>
</html>
"""

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form["username"] == ADMIN_LOGIN and request.form["password"] == ADMIN_PASSWORD:
            session["logged_in"] = True
            return redirect("/admin")
        error = "Login yoki parol noto'g'ri!"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/admin")
@login_required
def admin_dashboard():
    data = load_stats()
    today = datetime.now().strftime("%Y-%m-%d")
    today_dl = sum(1 for h in data["download_history"] if h.get("time", "").startswith(today))
    history = list(enumerate(reversed(data["download_history"]), 1))
    return render_template_string(
        DASHBOARD_HTML,
        users=data["total_users_count"],
        downloads=data["total_downloads"],
        today_downloads=today_dl,
        history_count=len(data["download_history"]),
        history=history,
        now=datetime.now().strftime("%d.%m.%Y %H:%M")
    )

@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin/login")

@app.route("/admin/api/stats")
@login_required
def api_stats():
    data = load_stats()
    return jsonify({
        "users": data["total_users_count"],
        "downloads": data["total_downloads"],
        "history_count": len(data["download_history"])
    })

@app.route("/")
def index():
    return redirect("/admin")