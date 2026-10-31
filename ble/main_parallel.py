import asyncio
import platform
from bleak import (BleakGATTCharacteristic, BleakClient, BleakScanner)
from ble.ble_linux import ble_linux_logger_disconnect_all
from rich import console




# tested loggers
mac_do2 = 'F0:5E:CD:25:A0:3D'
mac_ctd = 'F0:5E:CD:25:99:33'
g_d_names = {
    mac_do2: 'do2',
    mac_ctd: 'ctd',
}



console = console.Console()
UUID_R = 'f0001131-0451-4000-b000-000000000000'
UUID_T = 'f0001132-0451-4000-b000-000000000000'
TIME_FRAG_SLEEP_S = 0.01
g_d_mac_to_lc = dict()
g_d_mac_to_ael = dict()
g_bb = bytes()




def _get_ael(mac):
    mac = mac.upper()
    if not mac in g_d_mac_to_ael.keys():
        g_d_mac_to_ael[mac] = asyncio.new_event_loop()
    ael = g_d_mac_to_ael[mac]
    asyncio.set_event_loop(ael)
    return ael



def _lc_add(mac, lc):
    g_d_mac_to_lc[mac.upper()] = lc



def _lc_get(mac):
    return g_d_mac_to_lc[mac.upper()]



def _lc_does_it_exist(mac):
    return mac.upper() in g_d_mac_to_lc.keys()




def _rx_cb(_: BleakGATTCharacteristic, bb: bytearray):
    print('\t->', bytes(bb))
    global g_bb
    g_bb += bytes(bb)




async def _async_ble_smart_sleep(cmd: str):

    def _is_cmd_done():
        done = 0
        if cmd == 'DIR' and g_bb.endswith(b'\x04\n\r'):
            done = 1
        else:
            # easy answers
            tag_bb = cmd[:3].encode()
            if g_bb.startswith(tag_bb):
                done = 1
        return done


    # how long will we wait for an answer for this cmd
    cmd = cmd.replace(' \r', '')
    d_cmd_sleep = {
        'DIR': 5
    }
    t = int(d_cmd_sleep.get(cmd, .2))
    n = int(t / TIME_FRAG_SLEEP_S)
    for i in range(n):
        # during this loop, _rx_cb() is called
        await asyncio.sleep(TIME_FRAG_SLEEP_S)
        if _is_cmd_done():
            break





async def _async_ble_send_cmd_to_mac(mac: str, cmd: str) -> int:

    # ----------------------------------
    # create or recover LC for this MAC
    # ----------------------------------
    lc_already_existed = _lc_does_it_exist(mac)
    if not lc_already_existed:
        console.print(f'<- connecting {g_d_names[mac]} ...', style='bold blue')
        try:
            if platform.system() != 'Darwin':
                # Linux
                lc = BleakClient(mac, timeout=20)
            else:
                # macOS
                dev = await BleakScanner.find_device_by_address(mac, cb={"use_bdaddr": True})
                if not dev:
                    raise Exception(f'error, scanner did not find {mac} around')
                lc = BleakClient(dev, timeout=20)

            # added to our list of logger controllers
            _lc_add(mac, lc)
        except Exception as e:
            print(f'exception: {e}')
            return 1


    # -----------------------------------------
    # CONNECT to LC, send command, wait answer
    # -----------------------------------------
    lc = _lc_get(mac)
    if not lc_already_existed:
        await lc.connect()
        await asyncio.sleep(.5)
        await lc.start_notify(UUID_T, _rx_cb)

    console.print(f"<- {cmd.replace(' \r', '')} to {g_d_names[mac]}", style='bold yellow')
    await lc.write_gatt_char(UUID_R, cmd.encode())
    await _async_ble_smart_sleep(cmd)

    # todo: maybe analyze the command answer here
    return 0



async def _async_ble_disconnect(mac: str):
    lc_already_existed = _lc_does_it_exist(mac)
    if not lc_already_existed:
        return
    console.print(f'<- disconnect {g_d_names[mac]}', style='bold blue')
    lc = _lc_get(mac)
    await lc.disconnect()




# this is NOT async
def ble_cmd(mac: str, cmd: str) -> int:
    global g_bb
    g_bb = bytes()
    if not cmd.endswith(' \r'):
        cmd += ' \r'
    return _get_ael(mac).run_until_complete(_async_ble_send_cmd_to_mac(mac, cmd))



def ble_disconnect(mac: str):
    return _get_ael(mac).run_until_complete(_async_ble_disconnect(mac))



def main():
    ble_linux_logger_disconnect_all()
    ls_cmd = [
        'GLT',
        'GFV',
        'GCI',
        'STS',
        'GTM',
        'UTM',
        'DIR'
    ]
    for c in ls_cmd:
        ble_cmd(mac_do2, c)
        ble_cmd(mac_ctd, c)
    # todo: maybe do ble_disconnect a command inside ble_cmd for more parallellism
    ble_disconnect(mac_do2)
    ble_disconnect(mac_ctd)



if __name__ == '__main__':
    main()

