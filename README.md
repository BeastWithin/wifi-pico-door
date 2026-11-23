# wifi-pico-door

Raspberry Pi Pico W (MicroPython) door controller with a Deus Ex style
surveillance terminal. Two relay outputs per door (Up/Down), a token-protected
HTTP API, and live camera feeds from a go2rtc server.

## Files

- `deus ex kapı.py` - firmware, deployed as `main.py` on the Pico.
- `dx.html` - control page, deployed as `dx.html` on the Pico (served at `/`).
- `LICENSE` - original licence.

## Setup

1. Create `psw.py` on the Pico (not in this repo):

   ```python
   ssid, password = "your-wifi", "your-wifi-password"
   api_token = "<long random string, 24+ chars>"
   ```

   Generate the token with `python3 -c "import secrets;print(secrets.token_urlsafe(32))"`.

2. Upload the files with mpremote:

   ```sh
   mpremote cp "deus ex kapı.py" :main.py
   mpremote cp dx.html :dx.html
   ```

3. Open `http://<pico-ip>/` and enter the token when asked.

The camera URL is set in `dx.html` (`GO2RTC`). The page embeds go2rtc's own
player, because go2rtc only accepts WebSocket connections from its own origin.

## API

- `GET /api/status` (header `X-Token`) - door states and temperature.
- `POST /api/door` (header `X-Token`, JSON `{"door": 1|2, "dir": "up"|"down"}`) -
  pulses the relay for 0.5 s. A 2 s cooldown applies per door, and the opposite
  relay of the same door is checked first (software interlock).

The old `GET /control?...` endpoints were removed, because a plain GET could be
triggered from any web page on the LAN.

## Safety

Keep a hardware interlock between each door's Up and Down relays, and make sure
a power loss leaves the doors in a safe, openable state. The software interlock
does not replace these.
