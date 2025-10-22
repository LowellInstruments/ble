import subprocess as sp
import time


def pm(s):
    print(f'BLE: {s}')



def ble_linux_get_bluez_version() -> str:
    c = 'bluetoothctl -v'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    v = rv.stdout.decode()
    # v: b'bluetoothctl: 5.55\n'
    return str(v.replace('\n', '').split(': ')[1])



def ble_linux_reset_antenna_by_index(i: int):
    c = f"sudo hciconfig hci{i} reset"
    sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)



def ble_linux_detect_devices_left_connected_ll():

    # on bad bluetooth state, this takes a long time
    c = 'timeout 2 bluetoothctl info | grep "Connected: yes"'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    if rv.returncode == 124:
        print(f'error, ble_mat_detect_devices_left_connected_ll timeout-ed')

    if rv.returncode == 1:
        # no devices found connected
        return 0

    c = 'bluetoothctl info'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    for lg_type in ('DO-1', 'DO-2', 'TAP1', 'TDO', 'DO1', 'DO2'):
        b = '\tName: {}'.format(lg_type).encode()
        if b in rv.stdout:
            return 1

    return 0



def ble_linux_is_antenna_up_n_running_by_index(i: int):
    for _ in range(10):
        cr = f"hciconfig hci{i} | grep 'UP RUNNING'"
        rv = sp.run(cr, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        if rv.returncode == 0:
            return 0
        time.sleep(.1)
    return 1



def ble_linux_is_mac_already_connected(mac: str):
    # we check at bluez level
    c = f'bluetoothctl info | grep {mac.upper()}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    return rv == 0



def ble_linux_disconnect_by_mac(mac: str):
    # we disconnect at bluez level
    if not ble_linux_is_mac_already_connected(mac):
        return
    c = f'timeout 2 bluetoothctl disconnect {mac}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rv == 0:
        print('mac was already connected, disconnecting')



def ble_linux_disconnect_all():
    # disconnect at bluez level
    c = f'timeout 5 bluetoothctl disconnect'
    return sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode




def _ble_linux_get_interface_type_by_index(i) -> str:
    # probe external ones first
    c = f'hciconfig -a hci{i} | grep Manufacturer | grep Cambridge'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rv == 0:
        return 'external'
    return 'internal'



def ble_linux_enumerate_all_interfaces() -> dict:
    d = {}
    for i in range(10):
        c = f'hciconfig hci{i}'
        rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
        if rv == 0:
            d[i] = _ble_linux_get_interface_type_by_index(i)
    return d




def ble_linux_find_best_interface_index(app, single=False) -> int:
    # we assume:
    #   DDH will grab the lowest  number external interface or internal
    #   BIX will grab the lowest  number external interface or internal
    #   LAT will grab the highest number external interface

    c = 'hciconfig -a | grep Primary | wc -l'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    if rv.returncode:
        print(f'error, ble_linux_find_best_interface_index')
        return -1

    n = int(rv.stdout.decode())
    if n == 1:
        # we only have one interface
        return 0

    ls = list(range(n))
    ls_i = [i for i in ls if _ble_linux_get_interface_type_by_index(i) == 'internal']
    ls_e = [i for i in ls if _ble_linux_get_interface_type_by_index(i) == 'external']


    if app == 'LAT':
        if single:
            # LAT is running without DDH
            if ls_e:
                return ls_e[-1]
            print(f'error, ble_linux_find_best_interface_index for {app}, single, no external ')
            return -1

        # LAT not single, so we will need at least 2 external
        if n < 3:
            print(f'error, ble_linux_find_best_interface_index for {app}, not_single, few external')
            return -1
        return ls_e[-1]

    # BIX and DDH get the immediately after 0
    if ls_e:
        return ls_e[0]
    if ls_i:
        return ls_i[0]
    print(f'error, ble_linux_find_best_interface_index for {app}, single = {single}')
    return -1
