import asyncio
from ble.ble import main_ble_tdo, main_ble_ctd



if __name__ == "__main__":
    asyncio.run(main_ble_ctd())
    # asyncio.run(main_ble_tdo())

