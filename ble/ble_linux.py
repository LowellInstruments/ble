import subprocess as sp
import time



def _pm(s):
    print(f'BLE: {s}')



def ble_linux_get_bluez_version() -> str:
    c = 'bluetoothctl -v'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    v = rv.stdout.decode()
    # v: b'bluetoothctl: 5.55\n'
    return str(v.replace('\n', '').split(': ')[1])



def ble_linux_adapter_reset_by_index(i: int):
    c = f"sudo hciconfig hci{i} reset"
    sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)



def ble_linux_adapter_is_it_up_by_index(i: int):
    for _ in range(10):
        cr = f"hciconfig hci{i} | grep 'UP RUNNING'"
        rv = sp.run(cr, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        if rv.returncode == 0:
            return 0
        time.sleep(.1)
    return 1



def ble_linux_adapter_get_type_by_index(i) -> str:
    # probe external ones first
    c = f'hciconfig -a hci{i} | grep Manufacturer | grep Cambridge'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rv == 0:
        return 'external'
    return 'internal'



def ble_linux_adapter_enumerate_all_of_them() -> dict:
    d = {}
    for i in range(10):
        c = f'hciconfig hci{i}'
        rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
        if rv == 0:
            d[i] = ble_linux_adapter_get_type_by_index(i)
    return d



def ble_linux_adapter_find_best_index_by_app(app, single=False) -> int:

    # we assume:
    #   DDH = lowest  external interface or internal
    #   BIX = lowest  external interface or internal
    #   LAT = highest external interface

    app = app.upper()
    c = 'hciconfig -a | grep Primary | wc -l'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    if rv.returncode:
        _pm(f'error, ble_linux_adapter_find_best_index_by_app {app}')
        return -1

    n = int(rv.stdout.decode())
    if n == 1:
        # we only have one interface
        return 0

    ls = list(range(n))
    ls_i = [i for i in ls if ble_linux_adapter_get_type_by_index(i) == 'internal']
    ls_e = [i for i in ls if ble_linux_adapter_get_type_by_index(i) == 'external']


    if app == 'LAT':
        if single:
            # LAT is running without DDH
            if ls_e:
                return ls_e[-1]
            _pm(f'error, ble_linux_find_best_interface_index for {app}, single, no external ')
            return -1

        # LAT not single, so we will need at least 2 external
        if n < 3:
            _pm(f'error, ble_linux_find_best_interface_index for {app}, not_single, few external')
            return -1
        return ls_e[-1]

    # BIX and DDH get the immediately after 0
    if ls_e:
        return ls_e[0]

    if ls_i:
        return ls_i[0]
    _pm(f'error, ble_linux_find_best_interface_index for {app}, single = {single}')
    return -1




def ble_linux_adapter_find_index_by_type(ad_type: str) -> int:
    c = 'hciconfig -a | grep Primary | wc -l'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    if rv.returncode:
        _pm(f'error, ble_linux_adapter_find_index_by_type')
        return -1

    # n: how many adapters this linux machine has
    n = int(rv.stdout.decode())
    ls = list(range(n))
    ls_i = [i for i in ls if ble_linux_adapter_get_type_by_index(i) == ad_type]
    if ls_i:
        return ls_i[0]
    return -1



def ble_linux_adapter_find_internal_index() -> int:
    return ble_linux_adapter_find_index_by_type('internal')



def ble_linux_adapter_find_external_index() -> int:
    return ble_linux_adapter_find_index_by_type('external')




def ble_linux_logger_was_any_left_connected():

    # on bad bluetooth state, this takes a long time
    c = 'timeout 2 bluetoothctl info | grep "Connected: yes"'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    if rv.returncode == 124:
        _pm(f'error, ble_mat_detect_devices_left_connected_ll timeout-ed')

    if rv.returncode == 1:
        # no devices found connected
        return 0

    # see left connected stuff
    c = 'bluetoothctl info'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    for lg_type in ('DO-1', 'DO-2', 'TAP1', 'TDO', 'DO1', 'DO2'):
        b = '\tName: {}'.format(lg_type).encode()
        if b in rv.stdout:
            return 1
    return 0



def ble_linux_logger_is_this_mac_connected(mac: str):
    # we check at bluez level
    c = f'bluetoothctl info | grep {mac.upper()}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    return rv.returncode == 0



def ble_linux_logger_disconnect_by_mac(mac: str):

    # we disconnect at bluez level
    if not ble_linux_logger_is_this_mac_connected(mac):
        return

    # first build a list of all controller interfaces
    c = 'bluetoothctl list | grep Controller'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    if rv.returncode:
        _pm('error, ble_linux_get_list_of_mac_of_local_controllers')
        return
    ls = rv.stdout.decode().split('\n')
    ls_macs_controllers = [j.split(' ')[1] for i, j in enumerate(ls) if j]

    # for each interface see if this logger mac is connected
    for mc in ls_macs_controllers:
        c = f'timeout 2 echo "select {mc}\ndisconnect {mac}" | bluetoothctl'
        rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        if rv == 0:
            _pm('mac was already connected, disconnecting')



def ble_linux_logger_disconnect_all():
    for i in range(10):
        if not ble_linux_logger_was_any_left_connected():
            break
        print(f'BLE: linux, disconnecting logger {i+1} left connected')
        c = f'timeout 2 bluetoothctl disconnect'
        sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

