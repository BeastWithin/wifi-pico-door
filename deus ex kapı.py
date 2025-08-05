import network, machine, socket,time


ssid,password = '000000','0000000'

led = machine.Pin("LED", machine.Pin.OUT, value=1)
pin_1up = machine.Pin(20, machine.Pin.OUT, value=0)
pin_1down = machine.Pin(17, machine.Pin.OUT, value=0)
pin_2up = machine.Pin(10, machine.Pin.OUT, value=0)
pin_2down = machine.Pin (14, machine.Pin.OUT, value=0)

def blink_led(frequency = 0.5, num_blinks = 3):
    for _ in range(num_blinks):
        led.on()
        time.sleep(frequency)
        led.off()
        time.sleep(frequency)

def webpage(temperature, state):
    #Template HTML
    html = f"""

<body>
<div class="endis" >
<div style="width:20%;border-radius:5px;background: linear-gradient(160deg, rgba(55, 56, 88, 1) 0%, rgba(165, 164, 245, 1) 100%);"> <img height="18px" width="18px"align="left" alt="DXlogo" width="40%" src=></img>Surveillance</div>
<div style="width:600px;background-color:#615f62">
Active Window Options <img align="right" alt="DXlogo" width="22%" ></img>
<div>
 <form action="./dr1u"><input class="button1" type="submit" name="door1" value="Up"><input placeholder="{state}" type="text"/></form>
<br>
 <form action="./dr1d"><input class="button1" type="submit" name="door1" value="Down"><input placeholder="{state}" type="text"/></form>
<br>
 <form action="./dr2u"><input class="button1" type="submit" name="door2" value="Up"><input placeholder="{state}" type="text"/></form>
<br>
 <form action="./dr2d"><input class="button1" type="submit" name="door2" value="Down"><input placeholder="{state}" type="text"/></form>
</div>
<div class="cams">
<div >cam1</div>
<div >cam2</div>
<div >cam3</div>
</div>
<div class="mf">
Temperature is {temperature}
</div>
</div>
<div style="transform: translate(90%, 90%);"><input type="submit" value="Disconnect" style="align:right;width:auto"></div>
</div>
</body>
</html>"""
    html2= """           <!DOCTYPE html>
<html>
<head></head>
<style>
.endis		{width:600px}
.cams div	{border-radius:0px;width:33%; float:left; height:144px;border-width:1px;border-color:black;border-style:solid; background-image: ul()}
.cams		{width:100%; overflow:auto;}
body		{color:white; background-color: black;font-family:Arial, Helvetica, sans-serif; }
input		{color:white;background-color:#6c6b69; border-color:white; width: 100px;  clip-path: polygon(0 5px,11px 0,100% 0,100% calc(100% - 5px),calc(100% - 11px) 100%,0 100%); border-width:2px}
.button1		{font-family:Arial, Helvetica, sans-serif;width: 160px; text-align:left; color:white; background-color: #d4d2d4; clip-path: polygon(0 5px,11px 0,100% 0,100% calc(100% - 5px),calc(100% - 11px) 100%,0 100%);}
div			{border-radius: 3px 3px 3px 9px;}
.mf			{text-align:center;background-color:#4b4b4d;position:middle;width:90%;border-width:1px;border-color:black;border-style:solid;border-radius:8px 0px 0px 0px}
</style>"""
    return str(html2)+str(html)

def connect():
    #Connect to WLAN
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        time.sleep(1)
    ip = wlan.ifconfig()[0]
    print(f'Connected on {ip}')
    return ip
    
    
def open_socket(ip):
    # Open a socket
    address = (ip, 80)
    connection = socket.socket()
    connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #bağlantı koptuğunda socket hatası vermesin diye
    connection.bind(address)
    connection.listen(1)
    return connection

def serve(connection):
    #Start a web server
    state = 'OFF'
    led.off()
    temperature = 0
    while True:
        client = connection.accept()[0]
        request = client.recv(1024)
        request = str(request)
        try:
            print(request)
            request = request.split()[1]
        except IndexError:
            pass
        if request == '/dr1u?door1=Up':
            state = "1. kapı açılıyor."
            print(state)
            control_door(state)
        elif request =='/dr1d?door1=Down':
            state = "1. kapı kapanıyor."
            print(state)
            control_door(state)
        elif request =='/dr2u?door2=Up':
            state = "2. kapı açılıyor."
            print(state)
            control_door(state)
        elif request =='/dr2d?door2=Down':
            state = "2. kapı kapanıyor."
            print(state)
            control_door(state)
        temperature = onboard_temp()
        html = webpage(temperature, state)
        client.send(html)
        client.close()


def control_door(cmd):
    if cmd == "1. kapı açılıyor.":
        pin_1up.on()
        blink_led(0.1, 1)
        pin_1up.off()
        
    if cmd == "1. kapı kapanıyor.":
        pin_1down.on()
        blink_led(0.1, 1)
        pin_1down.off()

    if cmd == "2. kapı açılıyor.":
        pin_2up.on()
        blink_led(0.1, 1)
        pin_2up.off()

    if cmd == "2. kapı kapanıyor.":
        pin_2down.on()
        blink_led(0.1, 1)
        pin_2down.off()

def onboard_temp():
    adc = machine.ADC(4)
    ADC_voltage = adc.read_u16() * (3.3 / (65536))
    temp = 27 - (ADC_voltage - 0.706)/0.001721
    return temp

try:
    ip = connect()
    connection = open_socket(ip)
    serve(connection)
except Exception as e:
    print(e)
    connection.close()
finally:
    connection.close()


