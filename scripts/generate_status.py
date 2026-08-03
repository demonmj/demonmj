"""
Generates status-panel.svg: a self-contained cyberpunk "system status" readout
built from live GitHub API data. No third-party rendering service involved,
so there is nothing external that can rate-limit or go down.
"""
import os
import sys
import datetime
import requests

USERNAME = os.environ.get("USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER")
TOKEN = os.environ.get("GITHUB_TOKEN")

if not USERNAME:
    print("USERNAME env var is required", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Accept": "application/vnd.github+json"}
if TOKEN:
    HEADERS["Authorization"] = f"Bearer {TOKEN}"

def get(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

user = get(f"https://api.github.com/users/{USERNAME}")
events = []
try:
    events = get(f"https://api.github.com/users/{USERNAME}/events/public")
except Exception:
    events = []

created = datetime.datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ")
now = datetime.datetime.utcnow()
uptime_days = (now - created).days

last_activity = "no recent public activity"
if events:
    e = events[0]
    etype = e.get("type", "Event").replace("Event", "")
    repo = e.get("repo", {}).get("name", "")
    last_activity = f"{etype.lower()} @ {repo}"
    if len(last_activity) > 46:
        last_activity = last_activity[:43] + "..."

public_repos = user.get("public_repos", 0)
followers = user.get("followers", 0)
following = user.get("following", 0)
timestamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")

W, H = 900, 300
CYAN = "#00fff2"
MAGENTA = "#ff2ec4"
GREEN = "#39ff9d"
BG0 = "#050208"
BG1 = "#120524"

rows = [
    ("USER", f"{USERNAME}"),
    ("UPTIME", f"{uptime_days} days since account init"),
    ("PUBLIC_REPOS", str(public_repos)),
    ("FOLLOWERS / FOLLOWING", f"{followers} / {following}"),
    ("LAST_ACTIVITY", last_activity),
    ("SYSTEM_TIME", timestamp),
]

row_svgs = []
row_y = 118
for label, value in rows:
    row_svgs.append(f'''
    <text x="60" y="{row_y}" font-family="Consolas, 'Courier New', monospace" font-size="15" fill="{GREEN}">{label}</text>
    <text x="360" y="{row_y}" font-family="Consolas, 'Courier New', monospace" font-size="15" fill="{CYAN}">{value}</text>
    <line x1="60" y1="{row_y+12}" x2="{W-60}" y2="{row_y+12}" stroke="#1c1236" stroke-width="1"/>''')
    row_y += 30

svg = f'''<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{BG0}"/>
      <stop offset="100%" stop-color="{BG1}"/>
    </linearGradient>
    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{CYAN}"/>
      <stop offset="50%" stop-color="{MAGENTA}"/>
      <stop offset="100%" stop-color="{CYAN}"/>
    </linearGradient>
    <pattern id="grid" width="26" height="26" patternUnits="userSpaceOnUse">
      <path d="M 26 0 L 0 0 0 26" fill="none" stroke="#1c1236" stroke-width="1"/>
    </pattern>
    <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="2.6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>

  <rect width="{W}" height="{H}" rx="6" fill="url(#bg)"/>
  <rect width="{W}" height="{H}" rx="6" fill="url(#grid)" opacity="0.5"/>
  <rect x="1" y="1" width="{W-2}" height="{H-2}" rx="6" fill="none" stroke="url(#borderGrad)" stroke-width="2"/>

  <text x="60" y="46" font-family="Consolas, 'Courier New', monospace" font-size="20" fill="{CYAN}" filter="url(#glow)">root@demonmj:~$ ./system_status.sh</text>
  <circle cx="{W-40}" cy="40" r="6" fill="{GREEN}">
    <animate attributeName="opacity" values="1;0.2;1" dur="1.4s" repeatCount="indefinite"/>
  </circle>
  <text x="{W-58}" y="45" font-family="Consolas, 'Courier New', monospace" font-size="12" fill="{GREEN}" text-anchor="end">LIVE</text>

  <line x1="60" y1="60" x2="{W-60}" y2="60" stroke="{MAGENTA}" stroke-width="1" opacity="0.6"/>

  {''.join(row_svgs)}

  <text x="60" y="{H-24}" font-family="Consolas, 'Courier New', monospace" font-size="12" fill="#7a7a9a">auto-refreshed by .github/workflows/status-panel.yml</text>
</svg>
'''

with open("status-panel.svg", "w") as f:
    f.write(svg)

print(f"wrote status-panel.svg for {USERNAME}: uptime={uptime_days}d repos={public_repos} followers={followers}")
