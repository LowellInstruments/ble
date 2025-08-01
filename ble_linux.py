import subprocess as sp



BLE_SCAN_DURATION_S = 1
d_d = {}
p_mod = 'BLE'



def pm(s):
    print(f'{p_mod}: {s}')



def ble_linux_is_mac_already_connected(mac: str):
    # check at bluez level
    c = f'bluetoothctl devices Connected | grep {mac.upper()}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    return rv == 0



def ble_linux_disconnect_by_mac(mac: str):
    # disconnect at bluez level
    if not ble_linux_is_mac_already_connected(mac):
        return
    c = f'bluetoothctl disconnect {mac}'
    rv = sp.run(c, shell=True, stdout=sp.PIPE, stderr=sp.PIPE).returncode
    if rv == 0:
        print('mac was already connected, disconnecting')



def _ble_linux_count_interfaces() -> int:
    c0 = 'hciconfig hci0'
    c1 = 'hciconfig hci1'
    rv0 = sp.run(c0, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode
    rv1 = sp.run(c1, shell=True, stdout=sp.DEVNULL, stderr=sp.DEVNULL).returncode
    return [rv0, rv1].count(0)



def _ble_linux_get_type_of_interface(i) -> str:
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
        if _ble_linux_get_type_of_interface(i) == s:
            return i
    return -1



def ble_linux_find_best_interface():
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
