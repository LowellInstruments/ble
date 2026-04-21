import contextlib
from ble.ble_linux import ble_linux_logger_disconnect_all
from ble.ble_oop import *
import os
from lix.lix import parse_lid_v2_data_file
from cacheout import Cache
import inspect




os.system('clear')
if platform.system() == 'Linux':
    ble_linux_logger_disconnect_all()
FOL = pathlib.Path.home() / 'Downloads'
LS_MACS_WE_WANT = ['F0:5E:CD:25:A2:03']




def _rae(cond_error, s):
    if cond_error:
        raise Exception(s)





async def download_logger(dev, g):

    # output separator
    print('\n')


    # connect to BLE logger
    lc = LoggerBle()
    rv = await lc.ble_connect_by_dev(dev)
    _rae(not rv, f'cannot connect {dev.name} ({dev.address})')
    pm(f'working with logger {dev.name}')



    # get the status logger is in when we meet it
    rv, v = await lc.cmd_sts()
    _rae(rv, f'cannot get status {dev.name}')
    pm(f'logger status = {v}')


    rv = await lc.cmd_ssi('dbar_30')
    _rae(rv, f'cannot set sub_info')



    rv, v = await lc.cmd_gsi()
    _rae(rv, f'cannot get sub_info')
    pm(f'logger sub_info = {v}')





async def main_ble_tdo():

    # scan and get list (dev, adv_name) of ALL BLE devices around
    pm(f'Scanning for devices during {SCAN_TIMEOUT_SECS} seconds ...', color='blue')
    d = await ble_scan_slow_with_adv_data(
        adapter='',
        timeout=SCAN_TIMEOUT_SECS
    )



    # dictionary scan results as list of BLEDevice: dev.address, dev.name
    ls = [v[0] for k,v in d.items()]
    pm(f'found {len(ls)} BLE devices', color='blue')



    # filter by only <logger_type> devices
    logger_type = 'TDO'
    ls = [i for i in ls if i.name and logger_type in i.name]
    if not ls:
        pm('no LI loggers found', 'yellow')
        return
    pm(f'filtered down to {logger_type} loggers = {len(ls)}',
       color='blue')



    # filter by the macs we want to download
    ls = [i for i in ls if i.address in LS_MACS_WE_WANT]
    pm(f'filtered down to wanted loggers = {len(ls)}', color='blue')



    # interact with it
    g = ("-3.333333", "-4.444444", None, None)
    if ls:
        await download_logger(ls[0], g)



if __name__ == '__main__':
    asyncio.run(main_ble_tdo())
