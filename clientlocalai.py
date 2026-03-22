import requests, json, base64, subprocess, time, io
from PIL import Image, ImageDraw, ImageFont
from json_repair import repair_json

# WARNING  ! ! ! !  this is really old version, instead use the "clientcloudai.py" for fresher code and perhaps better action handling

VM_IP = "YOUR_SERVERS_IP"
VNC_PASS = "YOUR_VNC_PASSWORD"
LM_URL = "YOUR_LOCAL_IP"
MODEL = "YOUR_MODEL"

SYSTEM = """You control a Windows 10 PC (1024x768).
Screenshots have a coordinate ruler — thin yellow lines every 100px with numbers showing X,Y positions. Use these to aim clicks precisely.
A red crosshair shows where the cursor currently is.

X is pointing to right, Y is pointing to down.

X is first, then Y is second in input numbers which you need move your mouse cursor.

For example, To perfect center click on Recycle bin is left top corner of desktop, it needs "40 40" in X,Y positions.
Next, Windows menu button inside the taskbar which is left bottom corner of screen, it needs "24 745" in X,Y positions.
For much small buttons, to be sure without missing, always move the mouse cursor really, really, really slightly until you notice something is changed. (such as button changes color) then you can click.

Use super as Windows key.

Dont expect everything will be succesfully done, expect imperfection, you are not perfectionist by doing actions. Check new screenshot to previous one, if nothing happened, think why.
Each actions or screenshots, please try to do differently and do not get stuck in loop trying to do action that you want and expect something, it will not.

Please ALWAYS think to every screenshots you see, not blindly guessing, thinking every screenshots is actually same. It isn't. Every screenshot is different.
Each actions will trigger screenshot which you will see at.

Reply ONLY in this exact JSON, nothing else:
{"thought": "brief plan", "action": "ACTION", "x": 0, "y": 0, "x2": 0, "y2": 0, "text": ""}

Actions:
- click        left click at x,y
- doubleclick  double click at x,y
- rightclick   right click at x,y
- drag         drag from x,y to x2,y2
- type         type text string (use text field)
- key          press key (use text field: enter, ctrl-c, ctrl-v, super, alt-F4, tab, escape, ctrl-z, super-d, super-e, shift-super-r)
- keydown      hold key down (text field)
- keyup        release held key (text field)
- scroll_up    scroll up at x,y
- scroll_down  scroll down at x,y
- wait         do nothing"""

# ^- very advanced maybe will break some models idk yet just worked on my machine and my choice of models

GRID = 100  # ruler grid spacing in pixels
cursor_pos = [512, 384]

def add_ruler(img_bytes):
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans.ttf", 10)
    except:
        font = ImageFont.load_default()
    for x in range(0, w, GRID):
        draw.line([(x,0),(x,h)], fill=(255,255,0,55), width=1)
        draw.text((x+2,2), str(x), fill=(255,255,0,180), font=font)
    for y in range(0, h, GRID):
        draw.line([(0,y),(w,y)], fill=(255,255,0,55), width=1)
        draw.text((2,y+2), str(y), fill=(255,255,0,180), font=font)
    cx, cy = cursor_pos
    draw.line([(cx-12,cy),(cx+12,cy)], fill=(255,50,50,255), width=2)
    draw.line([(cx,cy-12),(cx,cy+12)], fill=(255,50,50,255), width=2)
    draw.ellipse([(cx-4,cy-4),(cx+4,cy+4)], outline=(255,50,50,255), width=2)
    draw.text((cx+7,cy+7), f"{cx},{cy}", fill=(255,50,50,220), font=font)
    result = Image.alpha_composite(img, overlay).convert("RGB")
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()

def screenshot():
    raw = requests.get(f"http://{VM_IP}:8765/screenshot", timeout=30).content
    return base64.b64encode(add_ruler(raw)).decode()

def vdo(*args):
    # fresh subprocess call every time — avoids connection lost bug
    try:
        result = subprocess.run(
            ["vncdo", "-s", VM_IP, "--password", VNC_PASS] + [str(a) for a in args],
            timeout=8, capture_output=True
        )
        time.sleep(0.3)  # small gap prevents VNC server overload
    except subprocess.TimeoutExpired:
        print("  (vncdo timed out, skipping)")

def act(j):
    a = j.get("action", "wait")
    x, y = j.get("x", 0), j.get("y", 0)
    x2, y2 = j.get("x2", 0), j.get("y2", 0)
    txt = j.get("text", "")

    if a == "click":
        cursor_pos[0], cursor_pos[1] = x, y
        vdo("move", x, y, "click", "1")
    elif a == "doubleclick":
        cursor_pos[0], cursor_pos[1] = x, y
        vdo("move", x, y, "click", "1")
        time.sleep(0.01)
        vdo("move", x, y, "click", "1")
    elif a == "rightclick":
        cursor_pos[0], cursor_pos[1] = x, y
        vdo("move", x, y, "click", "3")
    elif a == "drag":
        cursor_pos[0], cursor_pos[1] = x2, y2
        vdo("move", x, y, "mousedown", "1", "mousemove", x2, y2, "mouseup", "1")
    elif a == "type":
        cursor_pos[0], cursor_pos[1] = x, y
        requests.post(f"http://{VM_IP}:8765/type", json={"text": txt}, timeout=10)
    elif a == "key":
        vdo("key", txt)
    elif a == "keydown":
        vdo("keydown", txt)
    elif a == "keyup":
        vdo("keyup", txt)
    elif a == "scroll_up":
        vdo("move", x, y, "key", "page-up")
    elif a == "scroll_down":
        vdo("move", x, y, "key", "page-down")
    elif a == "wait":
        time.sleep(3)

def think(img_b64, history):
    msgs = [{"role": "system", "content": SYSTEM}]
    text_history = [m for m in history if isinstance(m.get("content"), str)][-3:]
    msgs += text_history
    msgs.append({"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
        {"type": "text", "text": "What do you see? What is your next action?"}
    ]})
    r = requests.post(LM_URL, json={"model": MODEL, "messages": msgs,
                                     "max_tokens": 500, "temperature": 0.7}, timeout=120)
    return r.json()["choices"][0]["message"]["content"]

history = []
goal = input("Goal (Enter = AI decides freely): ").strip()
if not goal:
    goal = "Explore this Windows 10 computer freely. Pick something interesting to build or do. You decide everything."
history.append({"role": "user", "content": goal})
print("🤖 Agent running. Ctrl+C to stop.\n")

while True:
    try:
        print("📸 Screenshot...")
        img = screenshot()
        # save what AI is about to see
        import os
        os.makedirs("frames", exist_ok=True)
        frame_path = f"frames/AIpov.png"
        with open(frame_path, "wb") as f:
            f.write(base64.b64decode(img))
        print(f"   saved → {frame_path}")
        print("🧠 Thinking...")
        response = think(img, history)
        print(f"AI: {response}\n")
        history.append({"role": "assistant", "content": response})
        try:
            act(repair_json(response, return_objects=True))
        except Exception as pe:
            print(f"(parse error: {pe})")
        if len(history) > 20:
            history = history[:1] + history[-10:]
        time.sleep(2)
    except KeyboardInterrupt:
        print("\n🛑 Stopped."); break
    except Exception as ex:
        print(f"Error: {ex}")
        if "Connection" in str(ex) or "timeout" in str(ex):
            print("⚠️ Lost VM connection! Restart server.py in VM then press Enter...")
            input()
        time.sleep(5)
