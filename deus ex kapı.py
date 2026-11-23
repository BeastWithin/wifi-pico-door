# Pico W door controller - hardened DRAFT (not flashed yet)
#
# Changes from the running main.py:
#  * Door commands are POST /api/door with a JSON body (GET no longer moves anything,
#    so a web page or <img> tag on the LAN cannot trigger the doors).
#  * Every /api/* call needs the X-Token header (constant-time compare).
#  * Per-door cooldown and a software interlock (never pulse Up and Down together).
#  * The control page is served from flash (dx.html), not from an f-string in RAM.
#  * Request parsing uses real bytes instead of str(request).split().
#
# Wiring/pulse behaviour is kept identical to main.py: idle HIGH, active-low pulse
# of 0.5 s on the relay pin.
#
# Required line in psw.py (generate the value once, keep it secret):
#   api_token = "<output of: python3 -c 'import secrets;print(secrets.token_urlsafe(32))'>"
# Deploy with:  mpremote cp dx.html :dx.html  &&  mpremote cp main_secure.py :main.py

import network, socket, time, gc, os, json
from machine import WDT, Pin, ADC
from psw import ssid, password, api_token

WEB_FILE = "dx.html"
STATIC_FILES = {
    "/mj13logo.svg": ("mj13logo.svg", "image/svg+xml"),
    "/video-stream.js": ("video-stream.js", "text/javascript"),
    "/video-rtc.js": ("video-rtc.js", "text/javascript"),
}
PULSE_S = 0.5            # same pulse as the original firmware
COOLDOWN_MS = 2000       # minimum gap between commands for the same door
MOVING_MS = 3000         # how long a door shows as MOVING after a command
MAX_HEADER = 2048
MAX_BODY = 512

if not api_token or len(api_token) < 24:
    raise SystemExit("api_token missing or too short in psw.py - refusing to start")

wdt = WDT(timeout=8000)  # hardware watchdog, same as before
led = Pin("LED", Pin.OUT, value=1)

# relay pins, idle HIGH (value=1), pulse LOW (value=0)
RELAY = {
    (1, "up"): Pin(20, Pin.OUT, value=1),
    (1, "down"): Pin(17, Pin.OUT, value=1),
    (2, "up"): Pin(10, Pin.OUT, value=1),
    (2, "down"): Pin(14, Pin.OUT, value=1),
}
last_cmd_ms = {1: None, 2: None}
last_dir = {1: None, 2: None}
wlan = None


def log(*args):
    print(*args)


def onboard_temp():
    adc = ADC(4)
    v = adc.read_u16() * (3.3 / 65536)
    return 27 - (v - 0.706) / 0.001721


def same_secret(a, b):
    if a is None or b is None or len(a) != len(b):
        return False
    diff = 0
    for x, y in zip(a, b):
        diff |= ord(x) ^ ord(y)
    return diff == 0


def authorized(headers):
    return same_secret(headers.get("x-token"), api_token)


def connect():
    global wlan
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.config(pm=0xa11154)
    if not wlan.isconnected():
        wlan.connect(ssid, password)
        tries = 0
        while not wlan.isconnected():
            wdt.feed()
            led.toggle()
            time.sleep(0.8)
            tries += 1
            if tries > 30:
                raise OSError("Wi-Fi timeout")
    led.value(1)
    return wlan.ifconfig()[0]


def open_server(ip):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((ip, 80))
    s.listen(6)  # browsers open several parallel connections
    s.settimeout(2.0)
    return s


def read_request(cl):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = cl.recv(256)
        if not chunk:
            return None
        data += chunk
        if len(data) > MAX_HEADER:
            return None
    cut = data.find(b"\r\n\r\n")
    head = data[:cut].decode("utf-8", "ignore")
    body = data[cut + 4:]
    lines = head.split("\r\n")
    parts = lines[0].split(" ")
    if len(parts) < 2:
        return None
    method, path = parts[0], parts[1]
    headers = {}
    for ln in lines[1:]:
        if ":" in ln:
            k, v = ln.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    n = int(headers.get("content-length", "0"))
    if n > MAX_BODY:
        return None
    while len(body) < n:
        chunk = cl.recv(n - len(body))
        if not chunk:
            break
        body += chunk
    return method, path, headers, body[:n]


def send_all(cl, data):
    # MicroPython socket.send may accept only part of the buffer; keep sending the rest
    mv = memoryview(data)
    while len(mv):
        n = cl.send(mv) or 0
        if n == 0:
            wdt.feed()
            time.sleep_ms(10)
            continue
        mv = mv[n:]


def send(cl, status, ctype, body):
    if isinstance(body, str):
        body = body.encode()
    head = ("HTTP/1.0 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            "Connection: close\r\n\r\n") % (status, ctype, len(body))
    send_all(cl, head.encode())
    send_all(cl, body)


def send_file(cl, fname, ctype):
    try:
        size = os.stat(fname)[6]
    except OSError:
        return send(cl, "404 Not Found", "text/plain", "not found")
    head = ("HTTP/1.0 200 OK\r\nContent-Type: %s\r\nContent-Length: %d\r\n"
            "Cache-Control: no-store\r\nConnection: close\r\n\r\n") % (ctype, size)
    send_all(cl, head.encode())
    with open(fname, "rb") as f:
        while True:
            chunk = f.read(512)
            if not chunk:
                break
            send_all(cl, chunk)
            wdt.feed()


def door_status(door):
    t = last_cmd_ms[door]
    if t is None:
        return "unknown"
    if time.ticks_diff(time.ticks_ms(), t) < MOVING_MS:
        return "moving"
    return "idle"


def pulse(door, direction):
    """Refuse if the opposite relay of the same door is not idle; otherwise pulse."""
    opposite = "down" if direction == "up" else "up"
    if RELAY[(door, opposite)].value() == 0:
        return False, "interlock: opposite relay active"
    now = time.ticks_ms()
    if last_cmd_ms[door] is not None and time.ticks_diff(now, last_cmd_ms[door]) < COOLDOWN_MS:
        return False, "cooldown"
    pin = RELAY[(door, direction)]
    pin.value(0)
    time.sleep(PULSE_S)
    pin.value(1)
    last_cmd_ms[door] = time.ticks_ms()
    last_dir[door] = direction
    return True, "ok"


def handle(cl, addr):
    ip = addr[0] if addr else "?"
    req = read_request(cl)
    if req is None:
        return
    method, full_path, headers, body = req
    path = full_path.split("?", 1)[0]
    wdt.feed()

    if method == "GET" and path in ("/", "/index.html"):
        return send_file(cl, WEB_FILE, "text/html; charset=utf-8")

    if method == "GET" and path in STATIC_FILES:
        fname, ctype = STATIC_FILES[path]
        return send_file(cl, fname, ctype)

    if path.startswith("/api/"):
        if not authorized(headers):
            log("auth fail", ip, method, path)
            time.sleep(1)  # slow down guessing
            return send(cl, "401 Unauthorized", "application/json", '{"error":"unauthorized"}')

        if method == "GET" and path == "/api/status":
            temp = onboard_temp()
            data = {
                "door1": door_status(1),
                "door2": door_status(2),
                "temp": round(temp, 1),
            }
            return send(cl, "200 OK", "application/json", json.dumps(data))

        if method == "POST" and path == "/api/door":
            try:
                cmd = json.loads(body.decode())
                door = int(cmd.get("door"))
                direction = str(cmd.get("dir"))
            except Exception:
                return send(cl, "400 Bad Request", "application/json", '{"error":"bad body"}')
            if door not in (1, 2) or direction not in ("up", "down"):
                return send(cl, "400 Bad Request", "application/json", '{"error":"bad door/dir"}')
            ok, why = pulse(door, direction)
            log("door", door, direction, "from", ip, "->", why)
            if not ok:
                return send(cl, "409 Conflict", "application/json",
                            json.dumps({"ok": False, "message": why}))
            return send(cl, "200 OK", "application/json",
                        json.dumps({"ok": True, "message": "door %d %s" % (door, direction)}))

    return send(cl, "404 Not Found", "text/plain", "not found")


def serve(server, wl):
    while wl.isconnected():
        wdt.feed()
        try:
            cl, addr = server.accept()
        except OSError:
            continue  # accept timeout; loop and feed the watchdog
        try:
            cl.settimeout(2.0)
            handle(cl, addr)
        except Exception as e:
            log("handler error:", e)
        finally:
            cl.close()
            gc.collect()


def main():
    while True:
        server = None
        try:
            wdt.feed()
            ip = connect()
            server = open_server(ip)
            log("server active on", ip)
            serve(server, wlan)
            log("Wi-Fi dropped, reconnecting")
        except Exception as e:
            log("main loop:", e)
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass
            gc.collect()
            time.sleep(2)


main()
