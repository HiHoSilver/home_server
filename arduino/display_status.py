import serial
import time

def send_msg_to_arduino(arduino_text):
    try:
        arduino = serial.Serial(
            port='COM3',
            baudrate=115200,
            timeout=1,
            write_timeout=1
        )
    except serial.SerialException as e:
        print("Could not open serial port:", e)
        return

    time.sleep(2)  # allow Arduino reset

    try:
        arduino.write((arduino_text + '\n').encode('utf-8'))
        arduino.flush()
    except Exception as e:
        print("Error writing to Arduino:", e)

    arduino.close()
