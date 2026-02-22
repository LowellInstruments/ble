import contextlib
import pathlib
from ble.ble_linux import ble_linux_logger_disconnect_all
from ble.ble_oop import *
import os
from lix.lix import parse_lid_v2_data_file
from cacheout import Cache



os.system('clear')
# ble_linux_logger_disconnect_all()
fol = pathlib.Path.home() / 'Downloads'
ch = Cache(maxsize=300, ttl=3600, timer=time.time)



def is_in_smart_lock_out(dev):
    # dev: bleak BLEDevice: dev.address, dev.name
    return False
    # return ch.get(dev.address)



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


    # get the status logger is in when we meet it
    rv, v = await lc.cmd_sts()
    _rae(rv, f'cannot get status {dev.name}')
    pm(f'logger status = {v}')



    # stop the logger
    rv = await lc.cmd_sws(g)
    _rae(rv, f'cannot stop logger {dev.name}')
    pm(f'we stopped the logger')




    # logger time
    rv, v = await lc.cmd_gtm()
    _rae(rv, f'cannot get time from {dev.name}')
    pm(f'logger time was {v}')
    rv = await lc.cmd_stm()
    _rae(rv, f'cannot set time to {dev.name}')
    dt = datetime.datetime.fromtimestamp(time.time(), tz=timezone.utc)
    pm(f'logger time set {dt.strftime('%Y/%m/%d %H:%M:%S')}')



    # disable logger uart logs for lower power consumption
    rv, v = await lc.cmd_log()
    _rae(rv, "log command 1")
    if v != 0:
        rv, v = await lc.cmd_log()
        _rae(rv, "log command 2")



    # get list of files inside the logger
    rv, d = await lc.cmd_dir()
    _rae(rv, "dir error " + str(rv))
    if d:
        pm(f"logger contains the following {len(d)} files")
        for k,v in d.items():
            pm(f"\t - {k}, {v} bytes")



    # iterate list of files inside the logger
    n_dl = 0
    for file_name, file_size in d.items():

        # delete zero-bytes files
        if file_size == 0:
            rv = await lc.cmd_del(file_name)
            _rae(rv, "del")
            continue


        # target file to download
        pm(f"downloading file {file_name}", color='blue')
        rv = await lc.cmd_dwg(file_name)
        _rae(rv, "dwg")


        # download file
        rv, file_data = await lc.cmd_dwl(int(file_size))
        _rae(rv, "dwl")



        # save file in our local disk path
        p = str(pathlib.Path(fol / file_name))
        with open(p, "wb") as f:
            f.write(file_data)
        n_dl += 1



        # convert file to  CSV
        if p.endswith('.lid'):
            with contextlib.redirect_stdout(None):
                rv = parse_lid_v2_data_file(p)
                _rae(rv, f"cannot convert lid file {p}")
            bn = os.path.basename(p)
            pm(f"converted lid file {bn} OK", color='green')



    # check we got all files locally
    _rae(n_dl != len(d), 'could not download all files')



    # all downloaded, format file-system
    await asyncio.sleep(1)
    rv = await lc.cmd_frm()
    _rae(rv, "frm")
    pm("logger file-system formatted OK")



    # check sensor Temperature
    rv = await lc.cmd_gst()
    _rae(not rv or rv[0] == 1 or rv[1] == 0xFFFF or rv[1] == 0,
         "temperature sensor")
    pm(f'ADC sensor temperature = {rv[1]}')



    # check sensor Pressure
    rv = await lc.cmd_gsp()
    _rae(not rv or rv[0] == 1 or rv[1] == 0xFFFF or rv[1] == 0,
         "pressure sensor")
    pm(f'ADC sensor pressure = {rv[1]}')



    # check sensor conductivity
    if 'CTD' in dev.name:
        rv = await lc.cmd_gsc()
        _rae(not rv or rv[0] == 1 or rv[1] == 0xFFFF or rv[1] == 0,
             'conductivity sensor')
        pm(f'ADC sensor conductivity = {rv[1]}')



    # wake mode
    rv = await lc.cmd_wak('on')
    _rae(rv, "wake mode")
    pm('wake mode ON')



    rv = await lc.cmd_rws(g)
    _rae(rv, 'run with string')
    pm("run OK", color='green')


    # add to smart lock-out
    ch.set(dev.address, 1)

    await lc.ble_disconnect()





async def main_ble_ctd():

    # get a list (dev, adv_name) of all the BLE devices around
    print('\n\n\n')
    pm('scanning for BLE devices...', color='blue')
    d = await ble_scan_slow_with_adv_data(
        adapter='',
        timeout=SCAN_TIMEOUT_SECS
    )
    pm(f'found {len(d)} BLE devices', color='blue')



    # filter by only LI devices
    ls = [v[0] for k,v in d.items() if UUID_S in v[1].service_uuids]
    pm(f'filtered down to {len(ls)} LI loggers', color='blue')



    # filter by only CTD devices
    logger_prefix = 'TDO'
    ls = [i for i in ls if logger_prefix in i.name]
    if not ls:
        pm('no LI loggers found', 'yellow')
        return
    pm(f'filtered down to {len(ls)} {logger_prefix} loggers', color='blue')



    # download all filtered devices
    for i in ls:
        if is_in_smart_lock_out(i):
            print(f'{i.name} is in smart lock out')
        else:
            g = ("-3.333333", "-4.444444", None, None)
            await download_logger(i, g)





if __name__ == '__main__':
    while 1:
        try:
            asyncio.run(main_ble_ctd())
        except (Exception, ) as e:
            pm(f'exception {e}', color='red')
