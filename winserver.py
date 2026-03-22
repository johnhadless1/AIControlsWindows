from flask import Flask, request, send_file, jsonify
import pyautogui, io, time
from PIL import Image

app = Flask(__name__)
pyautogui.FAILSAFE = False

@app.route('/screenshot')
def screenshot():
    img = pyautogui.screenshot()
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/click')
def click():
    x, y = int(request.args['x']), int(request.args['y'])
    pyautogui.click(x, y)
    return jsonify({"ok": True})

@app.route('/doubleclick')
def doubleclick():
    x, y = int(request.args['x']), int(request.args['y'])
    pyautogui.doubleClick(x, y)
    return jsonify({"ok": True})

@app.route('/rightclick')
def rightclick():
    x, y = int(request.args['x']), int(request.args['y'])
    pyautogui.rightClick(x, y)
    return jsonify({"ok": True})

@app.route('/move')
def move():
    x, y = int(request.args['x']), int(request.args['y'])
    pyautogui.moveTo(x, y)
    return jsonify({"ok": True})

@app.route('/drag')
def drag():
    x, y = int(request.args['x']), int(request.args['y'])
    x2, y2 = int(request.args['x2']), int(request.args['y2'])
    pyautogui.moveTo(x, y)
    pyautogui.dragTo(x2, y2, duration=0.4, button='left')
    return jsonify({"ok": True})

@app.route('/type', methods=['POST'])
def type_text():
    text = request.json.get('text', '')
    pyautogui.write(text, interval=0.04)
    return jsonify({"ok": True})

@app.route('/key', methods=['POST'])
def press_key():
    k = request.json.get('key', '')
    # map vncdo/x11 names → pyautogui names
    keymap = {
        'super': 'win', 'super-d': ['win','d'], 'super-e': ['win','e'],
        'shift-super-r': ['shift','win','r'], 'ctrl-c': ['ctrl','c'],
        'ctrl-v': ['ctrl','v'], 'ctrl-z': ['ctrl','z'], 'ctrl-a': ['ctrl','a'],
        'alt-F4': ['alt','f4'], 'enter': 'enter', 'tab': 'tab',
        'escape': 'escape', 'page-up': 'pageup', 'page-down': 'pagedown'
    }
    mapped = keymap.get(k, k)
    if isinstance(mapped, list):
        pyautogui.hotkey(*mapped)
    else:
        pyautogui.press(mapped)
    return jsonify({"ok": True})

@app.route('/scroll')
def scroll():
    x, y = int(request.args.get('x', 512)), int(request.args.get('y', 384))
    direction = int(request.args.get('direction', 3))  # positive=up, negative=down
    pyautogui.scroll(direction, x=x, y=y)
    return jsonify({"ok": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765)
