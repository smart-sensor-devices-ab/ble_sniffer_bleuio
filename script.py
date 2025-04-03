import serial
import time
import re
from bluetooth_numbers import company
import binascii

# Replace with your actual serial port
#SERIAL_PORT = 'COM3'      # Windows
SERIAL_PORT = '/dev/cu.usbmodem4048FDE52DAF1'  # For Linux/macOS
BAUD_RATE = 9600

def scan_devices(duration=3):
    device_list = []  # list of tuples: (MAC, Name)

    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"\nStarting BLE scan for {duration} seconds...\n")
            ser.write(f'AT+GAPSCAN={duration}\r\n'.encode())
            time.sleep(duration + 1)

            print("Discovered Devices:\n" + "-"*50)
            while ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                print(">>", line)

                # Match: [08] Device: [1]D1:53:C9:A9:8C:D2  RSSI: -55 (HibouAIR)
                match = re.match(r"\[\d+\] Device: \[\d\]([0-9A-F:]{17})\s+RSSI:\s*-?\d+(?:\s+\((.+?)\))?", line)
                if match:
                    mac = match.group(1)
                    name = match.group(2) if match.group(2) else ""
                    device_list.append((mac, name))

        return device_list

    except serial.SerialException as e:
        print("Serial error:", e)
        return []


def scan_target_device(mac_address, duration=3):
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            print(f"\nScanning target device {mac_address} for {duration} seconds...\n")
            cmd = f'AT+SCANTARGET=[1]{mac_address}={duration}\r\n'
            ser.write(cmd.encode())
            time.sleep(duration + 1)

            print("Advertisement Data:\n" + "-"*50)
            adv_data = None  # To hold the first ADV payload

            while ser.in_waiting:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                #print(">>", line)

                # Extract ADV payload from first line like:
                # [MAC] Device Data [ADV]: <HEX>
                if "Device Data [ADV]:" in line and adv_data is None:
                    parts = line.split("Device Data [ADV]:")
                    if len(parts) == 2:
                        adv_data = parts[1].strip()

            if adv_data:
                print("\nDecoding Advertisement Payload...\n")
                decode_ble_adv(adv_data)
            else:
                print("No ADV data found to decode.")

    except serial.SerialException as e:
        print("Serial error:", e)

AD_TYPE_NAMES = {
    0x01: "Flags",
    0x02: "Incomplete 16-bit UUIDs",
    0x03: "Complete 16-bit UUIDs",
    0x08: "Shortened Local Name",
    0x09: "Complete Local Name",
    0x0A: "TX Power Level",
    0x16: "Service Data",
    0xFF: "Manufacturer Specific Data"
}

# Flag bit definitions
FLAGS_MAP = {
    0x01: "LE Limited Discoverable Mode",
    0x02: "LE General Discoverable Mode",
    0x04: "BR/EDR Not Supported",
    0x08: "Simultaneous LE and BR/EDR (Controller)",
    0x10: "Simultaneous LE and BR/EDR (Host)"
}

def decode_ble_adv(hex_str):
    data = bytearray.fromhex(hex_str)
    index = 0

    print(f"Decoding ADV Data: {hex_str}\n{'-'*50}")

    while index < len(data):
        length = data[index]
        if length == 0 or (index + length >= len(data)):
            break

        ad_type = data[index + 1]
        ad_data = data[index + 2: index + 1 + length]
        type_name = AD_TYPE_NAMES.get(ad_type, f"Unknown (0x{ad_type:02X})")

        print(f"\nLength: {length}")
        print(f"Type: 0x{ad_type:02X} ({type_name})")

        if ad_type == 0x01:  # Flags
            flags = ad_data[0]
            print("Flags:")
            for bit, label in FLAGS_MAP.items():
                if flags & bit:
                    print(f"   - {label}")
            print("Device Type Inferred:", end=" ")
            if flags & 0x04:
                print("LE Only")
            elif flags & (0x08 | 0x10):
                print("Dual Mode (LE + BR/EDR)")
            else:
                print("BR/EDR Only or Unknown")

        elif ad_type == 0xFF:  # Manufacturer Specific Data
            if len(ad_data) >= 2:
                company_id = ad_data[0] | (ad_data[1] << 8)
                company_name = company.get(company_id, "Unknown")
                print(f"Company Identifier: 0x{company_id:04X} ({company_name})")
                manufacturer_data = ad_data[2:]
                if manufacturer_data:
                    print("Manufacturer Data:", binascii.hexlify(manufacturer_data).decode())
            else:
                print("Malformed Manufacturer Data")

        else:
            print("Data:", binascii.hexlify(ad_data).decode())

        index += length + 1



if __name__ == "__main__":
    devices = scan_devices()

    if devices:
        print("\nSelect a device to scan further:")
        for idx, (mac, name) in enumerate(devices):
            label = f"{mac} ({name})" if name else mac
            print(f"[{idx}] {label}")

        choice = input("Enter device number to decode(e.g. 0): ").strip()

        try:
            selected_mac = devices[int(choice)][0]
            scan_target_device(selected_mac)
        except (IndexError, ValueError):
            print("Invalid selection. Exiting.")
    else:
        print("No devices found.")


