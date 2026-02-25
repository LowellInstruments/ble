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
# cacheout is in-memory, redis can be made persistent
CH = Cache(maxsize=300, ttl=120, timer=time.time)
g_iterations = 0



def is_in_smart_lock_out(dev):
    # dev: bleak BLEDevice: dev.address, dev.name
    return False
    # return CH.get(dev.address)



def _rae(cond_error, s):
    if cond_error:
        raise Exception(s)




# - - - - - - - - - - - - - - - - - - - - - -
# stop logger, get its LID, GPS files,
# convert them and disconnect
# - - - - - - - - - - - - - - - - - - - - - -

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



    # stop the logger
    rv = await lc.cmd_sws(g)
    _rae(rv, f'cannot stop logger {dev.name}')
    pm(f'we stopped the logger')



    # logger time
    rv, v = await lc.cmd_utm()
    _rae(rv, f'cannot get uptime')
    pm(f'logger uptime = {v}')
    rv, v = await lc.cmd_gtm()
    _rae(rv, f'cannot get time')
    pm(f'logger time was {v}')
    rv = await lc.cmd_stm()
    _rae(rv, f'cannot set time to {dev.name}')
    dt = datetime.datetime.fromtimestamp(time.time(), tz=timezone.utc)
    pm(f'logger time set {dt.strftime('%Y/%m/%d %H:%M:%S')}')



    # disable logger's UART logs for lower power consumption
    rv, v = await lc.cmd_log()
    _rae(rv, "log command 1")
    if v != 0:
        rv, v = await lc.cmd_log()
        _rae(rv, "log command 2")



    # get list of files in logger file-system
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
            n_dl += 1
            continue


        # target file to download and do it
        pm(f"downloading file {file_name}", color='blue')
        rv = await lc.cmd_dwg(file_name)
        _rae(rv, "dwg")
        rv, file_data = await lc.cmd_dwl(int(file_size))
        _rae(rv, "dwl")



        # save file in our local disk path
        p = str(pathlib.Path(FOL / file_name))
        with open(p, "wb") as f:
            f.write(file_data)
        n_dl += 1



        # convert LID data file to CSV
        if p.endswith('.lid'):
            with contextlib.redirect_stdout(None):
                rv = parse_lid_v2_data_file(p)
                _rae(rv, f"cannot convert lid file {p}")
            bn = os.path.basename(p)
            pm(f"converted lid file {bn} OK", color='green')



    # check we have all logger files locally
    _rae(n_dl != len(d), 'could not download all files')



    # all downloaded, format file-system
    await asyncio.sleep(.5)
    rv = await lc.cmd_frm()
    _rae(rv, "frm")
    pm("logger file-system formatted OK")



    # get sensor Temperature
    rv = await lc.cmd_gst()
    _rae(not rv or rv[0] == 1 or rv[1] == 0xFFFF or rv[1] == 0,
         "temperature sensor")
    pm(f'ADC sensor temperature = {rv[1]}')



    # get sensor Pressure
    rv = await lc.cmd_gsp()
    _rae(not rv or rv[0] == 1 or rv[1] == 0xFFFF or rv[1] == 0,
         "pressure sensor")
    pm(f'ADC sensor pressure = {rv[1]}')



    # get sensor conductivity
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



    # add the logger just downloaded to smart lock-out
    CH.set(dev.address, 1)


    # BLE disconnect from this logger
    await lc.ble_disconnect()




# - - - - - - - - - - - - - - - - - - - - - -
# scan for <logger_type> loggers and
# call the download function
# - - - - - - - - - - - - - - - - - - - - - -

async def main_ble_ctd():

    # scan and get list (dev, adv_name) of ALL BLE devices around
    pm(f'Scanning for devices ...', color='blue')
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
    pm(f'filtered down to {len(ls)} {logger_type} loggers',
       color='blue')



    # download filtered LI CTD devices not in smart lock-out
    for i in ls:
        if is_in_smart_lock_out(i):
            t = int(CH.get_ttl(i.address) or 1)
            pm(f'smart lock-out ({CH.size()}) contains {i.name} ({t} secs), refreshing')
            CH.set(i.address, 1)

        else:
            # gps position
            g = ("-3.333333", "-4.444444", None, None)
            await download_logger(i, g)




# - - - - -
# entry
# - - - - -

def main():

    global g_iterations
    g_iterations = 0
    fn = inspect.currentframe().f_code.co_name

    while 1:
        try:
            pm(f"Run #{g_iterations} of {fn}", color='blue')
            asyncio.run(main_ble_ctd())

            # time to do something else
            print('\n\n\n')
            time.sleep(2)
            g_iterations += 1

        except (Exception, ) as e:
            pm(f'exception {e}', color='red')



if __name__ == '__main__':
    main()
