"""Піксельна тема. Рух стрибками, тіні без розмиття."""

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Press+Start+2P&family=VT323&display=swap');

.stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
  background: #1A1033;
  color: #F5F0FF;
}
[data-testid="stSidebar"] {
  background: #241445;
  border-right: 3px solid #000;
}
[data-testid="stSidebar"] * {
  color: #F5F0FF;
}
html, body, .stApp, p, label, span, li, input, textarea {
  font-family: "VT323", monospace;
}
h1, h2, h3, .pixel {
  font-family: "Press Start 2P", monospace !important;
  color: #F5F0FF !important;
  letter-spacing: 0;
}
h1 { font-size: 14px !important; line-height: 1.7 !important; }
h2 { font-size: 12px !important; line-height: 1.7 !important; }
h3 { font-size: 10px !important; line-height: 1.7 !important; }
p, li, label, .stMarkdown { font-size: 20px !important; }
.stButton > button, .stDownloadButton > button {
  border-radius: 0 !important;
  border: 3px solid #000 !important;
  box-shadow: 4px 4px 0 #000 !important;
  background: #00E5C7 !important;
  color: #1A1033 !important;
  font-family: "VT323", monospace !important;
  font-size: 22px !important;
  transition: none !important;
}
.stButton > button:active {
  transform: translate(2px, 2px) !important;
  box-shadow: 2px 2px 0 #000 !important;
}
.stButton > button[kind="secondary"] {
  background: #2D1B4E !important;
  color: #F5F0FF !important;
}
[data-baseweb="select"] > div, [data-baseweb="input"] > div, .stTextInput input, .stNumberInput input {
  border-radius: 0 !important;
  background: #2D1B4E !important;
  color: #F5F0FF !important;
  border: 3px solid #000 !important;
}
.game-card {
  background: #2D1B4E;
  border: 3px solid #000;
  box-shadow: 4px 4px 0 #000;
  padding: 14px 14px 0;
  margin-bottom: 8px;
}
.game-card.watched {
  border-left: 6px solid #00E5C7;
  box-shadow: 6px 4px 0 #00E5C7;
}
.watch-badge {
  font-family: "VT323", monospace;
  font-size: 18px;
  color: #00E5C7;
  margin-left: 6px;
}
.game-top { display: flex; justify-content: space-between; gap: 12px; }
.game-artist {
  font-family: "Press Start 2P", monospace;
  font-size: 12px;
  line-height: 1.6;
  color: #F5F0FF;
}
.game-meta { font-size: 22px; color: #F5F0FF; margin-top: 8px; }
.game-badge {
  border: 3px solid #000;
  background: #1A1033;
  color: #00E5C7;
  font-family: "Press Start 2P", monospace;
  font-size: 8px;
  padding: 8px;
  height: fit-content;
  white-space: nowrap;
}
.game-status { margin: 12px -14px 0; padding: 8px 14px; display: flex; align-items: center; gap: 8px; justify-content: space-between; }
.game-status-label { font-family: "VT323", monospace; font-size: 20px; color: #1A1033; font-weight: bold; }
.ticket-link {
  display: inline-block;
  font-family: "Press Start 2P", monospace;
  font-size: 8px;
  color: #1A1033 !important;
  background: #00E5C7;
  border: 2px solid #000;
  box-shadow: 3px 3px 0 #000;
  padding: 6px 10px;
  text-decoration: none !important;
  white-space: nowrap;
}
.ticket-link:hover { box-shadow: 1px 1px 0 #000; transform: translate(2px,2px); }
.step-box {
  background: #2D1B4E;
  border: 3px solid #000;
  box-shadow: 4px 4px 0 #000;
  padding: 14px;
  margin-bottom: 12px;
}
.step-num {
  font-family: "Press Start 2P", monospace;
  font-size: 10px;
  color: #00E5C7;
  margin-bottom: 6px;
}
.step-desc { font-size: 20px; color: #F5F0FF; }
.px {
  width: 16px; height: 16px; display: inline-block;
  border: 2px solid #000; box-shadow: 2px 2px 0 #000;
}
.meter { display: flex; gap: 4px; margin-top: 8px; }
.meter i {
  width: 28px; height: 12px; display: inline-block;
  background: #6B5B8C; border: 2px solid #000;
}
.meter i.on-high { background: #FF4D9D; }
.meter i.on-medium { background: #FFD93D; }
.meter i.on-low { background: #00E5C7; }
.boot span {
  display: inline-block; width: 14px; height: 14px; margin-right: 4px;
  background: #6B5B8C; border: 2px solid #000;
  animation: blink 0.8s steps(2, end) infinite;
}
.boot span:nth-child(2) { animation-delay: 0.2s; }
.boot span:nth-child(3) { animation-delay: 0.4s; }
.boot span:nth-child(4) { animation-delay: 0.6s; }
@keyframes blink { 50% { background: #00E5C7; } }
.pixel-hero {
  font-family: "VT323", monospace;
  font-size: 20px;
  line-height: 1.1;
  color: #00E5C7;
  white-space: pre;
}
a { color: #00E5C7; }
"""

LOADING = '<div class="boot"><span></span><span></span><span></span><span></span></div>'

EMPTY = """
<div class="pixel-hero">
  ██
 █  █
█ ▄▄ █
█ ▀▀ █
 █  █
  ██
</div>
"""
