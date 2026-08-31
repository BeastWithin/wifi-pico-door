import network, machine, socket, time, gc
from machine import WDT, Pin, ADC
from psw import *

# Initialize Hardware Watchdog (8-second timeout)
# If the CPU or Wi-Fi stack freezes for >8s, the hardware forces a reboot.
wdt = WDT(timeout=8000)

led = Pin("LED", Pin.OUT, value=1)
pin_1up = Pin(20, Pin.OUT, value=1)
pin_1down = Pin(17, Pin.OUT, value=1)
pin_2up = Pin(10, Pin.OUT, value=1)
pin_2down = Pin(14, Pin.OUT, value=1)
doorstate = ("1. door opening.", "1. door closing.", "2. door opening.", "2. door closing.")

def blink_led(frequency=0.5, num_blinks=1):
    for _ in range(num_blinks):
        led.toggle()
        time.sleep(frequency)
        led.toggle()
        time.sleep(frequency)

def webpage(temperature, state):
    body = f"""
<body style="fcw bgb ff">
<div class="endis" >
<div style="width:20%;border-radius:5px;background: linear-gradient(160deg, #373858 0%, #a5a4f5 100%);">
<img height="18px" width="18px" align="left" alt="DXlogo" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAMAAABhEH5lAAAAbFBMVEUAAAAAAQQAAAcCAwkEBg4HCRIYGSAAAQ0TFBtmYmANDxhHR0ojJCpZVU8tLTJCQT46OkCDf353dHMOFC05Ny1dWlhxbWeOiYa3s7M1OVGemJUYHTErKCCGgXvJx8f7+/mlpKSAgYvm5+rCwsHuJdquAAAAuUlEQVQY00XPB26EMBAF0Knupne2Jve/Y8jCgqWRpSePvj8AADMh/B/E/QYUJx9jEf7S7abEyKJ6UtF1jsQGx8ciSVfGbKxJ9hAgjcPg+1TKVwBddP298YYuMhVRUdfFReSMFbuMjdJJKgJ+0rrC8xmzwONtZ38mbobpGdt2C7gImp95WmN5BTD8TnZu12yP7yNTeD6qYm1z2HsjkaTXa6l92ae9N2k5LuO9GXzORwFU45zZJgT9tPwDgA8IM61mBcIAAAAASUVORK5CYII=">Surveillance</div>
<div style="width:100%;background-color:#615f62">
Active Window Options <img src="mj13logo.svg" align="right" alt="DXlogo" width="22%" >
<div>
 <form action="./control">
  <input class="bt ff" type="submit" name="door1" value="Up"><input placeholder="{state}" type="text"/><br>
  <input class="bt ff" type="submit" name="door1" value="Down"><input placeholder="{state}" type="text"/><br>
  <input class="bt ff" type="submit" name="door2" value="Up"><input placeholder="{state}" type="text"/><br>
  <input class="bt ff" type="submit" name="door2" value="Down"><input placeholder="{state}" type="text"/>
</div>
 <div class="cams">
  <div>cam1</div><div>cam2</div><div>cam3</div>
 </div>
 <div class="mf">Temperature is {temperature}</div>
</div>
<div style="transform: translate(90%, 90%);"><input type="submit" value="Disconnect" style="align:right;width:auto"></div>
</div>
</body>
</html>
"""
    head = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
.endis {width:60%}
.cams div {float:left; border: solid 1px #000;border-radius:0px;width: 33%;height: 144px;margin: auto;background-image: repeating-radial-gradient(circle at 17% 32%, white, black 0.00085px);animation: back 5s linear infinite;}
.cams {width:100%; overflow:auto;}
input {color:white;background-color:#6c6b69; border: solid 2px #fff; width: 100px;  clip-path: polygon(0 5px,11px 0,100% 0,100% calc(100% - 5px),calc(100% - 11px) 100%,0 100%);}
.bt {font-family:Arial, Helvetica, sans-serif;width: 160px; text-align:left; color:white; background-color: #d4d2d4; clip-path: polygon(0 5px,11px 0,100% 0,100% calc(100% - 5px),calc(100% - 11px) 100%,0 100%);}
div {border-radius: 3px 3px 3px 9px;}
.mf {text-align:center;background-color:#4b4b4d;position:middle;width:90%;border-width:1px;border-color:black;border-style:solid;border-radius:8px 0px 0px 0px}
.bgw {background-color:#fff;} .bgb {background-color:#000;} .fcw {color:#fff;} .fcb {color:#000;} .ff {font-family:Arial, Helvetica, sans-serif; }
@keyframes back {from {background-size: 100% 100%;}to{background-size: 200% 200%;}
}
</style></head>
"""
    return head + body

def connect():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # Disable Wi-Fi power-saving mode (0xa11154) to eliminate dropouts
    wlan.config(pm=0xa11154)

    if not wlan.isconnected():
        print('Connecting to network...')
        wlan.connect(ssid, password)
        retry_count = 0
        while not wlan.isconnected():
            wdt.feed()  # Keep WDT alive while waiting for Wi-Fi association
            print('Waiting for connection...')
            blink_led(0.2, 1)
            time.sleep(0.8)
            retry_count += 1
            if retry_count > 15:
                raise OSError("Wi-Fi connection attempt timed out")

    ip = wlan.ifconfig()[0]
    print(f'Connected on {ip}')
    return wlan, ip

def open_socket(ip):
    address = (ip, 80)
    connection = socket.socket()
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    connection.bind(address)
    connection.listen(1)
    # Set 2.0s socket timeout so connection.accept() won't block indefinitely
    connection.settimeout(2.0)
    return connection

def control_door(cmd):
    if cmd == doorstate[0]:
        pin_1up.toggle()
        time.sleep(0.5)
        pin_1up.toggle()
    elif cmd == doorstate[1]:
        pin_1down.toggle()
        time.sleep(0.5)
        pin_1down.toggle()
    elif cmd == doorstate[2]:
        pin_2up.toggle()
        time.sleep(0.5)
        pin_2up.toggle()
    elif cmd == doorstate[3]:
        pin_2down.toggle()
        time.sleep(0.5)
        pin_2down.toggle()

def onboard_temp():
    adc = ADC(4)
    ADC_voltage = adc.read_u16() * (3.3 / 65536)
    return 27 - (ADC_voltage - 0.706) / 0.001721

def serve(connection, wlan):
    state = 'OFF'
    while wlan.isconnected():
        wdt.feed()  # Reset 8-second watchdog timer on every loop

        try:
            client, addr = connection.accept()
        except OSError:
            # Socket timeout hit; loop again and check wlan.isconnected()
            continue

        try:
            wdt.feed()
            client.settimeout(2.0)
            request = client.recv(1024)
            request = str(request)

            query = ""
            try:
                query = request.split()[1]
                print("**Sorgu** ", query)
            except IndexError:
                pass

            if query == '/control?door1=Up':
                state = doorstate[0]
                control_door(state)
            elif query == '/control?door1=Down':
                state = doorstate[1]
                control_door(state)
            elif query == '/control?door2=Up':
                state = doorstate[2]
                control_door(state)
            elif query == '/control?door2=Down':
                state = doorstate[3]
                control_door(state)

            temperature = onboard_temp()
            html = webpage(temperature, state)
            client.send(html)
        except Exception as err:
            print("Client handler error:", err)
        finally:
            client.close()
            gc.collect()  # Clean up memory after serving the dynamic HTML response

# Outer Execution Loop
while True:
    connection = None
    try:
        wdt.feed()
        wlan, ip = connect()
        connection = open_socket(ip)
        print("Server active on IP:", ip)
        serve(connection, wlan)
        print("Wi-Fi connection dropped. Reconnecting...")
    except Exception as e:
        print("Main loop exception:", e)
    finally:
        if connection:
            try:
                connection.close()
            except Exception:
                pass
        gc.collect()
        time.sleep(2)
