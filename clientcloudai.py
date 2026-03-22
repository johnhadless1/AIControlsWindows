import requests, json, base64, subprocess, time, io, os
from PIL import Image, ImageDraw, ImageFont
from json_repair import repair_json

# maybe... json_repair and something above needs to be install with pip idk

# ── CONFIG ─────────────────────────────────────────────────────────────────
VM_IP    = "YOUR_SERVERS_VNC_IP"
VNC_PASS = "YOUR_VNC_PASSWORD"
LM_URL = "https://ollama.com/v1/chat/completions" # any websites you would want (openai stuff only?)
API_KEY = "YOUR API_KEY" # not recommended, untested,
# API_KEY  = os.environ.get("OLLAMA_API_KEY", "") # UNCOMMENT IF YOU DID "export OLLAMA_API_KEY = blah1blah2blah3_blah4" IDK YET, BUT IT IS RECOMMENDED AS USED BY CREATOR.
MODEL    = "MODEL_OF_YOUR_CHOICE"   # or any cloud model on ollama.com/models / any website with models

# ── GRID SETTINGS ──────────────────────────────────────────────────────────
SCREEN_W, SCREEN_H = 1920, 1280
G1_COLS, G1_ROWS   = 8, 6     # level-1: 130 cells, cols a-m, rows a-j
G2_SIZE            = 5          # level-2: 5x5 = 25 sub-cells labeled 01-25

# ── STATE ──────────────────────────────────────────────────────────────────
cursor_pos = [512, 384]
grid = {"active": False, "level": 1, "region": None, "action": "click"}
os.makedirs("frames", exist_ok=True)

SYSTEM = """You control a Windows 10 PC (1920x1280).
Screenshots have a faint yellow coordinate grid every 100px. A red crosshair shows cursor position.

──── NORMAL ACTIONS ────
Reply ONLY as JSON, nothing else:
{"thought": "...", "action": "ACTION", "x": 0, "y": 0, "x2": 0, "y2": 0, "text": ""}

Actions:
- click / doubleclick / rightclick  at x,y
- drag       drag from x,y to x2,y2
- type       type text (text field)
- key        press key (text: enter, ctrl-c, ctrl-v, super, alt-F4, tab, escape, ctrl-z, super-d, super-e)
- scroll_up / scroll_down  at x,y
- wait       do nothing

──── GRID MODE (use when you need PRECISION clicking) ────
Step 1 — activate grid:
{"thought": "need precision", "action": "grid_show", "text": "click", "x":0,"y":0,"x2":0}
  (text can be: click / doubleclick / rightclick)

Step 2 — screenshot shows GREEN labeled cells (aa=top-left, mj=bottom-right)
         first letter = column (a=left → m=right), second = row (a=top → j=bottom)
{"thought": "target is in cell bc", "action": "grid_select", "text": "bc", "x":0,"y":0,"x2":0}

Step 3 — screenshot zooms into that cell, shows 25 ORANGE sub-cells labeled 01-25 (left→right, top→bottom)
{"thought": "target is sub-cell 13", "action": "grid_select", "text": "13", "x":0,"y":0,"x2":0}
  → click executes at that exact pixel. Grid deactivates.

Check every screenshot carefully — each one is different, never assume the screen is the same."""

# ^- note, clientlocalai.py at github of johnhadless1 has "clientlocalai" which has a lot advanced system prompt than this. or better, you could make yourself, with ai perhaps?

# ── GRID HELPERS ───────────────────────────────────────────────────────────

def g1_cell_rect(col_i, row_i):
    cw = SCREEN_W / G1_COLS
    ch = SCREEN_H / G1_ROWS
    return (int(col_i * cw), int(row_i * ch), int(cw), int(ch))

def g1_label_to_idx(label):
    return ord(label[0]) - ord('a'), ord(label[1]) - ord('a')

def g2_center(label_str, region):
    n   = int(label_str) - 1
    rx, ry, rw, rh = region
    ci, ri = n % G2_SIZE, n // G2_SIZE
    cw, ch = rw / G2_SIZE, rh / G2_SIZE
    return int(rx + ci * cw + cw / 2), int(ry + ri * ch + ch / 2)

def draw_L1(base_rgba):
    draw = ImageDraw.Draw(base_rgba)
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 11)
    except:
        font = ImageFont.load_default()
    for ci in range(G1_COLS):
        for ri in range(G1_ROWS):
            x, y, cw, ch = g1_cell_rect(ci, ri)
            draw.rectangle([x, y, x+cw-1, y+ch-1], outline=(80, 220, 80, 160), width=1)
            lbl = chr(ord('a')+ci) + chr(ord('a')+ri)
            draw.rectangle([x+2, y+2, x+26, y+16], fill=(0, 0, 0, 170))
            draw.text((x+3, y+3), lbl, fill=(80, 255, 80, 255), font=font)

def draw_L2(base_rgba, region):
    rx, ry, rw, rh = region
    dim = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(dim)
    d.rectangle([0, 0, base_rgba.width, base_rgba.height], fill=(0, 0, 0, 150))
    d.rectangle([rx, ry, rx+rw, ry+rh], fill=(0, 0, 0, 0))
    base_rgba.alpha_composite(dim)
    draw = ImageDraw.Draw(base_rgba)
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 14)
    except:
        font = ImageFont.load_default()
    cw, ch = rw / G2_SIZE, rh / G2_SIZE
    for ci in range(G2_SIZE):
        for ri in range(G2_SIZE):
            x = int(rx + ci * cw)
            y = int(ry + ri * ch)
            draw.rectangle([x, y, x+int(cw)-1, y+int(ch)-1], outline=(255, 180, 40, 230), width=2)
            lbl = f"{ri*G2_SIZE+ci+1:02d}"
            draw.rectangle([x+int(cw)//2-12, y+int(ch)//2-10, x+int(cw)//2+16, y+int(ch)//2+10], fill=(0,0,0,185))
            draw.text((x+int(cw)//2-11, y+int(ch)//2-9), lbl, fill=(255, 200, 40, 255), font=font)

# ── SCREENSHOT ─────────────────────────────────────────────────────────────

def add_ruler_and_cursor(img_rgba):
    draw = ImageDraw.Draw(img_rgba)
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 10)
    except:
        font = ImageFont.load_default()
    w, h = img_rgba.size
    for x in range(0, w, 100):
        draw.line([(x,0),(x,h)], fill=(255,255,0,55), width=1)
        draw.text((x+2,2), str(x), fill=(255,255,0,160), font=font)
    for y in range(0, h, 100):
        draw.line([(0,y),(w,y)], fill=(255,255,0,55), width=1)
        draw.text((2,y+2), str(y), fill=(255,255,0,160), font=font)
    cx, cy = cursor_pos
    draw.line([(cx-12,cy),(cx+12,cy)], fill=(255,50,50,255), width=2)
    draw.line([(cx,cy-12),(cx,cy+12)], fill=(255,50,50,255), width=2)
    draw.ellipse([(cx-4,cy-4),(cx+4,cy+4)], outline=(255,50,50,255), width=2)
    draw.text((cx+7,cy+7), f"{cx},{cy}", fill=(255,50,50,210), font=font)

def screenshot():
    raw = requests.get(f"http://{VM_IP}:8765/screenshot", timeout=30).content
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    add_ruler_and_cursor(img)
    if grid["active"]:
        if grid["level"] == 1:
            draw_L1(img)
        elif grid["level"] == 2 and grid["region"]:
            draw_L2(img, grid["region"])
    final = img.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format="PNG")
    data = buf.getvalue()
    with open("frames/AIpov.png", "wb") as f:
        f.write(data)
    print("   saved → frames/AIpov.png")
    return base64.b64encode(data).decode()

def vm(endpoint, params=None, body=None):
    try:
        base = f"http://{VM_IP}:8765"
        if body is not None:
            r = requests.post(f"{base}/{endpoint}", json=body, params=params, timeout=10)
        else:
            r = requests.get(f"{base}/{endpoint}", params=params, timeout=10)
        return r.json()
    except Exception as e:
        print(f"  (vm call failed: {e})")
        return {}

def execute_click(action, x, y):
    cursor_pos[0], cursor_pos[1] = x, y
    if action == "click":
        vm("click", {"x": x, "y": y})
    elif action == "doubleclick":
        vm("doubleclick", {"x": x, "y": y})
    elif action == "rightclick":
        vm("rightclick", {"x": x, "y": y})

def act(j):
    a   = j.get("action", "wait")
    x   = int(j.get("x",  0))
    y   = int(j.get("y",  0))
    x2  = int(j.get("x2", 0))
    y2  = int(j.get("y2", 0))
    txt = j.get("text", "")

    if a == "grid_show":
        grid["active"] = True
        grid["level"]  = 1
        grid["region"] = None
        grid["action"] = txt if txt in ("click","doubleclick","rightclick") else "click"
        print(f"  [GRID] Level 1 activated. Will {grid['action']} on final selection.")
        return

    if a == "grid_select":
        if grid["level"] == 1:
            label = txt.strip().lower()[:2]
            if len(label) < 2:
                print("  [GRID] bad label, ignoring"); return
            ci, ri = g1_label_to_idx(label)
            ci = max(0, min(ci, G1_COLS-1))
            ri = max(0, min(ri, G1_ROWS-1))
            rx, ry, rw, rh = g1_cell_rect(ci, ri)
            grid["region"] = (rx, ry, rw, rh)
            grid["level"]  = 2
            print(f"  [GRID] Cell '{label}' → region {grid['region']}. Showing L2.")
        elif grid["level"] == 2:
            txt_clean = txt.strip()
            if not txt_clean.isdigit():
                print(f"  [GRID] Expected number at L2, got '{txt_clean}' — resetting")
                grid["level"] = 1; return
            px, py = g2_center(txt_clean, grid["region"])
            print(f"  [GRID] Sub-cell '{txt_clean}' → ({px},{py}). Executing {grid['action']}.")
            execute_click(grid["action"], px, py)
            grid["active"] = False
            grid["level"]  = 1
        return

    if a in ("click","doubleclick","rightclick"):
        execute_click(a, x, y)
    elif a == "drag":
        cursor_pos[0], cursor_pos[1] = x2, y2
        vm("drag", {"x": x, "y": y, "x2": x2, "y2": y2})
    elif a == "type":
        vm("type", body={"text": txt})
    elif a == "key":
        vm("key", body={"key": txt})
    elif a == "scroll_up":
        vm("scroll", {"x": x, "y": y, "direction": 3})
    elif a == "scroll_down":
        vm("scroll", {"x": x, "y": y, "direction": -3})
    elif a == "wait":
        time.sleep(3)


# ── THINK ──────────────────────────────────────────────────────────────────

def think(img_b64, history):
    msgs = [{"role": "system", "content": SYSTEM}]
    msgs += [m for m in history if isinstance(m.get("content"), str)][-3:]
    msgs.append({"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        {"type": "text", "text": "What do you see? What is your next action?"}
    ]})
    try:
        r = requests.post(
            LM_URL,
            headers={"Authorization": f"Bearer {API_KEY}"},
            json={"model": MODEL, "messages": msgs, "max_tokens": 500, "temperature": 0.6},
            timeout=120
        )
        raw = r.json()
    except Exception as e:
        print(f"  request failed: {e}")
        return '{"action":"wait","thought":"request error","x":0,"y":0,"x2":0,"y2":0,"text":""}'

    # handle both openai-compat and ollama native formats
    content = None
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        pass
    if content is None:
        try:
            content = raw["message"]["content"]  # ollama native fallback
        except (KeyError, TypeError):
            pass
    if content is None:
        print(f"  unexpected response structure: {json.dumps(raw, indent=2)[:300]}")
        return '{"action":"wait","thought":"parse error","x":0,"y":0,"x2":0,"y2":0,"text":""}'

    # strip <think> tags if thinking model adds them
    if "<think>" in content:
        after_think = content.split("</think>")[-1].strip()
        if after_think:
            content = after_think

    print(f"  raw content: {content[:200]}")
    return content


# ── MAIN LOOP ──────────────────────────────────────────────────────────────

history = []
goal = input("Goal (Enter = AI decides freely): ").strip()
if not goal:
    goal = "Explore this Windows 10 computer freely. Pick something fun to build or do. You decide everything."
history.append({"role": "user", "content": goal})
print("🤖 Agent running. Ctrl+C to stop.\n")

while True:
    try:
        print("📸 Screenshot...")
        img = screenshot()
        print("🧠 Thinking...")
        response = think(img, history)
        print(f"AI: {response}\n")
        history.append({"role": "assistant", "content": response})
        try:
            j = repair_json(response, return_objects=True)
            if isinstance(j, dict):
                act(j)
        except Exception as pe:
            print(f"(parse error: {pe})")
        if len(history) > 20:
            history = history[:1] + history[-10:]
        time.sleep(1.5)
    except KeyboardInterrupt:
        print("\n🛑 Stopped."); break
    except Exception as ex:
        print(f"Error: {ex}")
        if any(w in str(ex) for w in ["Connection", "timeout", "refused"]):
            print("⚠️ Lost VM connection! Restart server.py in VM then press Enter...")
            input()
        time.sleep(5)
