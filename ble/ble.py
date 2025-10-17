import platform

import asyncio
import datetime
import json
import math
import time
from datetime import timezone
from typing import Optional
from bleak import BleakClient, BleakScanner, BLEDevice
from bleak.backends.characteristic import BleakGATTCharacteristic
import humanize
import subprocess as sp
from .ble_linux import ble_linux_is_mac_already_connected
from .li_cmds import *



# =========================================
# new bleak-v1.0-compliant Lowell library
# this also works with old v0.2
# =========================================



class ExceptionNotConnected(Exception):
    pass
class ExceptionCommand(Exception):
    pass



GPS_FRM_STR = '{:+.6f}'
UUID_T = 'f0001132-0451-4000-b000-000000000000'
UUID_R = 'f0001131-0451-4000-b000-000000000000'
UUID_S = 'f0001130-0451-4000-b000-000000000000'
SCAN_TIMEOUT_SECS = 10
DEF_TIMEOUT_CMD_SECS = 10
DEBUG = True
g_rx = bytes()
g_tag = ""
g_cli: BleakClient
p_mod = "BLE"
g_print_cmd = False



def _print_cmd_flow(v):
    if g_print_cmd:
        print(v)



def set_print_cmd_flow(b: bool):
    global g_print_cmd
    g_print_cmd = b



def pm(s):
    print(f'{p_mod}: {s}')



def _gui_notification(s):
    try:
        # pop-up at upper right
        c = f'notify-send "Bluetooth" "{s}" -t 3000'
        sp.run(c, shell=True)
    except (Exception, ):
        pass



def _rx_cb(_: BleakGATTCharacteristic, bb: bytearray):
    # just accumulate
    global g_rx
    g_rx += bb



async def ble_scan_slow(adapter='hci0', timeout=SCAN_TIMEOUT_SECS):
    bs = BleakScanner(adapter=adapter)
    await bs.start()
    await asyncio.sleep(timeout)
    await bs.stop()
    # pm(bs.discovered_devices)
    # [BLEDevice(71:C5:75:B7:CB:7A, 71-C5-75-B7-CB-7A), BLEDev...
    return bs.discovered_devices



async def ble_scan_fast_any_mac_in_list(
        ls_macs_wanted,
        adapter='hci0',
        timeout=SCAN_TIMEOUT_SECS
):

    # just tell, do not act here
    ls_macs_wanted = [i.upper() for i in ls_macs_wanted]
    for mtf in ls_macs_wanted:
        if ble_linux_is_mac_already_connected(mtf):
            pm(f'error, scan_fast_any_mac_in_list a mac that is already connected')
            return None

    bs = BleakScanner(adapter=adapter)
    el = time.perf_counter()

    # chunks for scan, must allow to get services at least once
    n = int(timeout / 3)


    # loop with early quit
    pm(f'scan_fast_any_mac_in_list {ls_macs_wanted} for {timeout} seconds')
    for i in range(n):
        await bs.start()
        await asyncio.sleep(3)
        await bs.stop()
        ls_macs_discovered = [i.address for i in bs.discovered_devices]

        try:
            for m in ls_macs_discovered:
                if m in ls_macs_wanted:
                    idx = ls_macs_discovered.index(m)
                    el = int(time.perf_counter() - el)
                    pm(f'fast_scan found mac {m} in {el} seconds')
                    return bs.discovered_devices[idx]

        except ValueError:
            # not in list
            continue

    return None



async def scan_fast_one_mac(mtf, adapter='hci0', timeout=SCAN_TIMEOUT_SECS):
    return await ble_scan_fast_any_mac_in_list([mtf], adapter, timeout)



def is_connected():
    try:
        # just check is defined
        g_cli
        return g_cli and g_cli.is_connected
    except NameError:
        return False



async def connect(dev: BLEDevice, conn_update=False) -> Optional[bool]:

    # dev might be None after a scan
    if not dev:
        pm('error: calling connect() with no dev')
        return False

    # retries embedded in bleak library
    try:
        global g_cli
        g_cli = BleakClient(dev, timeout=20)
        el = time.perf_counter()
        await g_cli.connect()

        # delay to negotiate connection parameters, if so
        if conn_update:
            await asyncio.sleep(1)

        await g_cli.start_notify(UUID_T, _rx_cb)
        el = int(time.perf_counter() - el)
        pm(f"connected in {el} seconds")
        _gui_notification(f'connected to {dev.address}')
        return True
    except (Exception, ) as ex:
        pm(f'error, connect {ex}')



async def disconnect():
    # blueman-applet, blueman-tray may interfere
    try:
        global g_cli
        await g_cli.disconnect()
        pm('disconnected cleanly')
    except (Exception, ):
        # disconnection a bit and seem it failed
        pm('disconnected')



async def connect_by_mac(mac: str, conn_update=False) -> Optional[bool]:

    # retries embedded in bleak library
    try:
        global g_cli
        if platform.system() != 'Darwin':
            g_cli = BleakClient(mac, timeout=20)
        else:
            dev = await BleakScanner.find_device_by_address(mac, cb={"use_bdaddr": True})
            if not dev:
                return False
            g_cli = BleakClient(dev, timeout=20)

        el = time.perf_counter()
        await g_cli.connect()

        # delay to negotiate connection parameters, if so
        if conn_update:
            await asyncio.sleep(1)

        await g_cli.start_notify(UUID_T, _rx_cb)
        el = int(time.perf_counter() - el)
        pm(f"connected in {el} seconds")
        _gui_notification(f'connected to {mac}')
        return True
    except (Exception, ) as ex:
        pm(f'error, connect {ex}')





def _is_cmd_done():
    c = g_tag

    if g_rx == b'ERR':
        return 1

    if c in (
        'ARA',
        'ARF',
        'BAT',
        'BEH',
        'BNA',
        'CFG',
        'CRC',
        'DEL',
        'DHA',
        'DNG',
        'DNS',
        'DWG',
        # no DWF
        # no DWL
        'FDG',
        'FDS',
        'FEX',
        'FRM',
        'GAB',
        'GCC',
        'GCI',
        'GCF',
        'GDO',
        'GDX',
        'GEC',
        'GFV',
        'GLT',
        'GSA',
        'GSC',
        'GSP',
        'GST',
        'GTM',
        'GWC',
        'GWF',
        'HBW',
        'GIN',
        'LED',
        'LOG',
        'MAC',
        'MTS',
        'MUX',
        'OAD',
        'OAF',
        'OSC',
        'RFN',
        'RLI',
        RUN_CMD,
        RWS_CMD,
        'SCC',
        'SCF',
        'SPN',
        'SSP',
        'STM',
        STOP_CMD,
        'STS',
        SWS_CMD,
        'TST',
        'UTM',
        'WAK',
        'WAT',
        'WLI',
        'XOD'
    ):
        return c.encode() in g_rx

    if c == 'DIR':
        return g_rx.endswith(b'\x04\n\r')

    return None



async def _wait_until_cmd_is_done(cmd_timeout):

    # accumulate command answer in notification handler
    till = time.perf_counter() + cmd_timeout
    while is_connected() and time.perf_counter() < till:
        await asyncio.sleep(0.1)

        # consider command finished
        if _is_cmd_done():
            _print_cmd_flow(f'-> {g_rx}')
            return g_rx


    # debug command answer when errors
    e = f'error, _wait_ans cmd {g_tag} timeout {cmd_timeout}'
    pm("\033[91m {}\033[00m".format(e))
    pm("\t\033[91m g_rx: {}\033[00m".format(g_rx))
    if not g_rx:
        return []


    # detect extra errors when developing mobile app
    n = int(len(g_rx) / 2)
    if g_rx[:n] == g_rx[n:]:
        pm('-----------------------------------')
        e = 'error, duplicate answer {} \n' \
            'seems you used PWA recently \n' \
            'and Linux BLE stack got crazy, \n' \
            'just run $ systemctl restart bluetooth'
        pm('-----------------------------------')
        pm(e.format(g_rx))

    # any other error
    return []



async def cmd(c: str, empty=True, timeout=DEF_TIMEOUT_CMD_SECS):

    # send a command via BLE and wait for it to be considered finish
    async def _cmd():
        if not is_connected():
            raise ExceptionNotConnected

        global g_tag
        g_tag = c[:3]
        if empty:
            global g_rx
            g_rx = bytes()
        _print_cmd_flow(f'<- {c}')
        try:
            await g_cli.write_gatt_char(UUID_R, c.encode())

            # -----------------------------------------
            # check the answer to know it has finished
            # -----------------------------------------
            return await _wait_until_cmd_is_done(timeout)
        except (Exception,) as _ex:
            raise ExceptionCommand(_ex)

    # return command answer or None on command exceptions
    try:
        return await _cmd()
    except ExceptionNotConnected:
        pm(f'error, not connected to send cmd {c}')
    except ExceptionCommand as ex:
        pm(f'error, sending cmd {c} -> {ex}')





# =========================================
# commands for lowell instruments loggers
# =========================================


def _cmd_dir_ans_to_dict(ls, ext, match=True):
    if ls is None:
        return {}

    if b'ERR' in ls:
        return b'ERR'

    if type(ext) is str:
        ext = ext.encode()

    files, idx = {}, 0

    # ls: b'\n\r.\t\t\t0\n\r\n\r..\t\t\t0\n\r\n\rMAT.cfg\t\t\t189\n\r\x04\n\r'
    ls = ls.replace(b'System Volume Information\t\t\t0\n\r', b'')
    ls = ls.split()

    while idx < len(ls):
        name = ls[idx]
        if name in [b'\x04']:
            break

        names_to_omit = (
            b'.',
            b'..',
        )

        if type(ext) is str:
            ext = ext.encode()
        # wild-card case
        if ext == b'*' and name not in names_to_omit:
            files[name.decode()] = int(ls[idx + 1])
        # specific extension case
        elif name.endswith(ext) == match and name not in names_to_omit:
            files[name.decode()] = int(ls[idx + 1])
        idx += 2
    return files




def _build_cmd(*args):

    tp_mode = len(str(args[0]).split(' ')) > 1
    c = str(args[0])
    if tp_mode:
        to_send = c
    else:
        c = str(args[0])
        arg = str(args[1]) if len(args) == 2 else ''
        n = '{:02x}'.format(len(arg)) if arg else ''
        to_send = c + ' ' + n + arg
    to_send += chr(13)

    # debug
    # pm(to_send.encode())

    # know command tag, ex: 'STP'
    tag = c[:3]
    return to_send, tag



# for development, adjust rate advertisement logger
async def cmd_ara():
    rv = await cmd('ARA \r')
    ok = rv and len(rv) == 8 and rv.startswith(b'ARA')
    if ok:
        return 0, int(rv.decode()[-1])
    return 1, 0



# for development, adjust rate advertisement fast for 1 minute
async def cmd_arf():
    rv = await cmd('ARF \r')
    ok = rv and len(rv) == 8 and rv.startswith(b'ARF')
    if ok:
        return 0, int(rv.decode()[-1])
    return 1, 0



# gets logger battery in mV, you will need to scale it later
async def cmd_bat():
    rv = await cmd(f'{BAT_CMD} \r')
    ok = rv and len(rv) == 10 and rv.startswith(b'BAT')
    if not ok:
        return 1, 0
    a = rv
    if a and len(a.split()) == 2:
        # a: b'BAT 04BD08'
        _ = a.split()[1].decode()
        b = _[-2:] + _[-4:-2]
        b = int(b, 16)
        return 0, b
    return 1, 0



# when bye, do not advertise faster
async def cmd_bna():
    c, _ = _build_cmd('BNA')
    rv = await cmd(c)
    ok = rv and len(rv) == 6 and rv.startswith(b'BNA 00')
    if ok:
        return 0
    return 1



# sets BEHavior flags
async def cmd_beh(tag, v):
    # ex: BEH 04BCU1\r to activate connection update
    assert len(tag) == 3
    s = f'{tag}{v}'
    c, _ = _build_cmd("BEH", s)
    rv = await cmd(c, timeout=5)
    if rv and rv.startswith(b'BEH'):
        return 0
    return 1



# send configuration string for DOX loggers
async def cmd_cfg(cfg_d):
    assert type(cfg_d) is dict
    s = json.dumps(cfg_d)
    c, _ = _build_cmd(CONFIG_CMD, s)
    rv = await cmd(c)
    ok = rv == b'CFG 00'
    return 0 if ok else 1



# make logger calculate CRC of a file it contains
async def cmd_crc(s):
    c, _ = _build_cmd(CRC_CMD, s)
    rv = await cmd(c)
    ok = rv and len(rv) == 14 and rv.startswith(b'CRC')
    if ok:
        return 0, rv[-8:].decode().lower()
    return 1, ''



# deletes a file
async def cmd_del(s):
    c, _ = _build_cmd("DEL", s)
    rv = await cmd(c)
    return 0 if rv == b'DEL 00' else 1



# delete HSA area
async def cmd_dha():
    rv = await cmd('DHA \r')
    ok = rv == b'DHA 00'
    return 0 if ok else 1



# gets list of files in the logger
async def cmd_dir():
    rv = await cmd('DIR \r')
    if not rv:
        return 1, 'not'
    if rv == b'ERR':
        return 2, 'error'
    if rv and not rv.endswith(b'\x04\n\r'):
        return 3, 'partial'
    ls = _cmd_dir_ans_to_dict(rv, '*', match=True)
    return 0, ls



# deployment name get
async def cmd_dng():
    c, _ = _build_cmd(DEPLOYMENT_NAME_GET_CMD)
    rv = await cmd(c)
    ok = rv and len(rv) == 9 and rv.startswith(b'DNG')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()



# Deployment Name Set
async def cmd_dns(s):
    assert len(s) == 3
    c, _ = _build_cmd(DEPLOYMENT_NAME_SET_CMD, s)
    rv = await cmd(c)
    ok = rv == b'DNS 00'
    return 0 if ok else 1



# targets file to download
async def cmd_dwg(s):
    c, _ = _build_cmd(DWG_FILE_CMD, s)
    rv = await cmd(c)
    return 0 if rv == b'DWG 00' else 1



# download a file in SLOW mode
# does NOT use function cmd()
async def cmd_dwl(file_size) -> tuple:

    # prepare variables pre-DWL
    global g_rx
    g_rx = bytes()
    n = math.ceil(file_size / 2048)
    with open(DEV_SHM_DL_PROGRESS, 'w') as f:
        f.write('0')
    el = time.perf_counter()


    # loop through receiving 2048 bytes chunks
    for i in range(n):
        if not is_connected():
            pm('error, DWL not connected')
            return 1, g_rx

        # -----------------
        # send DWL command
        # -----------------
        try:
            c = 'DWL {:02x}{}\r'.format(len(str(i)), i)
            await g_cli.write_gatt_char(UUID_R, c.encode())
        except (Exception,) as ex:
            pm(f'error, DWL -> {ex}')
            return 1, g_rx


        # don't print progress too often or screws the download timing
        pm('DWL progress {:5.2f} %, chunk {}'.
              format(100 * len(g_rx) / file_size, i))


        # share DL progress with other guys interested in it
        with open(DEV_SHM_DL_PROGRESS, 'w') as f:
            v = '{:5.2f}'.format(100 * len(g_rx) / file_size, i)
            f.write(str(v))

        # download using DWL command (~7 KB/s when no connection update)
        ok = 0
        for _ in range(20):
            await asyncio.sleep(.1)
            if len(g_rx) == (i + 1) * 2048:
                # next chunk
                ok = 1
                break
            if len(g_rx) == file_size:
                # all file done
                ok = 1
                break

        if not ok:
            pm('error, DWL timeout')
            break

    el = int(time.perf_counter() - el) or 1
    pm(f'DWL speed {(file_size / el) / 1000} KB/s')
    rv = 0 if file_size == len(g_rx) else 1
    if rv == 0:
        with open(DEV_SHM_DL_PROGRESS, 'w') as f:
            f.write('100')
    return rv, g_rx



# download a file in FAST mode
# does NOT use function cmd()
async def cmd_dwf(file_size) -> tuple:

    # prepare variables pre-DWF
    global g_rx
    g_rx = bytes()
    # r_set()
    last_n = 0
    el = time.perf_counter()
    with open(DEV_SHM_DL_PROGRESS, 'w') as f:
        f.write('0')
    pm(f'DWF receiving file {file_size} bytes long')
    await g_cli.write_gatt_char(UUID_R, b'DWF \r')


    # receive whole file
    while 1:
        if not is_connected():
            pm('error, DWF disconnected while receiving file')
            return 1, bytes()

        # don't print progress too often or screws download timing
        await asyncio.sleep(1)
        n = len(g_rx)
        # pm('DWF progress', '{:5.2f} %'.format(100 * n / file_size))
        # r_set()

        # share DL progress with other guys interested in it
        with open(DEV_SHM_DL_PROGRESS, 'w') as f:
            v = '{:5.2f}'.format(100 * len(g_rx) / file_size)
            f.write(str(v))

        if n == last_n or n == file_size:
            break
        last_n = n


    # report download result
    rv = 0 if n == file_size else 1
    if rv:
        pm(f'error, DWF received {n} bytes vs file_size {file_size}')
    else:
        el = int(time.perf_counter()) - el
        pm(f'DWF speed {(file_size / el) / 1000} KB/s')
    return rv, g_rx



# First Deployment Get, returns a date
async def cmd_fdg():
    rv = await cmd('FDG \r')
    ok = rv and len(rv) == 25 and rv.startswith(b'FDG')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()



# First Deployment Set as seconds since epoch, in UTC
async def cmd_fds():
    dt = datetime.datetime.fromtimestamp(time.time(), tz=timezone.utc)
    c, _ = _build_cmd(FIRST_DEPLOYMENT_SET_CMD, dt.strftime('%Y/%m/%d %H:%M:%S'))
    rv = await cmd(c)
    return 0 if rv == b'FDS 00' else 1



# does File Exists in logger
async def cmd_fex(s):
    c, _ = _build_cmd(FILE_EXISTS_CMD, s)
    rv = await cmd(c)
    # return 0 == OK if file exists
    return 0 if rv == b'FEX 01' else 1



# format file-system
async def cmd_frm():
    rv = await cmd('FRM \r')
    ok = rv == b'FRM 00'
    return 0 if ok else 1



# get info
async def cmd_gin():
    rv = await cmd('GIN \r')
    ok = rv.startswith(b'GIN')
    if not ok:
        return 1, 0
    print('GIN all rv', rv)
    return 0, rv[6:]




# Get Accelerometer Burst
async def cmd_gab():
    c, _ = _build_cmd("GAB")
    rv = await cmd(c)
    # rv: GAB C0XXYYZZXXYYZZ...
    ok = rv and len(rv) == 198 and rv.startswith(b'GAB')
    if not ok:
        return 1, 0
    return 0, rv[6:]




# Get Sample Accelerometer
async def cmd_gsa():
    c, _ = _build_cmd("GSA")
    rv = await cmd(c)
    # rv: GAB 06XXYYZZ
    ok = rv and len(rv) == 12 and rv.startswith(b'GSA')
    if not ok:
        return 1, 0
    return 0, rv[6:]



# Get Calibration Constants
async def cmd_gcc():
    rv = await cmd('GCC \r')
    # n: number of fields of cc_area v1 29 v2 33
    n = 33
    ok = rv and len(rv) == ((n * 5) + 6) and rv.startswith(b'GCC')
    if ok:
        return 0, rv.decode()
    if rv:
        pm(f'error, bad GCC length {len(rv)} - 6 != {n} - 6')
    else:
        pm(f'error, bad GCC length = None')
    return 1, ""




# Get constants proFiling
async def cmd_gcf():
    rv = await cmd('GCF \r')
    # n: number of fields of cf_area v1 9 v2 13
    n = 9
    ok = rv and len(rv) == ((n * 5) + 6) and rv.startswith(b'GCF')
    if ok:
        return 0, rv.decode()
    return 1, ""



# get dissolved oxygen, v1
async def cmd_gdo():
    c, _ = _build_cmd(OXYGEN_SENSOR_CMD)
    rv = await cmd(c)
    ok = rv and len(rv) == 18 and rv.startswith(b'GDO')
    if not ok:
        return -1, -1, -1
    a = rv
    if a and len(a.split()) == 2:
        # a: b'GDO 0c112233445566'
        _ = a.split()[1].decode()
        dos, dop, dot = _[2:6], _[6:10], _[10:14]
        dos = dos[-2:] + dos[:2]
        dop = dop[-2:] + dop[:2]
        dot = dot[-2:] + dot[:2]
        if dos.isnumeric():
            return dos, dop, dot

    return -1, -1, -1



# get dissolved oxygen, v2
async def cmd_gdx():
    c, _ = _build_cmd('GDX')
    rv = await cmd(c)
    # rv: b'GDX -0.03, -0.41, 17.30'
    ok = rv and rv.startswith(b'GDX') and len(rv.split(b',')) == 3
    if not ok:
        return -1, -1, -1
    a = rv[4:].decode().replace(' ', '').split(',')
    if a and len(a) == 3:
        dos, dop, dot = a
        return dos, dop, dot
    return -1, -1, -1



# get firmware version
async def cmd_gfv():
    rv = await cmd('GFV \r')
    ok = rv and len(rv) == 12 and rv.startswith(b'GFV')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()



# get logger type
async def cmd_glt():
    rv = await cmd('GLT \r')
    ok = rv and rv in (b'GLT DO1', b'GLT DO2', b'GLT TDO', b'GLT CTD')
    # rv: b'ERR' in loggers not supporting this command
    if ok:
        return 0, rv.decode()[-3:]
    return 1, None



# Get Sensor Conductivity
async def cmd_gsc():
    # rv: GSC 101234567890ABCDEF
    rv = await cmd('GSC \r')
    print('gsc rv', rv)
    ok = rv and (len(rv) == 22 or len(rv) == 14) and rv.startswith(b'GSC')
    if not ok:
        return 1, 0
    return 0, rv[6:]



# Get Sensor Pressure
async def cmd_gsp():
    c, _ = _build_cmd(PRESSURE_SENSOR_CMD)
    rv = await cmd(c)
    # rv: GSP 04ABCD
    ok = rv and len(rv) == 10 and rv.startswith(b'GSP')

    if not ok:
        return 1, 0
    a = rv
    if a and len(a.split()) == 2:
        # a: b'GSP 043412'
        _ = a.split()[1].decode()
        p = _[2:6]
        # p: '3412' --> '1234'
        p = p[-2:] + p[:2]
        p = int(p, 16)
        return 0, p
    return 1, 0



# get Sensor Temperature
async def cmd_gst():
    c, _ = _build_cmd(TEMPERATURE_SENSOR_CMD)
    rv = await cmd(c)
    # rv: GST 04ABCD
    ok = rv and len(rv) == 10 and rv.startswith(b'GST')
    if not ok:
        return 1,0

    a = rv
    # a: b'GST 043412'
    if a and len(a.split()) == 2:
        _ = a.split()[1].decode()
        t = _[2:6]
        # t: '3412' --> '1234'
        t = t[-2:] + t[:2]
        t = int(t, 16)
        return 0, t
    return 1, 0




# for developing, get water column (up, down...)
async def cmd_gwc():
    rv = await cmd('GWC \r')
    ok = rv and rv.startswith(b'GWC')
    if ok:
        return 0, rv.decode()
    return 1, ""



# gets logger time in UTC
async def cmd_gtm():
    rv = await cmd('GTM \r')
    ok = rv and len(rv) == 25 and rv.startswith(b'GTM')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()




# Get Wake flag
async def cmd_gwf():
    rv = await cmd('GWF \r')
    if rv == b'GWF 0201':
        return 0, 1
    if rv == b'GWF 0200':
        return 0, 0
    return 1, 0



# has been in water
async def cmd_hbw():
    rv = await cmd('HBW \r')
    if rv == b'HBW 0201':
        return 0, 1
    if rv == b'HBW 0200':
        return 0, 0
    return 1, 0




# makes logger blink its leds
async def cmd_led():
    rv = await cmd('LED \r')
    ok = rv == b'LED 00'
    return 0 if ok else 1



# toggle log output generation
async def cmd_log():
    rv = await cmd(f'{LOG_EN_CMD} \r')
    if rv == b'LOG 0201':
        return 0, 1
    if rv == b'LOG 0200':
        return 0, 0
    return 1, 0



# gets logger Bluetooth mac address
async def cmd_mac():
    rv = await cmd('MAC \r')
    # rv: b'MAC 11D0:2E:AB:D9:29:48'
    ok = rv and len(rv) == 23 and rv.startswith(b'MAC')
    if ok:
        return 0, rv[6:].decode()
    return 1, ''



# gets logger error count
async def cmd_gec():
    rv = await cmd('GEC \r')
    ok = rv and rv.startswith(b'GEC')
    if ok:
        return 0, rv[6:].decode()
    return 1, ''



# route multiplexer
async def cmd_mux():
    rv = await cmd('MUX \r')
    ok = rv and rv.startswith(b'MUX')
    if ok:
        return 0, rv[6:].decode()
    return 1, ''




# conductivity oscillator toggle
async def cmd_osc():
    rv = await cmd('OSC \r')
    ok = rv and rv.startswith(b'OSC')
    if ok:
        return 0, rv[6:].decode()
    return 1, ''



# get bluetooth connection interval
async def cmd_gci():
    rv = await cmd('GCI \r')
    ok = rv and rv.startswith(b'GCI')
    if ok:
        return 0, rv[6:].decode()
    return 1, ''





# creates a dummy file
async def cmd_mts():
    rv = await cmd('MTS \r', timeout=60)
    return 0 if rv == b'MTS 00' else 1


# oad area erase, for development
async def cmd_oad_erase():
    c, _ = _build_cmd('OAE')
    rv = await cmd(c)
    if rv == b'OAE 0200':
        return 0
    return 1



# oad area factory, for development
async def cmd_oad_factory():
    c, _ = _build_cmd('OAF')
    rv = await cmd(c, timeout=60)
    if rv == b'OAF 0200':
        return 0
    return 1




# request current data file name
async def cmd_rfn():
    rv = await cmd('RFN \r')
    ok = rv and rv.startswith(b'RFN')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()



# read memory area
async def cmd_rli():
    info = {}
    all_ok = True
    for each in ['SN', 'BA', 'CA']:
        pm(f'RLI doing {each}')
        c, _ = _build_cmd(LOGGER_INFO_CMD, each)
        # Nick wanted this timeout
        rv = await cmd(c, timeout=5)
        if not rv or rv == b'ERR':
            all_ok = False
        else:
            try:
                info[each] = rv.decode()[6:]
            except (Exception,) as ex:
                pm(f'error_rli: {ex}')
                return 1, info
        await asyncio.sleep(.1)
    if all_ok:
        return 0, info
    return 1, info



# resets the logger, restarts it
async def cmd_rst():
    try:
        await g_cli.write_gatt_char(UUID_R, b'RST \r')
        time.sleep(3)
    except (Exception,) as _ex:
        pm('exception during RST command')



# start the logger
async def cmd_run():
    rv = await cmd('RUN \r')
    ok = rv in (b'RUN 00', b'RUN 0200')
    return 0 if ok else 1



# RUN with STRING
async def cmd_rws(g: tuple):
    lat, lon, _, __ = g
    lat = GPS_FRM_STR.format(float(lat))
    lon = GPS_FRM_STR.format(float(lon))
    c, _ = _build_cmd(RWS_CMD, f'{lat} {lon}')
    rv = await cmd(c, timeout=30)
    ok = rv in (b'RWS 00', b'RWS 0200')
    return 0 if ok else 1



# Set Pressure Number, for profiling
async def cmd_spn(v):
    assert 0 < v < 9
    rv = await cmd('SPN 01{}\r'.format(v))
    ok = rv and len(rv) == 7 and rv.startswith(b'SPN')
    if not ok:
        return 1, ''
    return 0, rv[6:].decode()



# Set Calibration Constants, for PRA, PRB...
async def cmd_scc(tag, v):
    assert len(tag) == 3
    assert len(v) == 5
    c, _ = _build_cmd('SCC', f'{tag}{v}')
    rv = await cmd(c, timeout=30)
    return 0 if rv == b'SCC 00' else 1



# Set Calibration proFiling, for profiling
async def cmd_scf(tag, v):
    assert len(tag) == 3
    assert len(v) == 5
    c, _ = _build_cmd('SCF', f'{tag}{v}')
    rv = await cmd(c, timeout=30)
    return 0 if rv == b'SCF 00' else 1




# Set Sensor Pressure, for debugging and developing
async def cmd_ssp(v):
    v = str(v).zfill(5)
    c, _ = _build_cmd('SSP', v)
    rv = await cmd(c, timeout=5)
    return 0 if rv == b'SSP 00' else 1



# set logger time in UTC
async def cmd_stm():
    # time() gives seconds since epoch, in UTC
    dt = datetime.datetime.fromtimestamp(time.time(), tz=timezone.utc)
    c, _ = _build_cmd(SET_TIME_CMD, dt.strftime('%Y/%m/%d %H:%M:%S'))
    rv = await cmd(c)
    return 0 if rv == b'STM 00' else 1



# stop without string
async def cmd_stp():
    rv = await cmd('STP \r', timeout=30)
    ok = rv in (b'STP 00', b'STP 0200')
    return 0 if ok else 1



# get logger status
async def cmd_sts():
    rv = await cmd('STS \r')
    ok = rv and len(rv) == 8 and rv.startswith(b'STS')
    if ok:
        _ = {
            b'0200': 'running',
            b'0201': 'stopped',
            b'0203': 'delayed',
            # depending on version 'delayed' has 2
            b'0202': 'delayed',
        }
        state = _[rv.split(b' ')[1]]
        return 0, state
    return 1, 'error'



# stop with STRING
async def cmd_sws(g):
    lat, lon, _, __ = g
    lat = GPS_FRM_STR.format(float(lat))
    lon = GPS_FRM_STR.format(float(lon))
    c, _ = _build_cmd(SWS_CMD, f'{lat} {lon}')
    rv = await cmd(c, timeout=30)
    ok = rv in (b'SWS 00', b'SWS 0200')
    return 0 if ok else 1




# command test, for development
async def cmd_tst():
    c, _ = _build_cmd('TST')
    rv = await cmd(c, timeout=60)
    if rv == b'TST 0200':
        return 0
    return 1



# get logger uptime in seconds
async def cmd_utm():
    rv = await cmd('UTM \r')
    ok = rv and len(rv) == 14 and rv.startswith(b'UTM')
    if ok:
        _ = rv.split()[1].decode()
        b = _[-2:] + _[-4:-2] + _[-6:-4] + _[2:4]
        t = int(b, 16)
        s = humanize.naturaldelta(datetime.timedelta(seconds=t))
        return 0, s
    return 1, ''



# sets logger WAKE flag as 1
async def cmd_wak(s):
    assert s in ('on', 'off')
    rv = await cmd(f'{WAKE_CMD} \r')
    if s == 'off' and rv == b'WAK 0200':
        return 0
    if s == 'on' and rv == b'WAK 0201':
        return 0
    # just toggle again :)
    await asyncio.sleep(.1)
    rv = await cmd(f'{WAKE_CMD} \r')
    if s == 'off' and rv == b'WAK 0200':
        return 0
    if s == 'on' and rv == b'WAK 0201':
        return 0
    return 1



# measure the Water sensor
async def cmd_wat():
    c, _ = _build_cmd(WAT_CMD)
    rv = await cmd(c)
    ok = rv and len(rv) == 10 and rv.startswith(b'WAT')
    if not ok:
        return 1, 0
    a = rv
    if a and len(a.split()) == 2:
        _ = a.split()[1].decode()
        w = _[-2:] + _[-4:-2]
        w = int(w, 16)
        return 0, w
    return 1, 0



# write memory area
async def cmd_wli(s):
    # s: SN1234567
    c, _ = _build_cmd(LOGGER_INFO_CMD_W, s)
    rv = await cmd(c)
    ok = rv == b'WLI 00'
    return 0 if ok else 1




# detect logger works with liX files, an old one will return b'ERR'
async def cmd_xod():
    rv = await cmd('XOD \r')
    ok = rv and rv.endswith(b'.LIX')
    return 0 if ok else 1




# async def cmd_ddh_a(g) -> tuple:
#     lat, lon, _, __ = g
#     lat = GPS_FRM_STR.format(float(lat))
#     lon = GPS_FRM_STR.format(float(lon))
#     c, _ = _build_cmd('__A', f'{lat} {lon}')
#     await cmd(c)
#     rv = await self._ans_wait(timeout=30)
#     if not rv:
#         return 1, 'not'
#     if rv == b'ERR':
#         return 2, 'error'
#     if rv and not rv.endswith(b'\x04\n\r'):
#         return 3, 'partial'
#     ls = lowellcmd_dir_ans_to_dict(rv, '*', match=True)
#     return 0, ls
#
#
# async def cmd_ddh_b(rerun):
#     # time() -> seconds since epoch, in UTC
#     rerun = int(rerun)
#     dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
#     pm(f"debug, DDB sent {rerun}{dt.strftime('%Y/%m/%d %H:%M:%S')}")
#     c, _ = _build_cmd('__B', f"{rerun}{dt.strftime('%Y/%m/%d %H:%M:%S')}")
#     await cmd(c)
#     rv = await self._ans_wait()
#     ok = rv and rv.startswith(b'__B')
#     if ok:
#         return 0, rv
#     return 1, bytes()




async def main_ble_tdo():

    # n = input('enter TDO board number you want to test -> ')
    # d = {
    #     '0': "F0:5E:CD:25:92:F1",
    #     '1': "F0:5E:CD:25:A1:16",
    #     '3': "F0:5E:CD:25:92:95"
    # }
    # mac = d[n]
    # print(f'testing TDO #{n}, mac = {mac}')


    mac = "F0:5E:CD:25:97:02"
    print(f'searching mac {mac}')


    dev = await scan_fast_one_mac(mac)
    print(dev)

    # dev = await ble_scan_slow('hci0', 10)

    # if not dev:
    #     pm(f'error, not found {mac} during scan')
    #     return
    #
    rv = await connect(dev)
    if not rv:
        return

    rv = await cmd_gin()
    print('GIN', rv)


    # g = ("-3.333333", "-4.444444", None, None)
    # # await cmd_sws(g)
    # # await cmd_dir()
    # # await cmd_dwg('2508701_LAB_20250919_165930.lid')
    # # bb = await cmd_dwl(28928)
    #
    # # await cmd_gsp()
    # # await cmd_gst()
    #
    #
    # await cmd_stm()
    # await cmd_frm()
    # time.sleep(1)
    # await cmd_rws(g)
    #
    # await disconnect()





async def main_ble_ctd():

    n = input('enter CTD board number you want to test -> ')
    d = {
        '1': "F0:5E:CD:25:92:EA",
        '2': "F0:5E:CD:25:95:E0",
        '3': "F0:5E:CD:25:95:D4",
        '4': "F0:5E:CD:25:A4:21",
        '5': "F0:5E:CD:25:A1:30"
    }
    mac = d[n]
    print(f'testing CTD #{n}, mac = {mac}')


    # ls_dev = await scan()
    # pm(ls_dev)

    dev = await scan_fast_one_mac(mac)
    print(dev)

    if not dev:
        pm(f'error, not found {mac} during scan')
        return

    rv = await connect(dev)
    if not rv:
        return

    await cmd_frm()

    # await cmd_wli('SN2222222')
    # await cmd_stm()
    # await cmd_fds()
    # await cmd_dns('LAB')
    # g = ("-3.333333", "-4.444444", None, None)
    # await cmd_rws(g)

    for i in range(10900):
        rv = await cmd_gsc()
        pm(f'GSC = {rv}')
        time.sleep(1)



    await disconnect()


