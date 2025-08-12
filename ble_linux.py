import subprocess as sp
import time



BLE_SCAN_DURATION_S = 1
d_d = {}
p_mod = 'BLE'



def pm(s):
    print(f'{p_mod}: {s}')



def ble_linux_get_bluez_version() -> str:
    c = 'bluetoothctl -v'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
    v = rv.stdout.decode()
    # v: b'bluetoothctl: 5.55\n'
    return str(v.replace('\n', '').split(': ')[1])



def ble_linux_reset_antenna(h: int):
    c = f"sudo hciconfig hci{h} reset"
    sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)



def ble_linux_detect_devices_left_connected_ll():

    # on bad bluetooth state, this takes a long time
    c = 'timeout 2 bluetoothctl info | grep "Connected: yes"'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    if rv.returncode == 124:
        print(f'error: ble_mat_detect_devices_left_connected_ll timeouted')

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



def ble_linux_check_antenna_up_n_running(h_idx: int):
    # for up to 10 seconds, read the BLE interfaces state
    for i in range(10):
        cr = f"hciconfig hci{h_idx} | grep 'UP RUNNING'"
        rv = sp.run(cr, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)
        if rv.returncode == 0:
            return 0
        time.sleep(1)
    return 1



def ble_linux_some_devices_forgot_connected():

    # on bad bluetooth state, this takes long time
    c = 'timeout 2 bluetoothctl info | grep "Connected: yes"'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    if rv.returncode == 124:
        print(f'error, ble_linux_some_devices_forgot_connected timeouted')

    if rv.returncode == 1:
        # no devices found connected
        return None

    c = 'bluetoothctl info'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE)

    for lg_type in ('DO-1', 'DO-2', 'TAP1', 'TDO', 'DO1', 'DO2'):
        b = f'\tName: {lg_type}'.encode()
        if b in rv.stdout:
            print('ble_linux_some_devices_forgot_connected: some connected')
            return lg_type

    return None



def ble_linux_is_mac_already_connected(mac: str):
    # check at bluez level
    c = f'bluetoothctl devices Connected | grep {mac.upper()}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    return rv == 0



def ble_linux_disconnect_by_mac(mac: str):
    # disconnect at bluez level
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



def _ble_linux_count_interfaces() -> int:
    c0 = 'hciconfig hci0'
    c1 = 'hciconfig hci1'
    rv0 = sp.run(c0, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode
    rv1 = sp.run(c1, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode
    return [rv0, rv1].count(0)



def ble_linux_get_type_of_interface(i) -> str:
    cb = f'hciconfig -a hci{i} | grep Manufacturer | grep Cambridge'
    rvb = sp.run(cb, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rvb == 0:
        return 'external'
    ci = f'hciconfig -a hci{i} | grep Manufacturer | grep Intel'
    cc = f'hciconfig -a hci{i} | grep Manufacturer | grep Cypress'
    rvi = sp.run(ci, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    rvc = sp.run(cc, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rvi == 0 or rvc == 0:
        return 'internal'
    return 'unknown'



def _ble_linux_find_this_type_of_interface(s) -> int:
    assert s in ('internal', 'external')
    n = _ble_linux_count_interfaces()
    for i in range(n):
        if ble_linux_get_type_of_interface(i) == s:
            return i
    return -1



def ble_linux_find_best_interface() -> int:
    i = _ble_linux_find_this_type_of_interface('external')
    if i != -1:
        pm(f'using external interface hci{i}')
    else:
        i = _ble_linux_find_this_type_of_interface('internal')
        if i != -1:
            pm(f'using internal interface hci{i}')
        else:
            pm('error: cannot find using any bluetooth interface')
    return i
