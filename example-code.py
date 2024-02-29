#!/usr/bin/env python

# https://github.com/fesch/CanZE/blob/master/app/src/main/assets/ZOE_Ph2/LBC_Fields.csv
# https://github.com/rand12345/toucan_controller/blob/82afc4d42c77f529766b8e653638e13ea49b4a89/ze50_bms/src/bms.rs
# https://github.com/rand12345/toucan_controller/blob/82afc4d42c77f529766b8e653638e13ea49b4a89/ze50_bms/src/lib.rs#L275
# https://www.waveshare.com/wiki/2-CH_CAN_HAT
# https://pushevs.com/2020/05/14/new-generation-renault-zoe-battery-details/


# Zoe is physically on can0
# nominal_cell_voltage = 3.6
# nominal_pack_voltage = 350
# nominal_cell_amount = 96

import _thread
import threading
import re
import json
import time
import os.path
import sys
import subprocess
import traceback
import helper
import ssl
import can
import math
import RPi.GPIO as GPIO
import struct
from crccheck.crc import Crc8Base


GPIO.setmode(GPIO.BOARD)

hnn
class BMSData:
    charge_discharge_allowed = False
    soc = None
    usable_soc = None
    soh = None
    pack_voltage = None
    max_cell_voltage = None
    min_cell_voltage = None
    delta_cell_voltage = None
    avg_temp = None
    min_temp = None
    max_temp = None
    low_voltage_volts = None
    interlock = None
    kwh_remaining = None
    current = None
    current_offset = None
    max_power = 0
    charging_status = None
    remaining_charge = None
    max_generated = None
    max_available = None
    energy_complete = None
    energy_partial = None

    balance_1 = None
    balance_2 = None
    balance_3 = None
    balance_4 = None
    balance_5 = None
    balance_6 = None

    bms_state = None
    balance_switches = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    request_fan = 0
    mileage = None
    busbars = None
    slave_failures = None
    fan_duty = None
    fan_period = None
    fan_control = None
    fan_speed = None
    temporisation = 0
    time = None
    pack_time = None
    soc_min = None
    soc_max = None
    asic_1 = None
    asic_2 = None
    asic_3 = None
    asic_4 = None
    asic_5 = None

    limit_miniumum_temperature = 2
    limit_maxiumum_temperature = 40
    limit_maximum_current = 20
    limit_minimum_current = -20
    limit_minimum_soc = 4
    limit_maximum_soc = 100

    limit_minimum_cell_voltage = 2.9
    limit_maximum_cell_voltage = 4.2  # 400v / 96 is 4.17V
    limit_minimum_pack_voltage = 300
    limit_maximum_pack_voltage = 404  # max is 399.8v at 99.51%. We only want to charge to 400v

    user_limit_maximum_soc = 90  # Default to 90 but then overriden by HA

    def __init__(self):
        pass


class ZoeCanHandler:
    bus = None
    listener = None
    do_listen = False
    do_frame_sending = False
    do_cell_data = False
    last_message_received = None
    long_counter_100ms = 0

    def __init__(self, controller):
        self.controller = controller
        self.bus = can.Bus(interface="socketcan", channel='can1', receive_own_messages=False)
        can.util.set_logging_level(level_name='info')
        self.last_message_received = helper.get_timestamp()

    def begin_listening(self):
        self.do_listen = True
        self.listener = threading.Thread(target=self.listen)
        self.listener.start()

    def stop_listening(self):
        self.do_listen = False

    def listen(self):
        print("Starting to listen")
        can.Notifier(self.bus, [self.message_received])
        try:
            while self.do_listen:
                time.sleep(1)
                continue  # Run forever.
        except Exception as e:
            print(e)

    def message_received(self, message):
        if message.arbitration_id != 0x18daf1db:
            return

        self.last_message_received = helper.get_timestamp()


        if message.data[2] == 0x90 and message.data[3] == 0x01:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = (appended - 300) / 100
            self.controller.bmsdata.soc = adjusted
        elif message.data[2] == 0x91 and message.data[3] == 0xB9:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = appended / 100
            self.controller.bmsdata.soc_min = adjusted
        elif message.data[2] == 0x91 and message.data[3] == 0xBA:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = appended / 100
            self.controller.bmsdata.soc_max = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x02:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = appended / 100
            self.controller.bmsdata.usable_soc = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x03:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = appended / 100
            self.controller.bmsdata.soh = adjusted
        elif message.data[2] == 0xF4 and message.data[3] == 0x5B:
            adjusted = round(message.data[4] * 0.392156863, 2)
            self.controller.bmsdata.remaining_charge = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x05:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = appended / 10
            self.controller.bmsdata.pack_voltage = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x07:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.000976563, 3)
            self.controller.bmsdata.max_cell_voltage = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x09:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.000976563, 3)
            self.controller.bmsdata.min_cell_voltage = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x0C:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round((appended - 32640) * 0.03125, 3)
            self.controller.bmsdata.current_offset = adjusted
        # Max power
        elif message.data[2] == 0x90 and message.data[3] == 0x0E:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.01, 1)
            self.controller.bmsdata.max_generated = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x0F:  # Maximum Available Power (After Restriction)(Wxx_dchg_pw_lngtrm)
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.01, 1)
            self.controller.bmsdata.max_available = adjusted
        # Current
        elif message.data[2] == 0x92 and message.data[3] == 0x5D:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round((appended - 32640) * 0.03125, 3)
            self.controller.bmsdata.current = adjusted
        elif message.data[2] == 0x91 and message.data[3] == 0xC8:
            appended = self.append_hex_three(message.data[4], message.data[5], message.data[6])
            adjusted = round(appended / 1000, 3)
            self.controller.bmsdata.kwh_remaining = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x11:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.000976563, 2)
            self.controller.bmsdata.low_voltage_volts = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x12:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round((appended - 640) * 0.0625, 2)
            self.controller.bmsdata.avg_temp = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x13:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round((appended - 640) * 0.0625, 2)
            self.controller.bmsdata.min_temp = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x14:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round((appended - 640) * 0.0625, 2)
            self.controller.bmsdata.max_temp = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x1A:
            adjusted = message.data[4]
            self.controller.bmsdata.interlock = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x18:
            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended / 100, 3)
            self.controller.bmsdata.max_power = adjusted
        elif message.data[2] == 0x90 and message.data[3] == 0x19:
            self.controller.bmsdata.charging_status = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x10:
            appended = self.append_hex(message.data[4], message.data[5])
            self.controller.bmsdata.energy_complete = appended
        elif message.data[2] == 0x92 and message.data[3] == 0x15:
            appended = self.append_hex(message.data[4], message.data[5])
            self.controller.bmsdata.energy_partial = appended

        # Balance values
        elif message.data[2] == 0x92 and message.data[3] == 0x4F:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_1 = adjusted
        elif message.data[2] == 0x92 and message.data[3] == 0x50:  # Balance total hours - Total balancing time(Zxx_bal_time_tot)
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_2 = adjusted
        elif message.data[2] == 0x92 and message.data[3] == 0x51:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_3 = adjusted
        elif message.data[2] == 0x92 and message.data[3] == 0x52:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_4 = adjusted
        elif message.data[2] == 0x92 and message.data[3] == 0x62:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_5 = adjusted
        elif message.data[2] == 0x92 and message.data[3] == 0x63:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.000976563, 3)
            self.controller.bmsdata.balance_6 = adjusted
        # BMS Mode / State
        elif message.data[2] == 0x92 and message.data[3] == 0x59:
            self.controller.bmsdata.bms_state = message.data[4]
        # Balance switches
        elif message.data[0] == 0x23:
            for index, seg in enumerate(message.data):
                if index < 4:
                    continue #First few segs are length then irellevant
                self.controller.bmsdata.balance_switches[index - 4] = seg != 0 #Index 0-3
        elif message.data[0] == 0x24:
            for index, seg in enumerate(message.data):
                if index < 1:
                    continue  # First seg is length
                self.controller.bmsdata.balance_switches[index + 3] = seg != 0 #Index 4-10
        elif message.data[0] == 0x25:
            self.controller.bmsdata.balance_switches[11] = message.data[1] != 0 #Index 11



        # Requests/mileage/cooling
        elif message.data[2] == 0x91 and message.data[3] == 0xC9:
            self.controller.bmsdata.request_fan = message.data[4]
        elif message.data[2] == 0x91 and message.data[3] == 0xCC:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            self.controller.bmsdata.busbars = appended
        elif message.data[2] == 0x91 and message.data[3] == 0x29:
            appended = self.append_hex_three(message.data[4], message.data[5], message.data[6])
            self.controller.bmsdata.slave_failures = appended
        elif message.data[2] == 0x91 and message.data[3] == 0xCF:
            appended = self.append_hex_four(message.data[4], message.data[5], message.data[6], message.data[7])
            adjusted = round((appended - 2147483648) * 0.03125, 3)
            self.controller.bmsdata.mileage = adjusted
        elif message.data[2] == 0x91 and message.data[3] == 0xF4:
            appended = self.append_hex(message.data[4], message.data[5])
            self.controller.bmsdata.fan_duty = appended
        elif message.data[2] == 0x91 and message.data[3] == 0xF5:
            self.controller.bmsdata.fan_period = message.data[4]
        elif message.data[2] == 0x91 and message.data[3] == 0xC9:
            self.controller.bmsdata.fan_control = message.data[4]
        elif message.data[2] == 0x91 and message.data[3] == 0x2E:
            self.controller.bmsdata.speed = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x81:
            self.controller.bmsdata.temporisation = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x61:
            self.controller.bmsdata.time = self.append_hex_three(message.data[4], message.data[5], message.data[6])
        elif message.data[2] == 0x92 and message.data[3] == 0xC1:
            self.controller.bmsdata.pack_time = self.append_hex_three(message.data[4], message.data[5], message.data[6])

        elif message.data[2] == 0x92 and message.data[3] == 0x7B:
            self.controller.bmsdata.asic_1 = self.append_hex(message.data[4], message.data[5])
        elif message.data[2] == 0x92 and message.data[3] == 0x7C:
            self.controller.bmsdata.asic_2 = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x7D:
            self.controller.bmsdata.asic_3 = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x7E:
            self.controller.bmsdata.asic_4 = message.data[4]
        elif message.data[2] == 0x92 and message.data[3] == 0x7F:
            self.controller.bmsdata.asic_5 = message.data[4]

        # Cell Voltages
        if message.data[2] == 0x90 and message.data[3] >= 0x21 and message.data[3] <= 0x83:
            if message.data[3] == 0x40 or message.data[3] == 0x60 or message.data[3] == 0x80:
                return  # Ignore "DIDS supported in range"
            offset = 32
            if message.data[3] > 0x40:
                offset = 33
            elif message.data[3] > 0x60:
                offset = 34
            elif message.data[3] > 0x80:
                offset = 35

            appended = self.append_hex(message.data[4], message.data[5])
            adjusted = round(appended * 0.000976563, 3)
            devices = [{
                "device_id": 'cellvoltage-' + str(message.data[3] - offset),
                "name": "Cell Voltage " + str(message.data[3] - offset),
                "data_type": "Volts",
                "value": adjusted
            }]


    def append_hex(self, a, b):  # Append two hex values together like a string
        return (a << 8) | b

    def append_hex_three(self, a, b, c):  # Append three hex values together like a string
        return (a << 16) | (b << 8) | c

    def append_hex_four(self, a, b, c, d):  # Append four hex values together like a string
        return (a << 24) | (b << 16) | (c << 8) | d

    def start_cell_data(self):
        print("Starting cell data thread")
        self.do_cell_data = True
        cell_data_thread = threading.Thread(target=self.request_cell_data)
        cell_data_thread.start()

    def stop_cell_data(self):
        self.do_cell_data = False

    def start_frame_sending(self):
        print("Starting frame sending threads")
        self.do_frame_sending = True
        frame_sending_1000ms = threading.Thread(target=self.frame_sending_1000ms_thread)
        frame_sending_1000ms.start()
        frame_sending_100ms = threading.Thread(target=self.frame_sending_100ms_thread)
        frame_sending_100ms.start()
        frame_sending_10ms = threading.Thread(target=self.frame_sending_10ms_thread)
        frame_sending_10ms.start()

    def stop_frame_sending(self):
        self.do_frame_sending = False

    def increase_to_16(self, in_int):
        if in_int <= 14:
            return in_int + 1
        else:
            return 0

    def increase_hex_full(self, in_int):
        if in_int < 255:
            return in_int + 1
        else:
            return 1

    def generate_checksum(self, payload, crc_xor):
        our_payload = payload
        if len(our_payload) == 5:
            our_payload.append(0x00)
            our_payload.append(0x00)
        crc = Crc8Base
        crc._poly = 0x1D
        crc._reflect_input = False
        crc._reflect_output = False
        crc._initvalue = 0x0
        crc._xor_output = crc_xor
        output_int = crc.calc(our_payload)
        return output_int

    def slow_increment(self, value, divisor):
        if self.long_counter_100ms % divisor == 0:
            return self.increase_hex_full(value)
        return value

    def frame_sending_1000ms_thread(self):
        print("Starting to loop 1000ms frame_sending")
        while self.do_frame_sending:
            if not self.controller.frame_sending_allowed:
                time.sleep(1)
                continue

            # Vehicle ID
            Payload_5F8 = [0x16, 0x44, 0x90, 0x8f]
            self.bus.send(can.Message(arbitration_id=0x5F8, data=Payload_5F8, is_extended_id=False))

            # Total boost time
            Payload_6BF = [0x0, 0x0, 0x0]
            self.bus.send(can.Message(arbitration_id=0x6BF, data=Payload_6BF, is_extended_id=False))

            time.sleep(1)

    Payload_373 = [0xC1, 0x40, 'ALT', 'ALT', 0x0, 0x1, 0xff, 0xe3]
    Payload_375 = [0x02, 0x29, 0x00, 0xBF, 0xFE, 0x64, 0x0, 0xff]

    def frame_sending_100ms_thread(self):
        print("Starting to loop 100ms frame_sending")

        counter = 0
        self.long_counter_100ms = 0
        alternate_373_counter = 0
        alternate_373_flipper = 0
        Vehicle_production_time = 1577836800

        while self.do_frame_sending:
            if not self.controller.frame_sending_allowed:
                time.sleep(1)
                continue
            counter = self.increase_to_16(counter)
            alternate_373_counter += 1
            self.long_counter_100ms += 1

            Seconds_since_production = time.time() - 1614454107
            Minutes_since_production = Seconds_since_production / 60
            Year_unfloored = Minutes_since_production / 255 / 255
            Year_seg = math.floor(Year_unfloored)
            Remainder_years = Year_unfloored - Year_seg
            Remainder_hours_unfloored = (Remainder_years * 255)
            Hour_seg = math.floor(Remainder_hours_unfloored)
            Remainder_hours = Remainder_hours_unfloored - Hour_seg
            Minutes_seg = math.floor(Remainder_hours * 255)

            if alternate_373_counter >= 4:
                alternate_373_counter = 0
                alternate_373_flipper = not alternate_373_flipper

            # 373 HEVC Wakeup. Statusish
            self.Payload_373[0] = 0xc1 if self.controller.streaming_373 else 0x1
            self.Payload_373[2] = (0x5D if alternate_373_flipper else 0xB2)
            self.Payload_373[3] = (0x5D if not alternate_373_flipper else 0xB2)
            self.bus.send(can.Message(arbitration_id=0x373, data=self.Payload_373, is_extended_id=False))

            # 375 HEVC Statusish.
            self.bus.send(can.Message(arbitration_id=0x375, data=self.Payload_375, is_extended_id=False))

            # 376 Distance/Time. Accuracy is important
            Payload_376 = [Year_seg, Hour_seg, Minutes_seg, Year_seg, Hour_seg, Minutes_seg, 0x4A, 0x54]
            self.bus.send(can.Message(arbitration_id=0x376, data=Payload_376, is_extended_id=False))

            # 440 Relay/12V Voltage/
            Segment_1_440 = 0x31 if self.controller.latch_440 else 0x32  # Options are 0x30/31/32/33. 0x31:1=latched. 0x32:2= unlatched for sleep transient and balance
            Payload_440 = [0x00, Segment_1_440, counter << 4, 0x1f, 0xfe, 0xff, 0x82]
            Payload_440.insert(2, self.generate_checksum(Payload_440, 0xAB))
            self.bus.send(can.Message(arbitration_id=0x440, data=Payload_440, is_extended_id=False))

            # 4CE HEVC Charging type
            Charging_type = (self.controller.charging_mode * 2) << 4 | 0xf  # 2f=ISO charge
            Payload_4CE = [Charging_type, 0xff, 0xff, 0xff, 0xDF, 0xff, (0xE << 4) | counter]
            Payload_4CE.append(self.generate_checksum(Payload_4CE, 0xA))
            self.bus.send(can.Message(arbitration_id=0x4CE, data=Payload_4CE, is_extended_id=False))

            # 4FB Relay ish(missing on DG)
            Segment_X_4FB = 0x04  # Only seen 0x4
            Payload_4FB = [counter, 0x0, Segment_X_4FB, 0x00, 0x00]
            Payload_4FB.insert(5, self.generate_checksum(Payload_4FB, 0x82))
            self.bus.send(can.Message(arbitration_id=0x4FB, data=Payload_4FB, is_extended_id=False))

            time.sleep(0.1)

    def frame_sending_10ms_thread(self):
        print("Starting to loop 10ms frame_sending")
        counter = 0
        while self.do_frame_sending:
            if not self.controller.frame_sending_allowed:
                time.sleep(1)
                continue
            counter = self.increase_to_16(counter)

            # 0EE Pedal
            Pedal_1 = 0x00
            Pedal_2 = 0x00
            Payload_0EE = [0x32, 0x03, 0x20, 0xAA, Pedal_1, Pedal_2, counter]
            Payload_0EE.insert(7, self.generate_checksum(Payload_0EE, 0xAC))
            self.bus.send(can.Message(arbitration_id=0x0EE, data=Payload_0EE, is_extended_id=False))

            # OF5 Current ?
            OF5_Start = 0x7C  # 7D Common
            Payload_0F5 = [OF5_Start, counter, 0xff, 0xD7, 0xF8, 0x7D, 0x10]
            Payload_0F5.insert(2, self.generate_checksum(Payload_0F5, 0x16))
            self.bus.send(can.Message(arbitration_id=0x0F5, data=Payload_0F5, is_extended_id=False))

            # 133 Vehicle speed
            Payload_133 = [0xB1, 0xA6, counter << 2, 0x00, 0x06, 0x05, 0x05]
            Payload_133.insert(3, self.generate_checksum(Payload_133, 0x4E))
            self.bus.send(can.Message(arbitration_id=0x133, data=Payload_133, is_extended_id=False))

            time.sleep(0.01)

    def request_data(self):
        if not self.controller.frame_requesting_allowed:
            return True

        # https://en.wikipedia.org/wiki/Unified_Diagnostic_Services
        # https://www.csselectronics.com/pages/uds-protocol-tutorial-unified-diagnostic-services
        # https://www.csselectronics.com/cdn/shop/files/Unified-Diagnostic-Services-UDS-overview-0x22-0x19.png
        payloads = [
            # The first segment of request or response is always the length
            ["soc", [0x03, 0x22, 0x90, 0x01, 0xff, 0xff, 0xff, 0xff]],  # [05] [62 90 01] [23 3A] AA AA
            ["usable_soc", [0x03, 0x22, 0x90, 0x02, 0xff, 0xff, 0xff, 0xff]],
            ["soh", [0x03, 0x22, 0x90, 0x03, 0xff, 0xff, 0xff, 0xff]],
            ["pack_voltage", [0x03, 0x22, 0x90, 0x05, 0xff, 0xff, 0xff, 0xff]],
            ["max_cell_voltage", [0x03, 0x22, 0x90, 0x07, 0xff, 0xff, 0xff, 0xff]],
            ["min_cell_voltage", [0x03, 0x22, 0x90, 0x09, 0xff, 0xff, 0xff, 0xff]],
            ["12v", [0x03, 0x22, 0x90, 0x11, 0xff, 0xff, 0xff, 0xff]],
            ["avg_temp", [0x03, 0x22, 0x90, 0x12, 0xff, 0xff, 0xff, 0xff]],
            ["min_temp", [0x03, 0x22, 0x90, 0x13, 0xff, 0xff, 0xff, 0xff]],  #
            ["max_temp", [0x03, 0x22, 0x90, 0x14, 0xff, 0xff, 0xff, 0xff]],  # 05 [62 90 14] 03 30 AA AA
            ["max_power", [0x03, 0x22, 0x90, 0x18, 0xff, 0xff, 0xff, 0xff]],  # 05 [62 90 18] 1B DD AA AA
            ["interlock", [0x03, 0x22, 0x90, 0x1A, 0xff, 0xff, 0xff, 0xff]],  # [04] [62 90 1A] 02 AA AA AA
            ["kwh", [0x03, 0x22, 0x91, 0xC8, 0xff, 0xff, 0xff, 0xff]],  #
            ["current", [0x03, 0x22, 0x92, 0x5D, 0xff, 0xff, 0xff, 0xff]],
            ["current_offset", [0x03, 0x22, 0x90, 0x0C, 0xff, 0xff, 0xff, 0xff]],  # 05 [62 92 5D] 7E 50 AA AA
            ["max_generated", [0x03, 0x22, 0x90, 0x0E, 0xff, 0xff, 0xff, 0xff]],  #
            ["max_available", [0x03, 0x22, 0x90, 0x0F, 0xff, 0xff, 0xff, 0xff]],
            ["current_voltage", [0x03, 0x22, 0x91, 0x30, 0xff, 0xff, 0xff, 0xff]],
            ["charging_status", [0x03, 0x22, 0x90, 0x19, 0xff, 0xff, 0xff, 0xff]],  # [04] [62 90 19] 00 AA AA AA
            ["remaining_charge", [0x03, 0x22, 0xF4, 0x5B, 0xff, 0xff, 0xff, 0xff]],  # 04 62 F4 5B D1 AA AA AA

            ["balance_capacity_total", [0x03, 0x22, 0x92, 0x4F, 0xff, 0xff, 0xff, 0xff]],  # 07 [62 92 4F] [80 01 27 00]
            ["balance_time_total", [0x03, 0x22, 0x92, 0x50, 0xff, 0xff, 0xff, 0xff]],
            ["balance_capacity_sleep", [0x03, 0x22, 0x92, 0x51, 0xff, 0xff, 0xff, 0xff]],  # gives value
            ["balance_time_sleep", [0x03, 0x22, 0x92, 0x52, 0xff, 0xff, 0xff, 0xff]],  # gives value
            ["balance_capacity_wake", [0x03, 0x22, 0x92, 0x62, 0xff, 0xff, 0xff, 0xff]],  # 0
            ["balance_time_wake", [0x03, 0x22, 0x92, 0x63, 0xff, 0xff, 0xff, 0xff]],  # 0

            ["bms_state", [0x03, 0x22, 0x92, 0x59, 0xff, 0xff, 0xff, 0xff]],
            ["balance_switches", [0x03, 0x22, 0x91, 0x2B, 0xff, 0xff, 0xff, 0xff]],
            ["flow_control", [0x30, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]],
            ["energy_complete", [0x03, 0x22, 0x92, 0x10, 0xff, 0xff, 0xff, 0xff]],
            ["energy_partial", [0x03, 0x22, 0x92, 0x15, 0xff, 0xff, 0xff, 0xff]],

            ["request_fan", [0x03, 0x22, 0x91, 0xC9, 0xff, 0xff, 0xff, 0xff]],  # 04 [62 91 C9] [00] AA AA AA or no reply

            ["slave_failures", [0x03, 0x22, 0x91, 0x29, 0xff, 0xff, 0xff, 0xff]],  # [07] [62 91 29] [00 00 00 00]
            ["mileage", [0x03, 0x22, 0x91, 0xCF, 0xff, 0xff, 0xff, 0xff]],  # [07] [62 91 CF] 96 B1 E0 3D = 2528239677=11,898,625km [07] [62 91 CF] 97 17 99 C0 2534906304=12,106,958km

            ["fan_speed", [0x03, 0x22, 0x91, 0x2E, 0xff, 0xff, 0xff, 0xff]],  #
            ["fan_period", [0x03, 0x22, 0x91, 0xF4, 0xff, 0xff, 0xff, 0xff]],  # 05 [62 91 F4] [03 E8] AA AA
            ["fan_control", [0x03, 0x22, 0x91, 0xC9, 0xff, 0xff, 0xff, 0xff]],
            ["fan_duty", [0x03, 0x22, 0x91, 0xF5, 0xff, 0xff, 0xff, 0xff]],  # 04 [62 91 F5] [03] AA AA AA

            ["temporisation", [0x03, 0x22, 0x92, 0x81, 0xff, 0xff, 0xff, 0xff]],  # 04 62 92 5A 00 AA AA AA
            ["time", [0x03, 0x22, 0x92, 0x61, 0xff, 0xff, 0xff, 0xff]],  #
            ["pack_time", [0x03, 0x22, 0x91, 0xC1, 0xff, 0xff, 0xff, 0xff]],  #
            ["soc_min", [0x03, 0x22, 0x91, 0xB9, 0xff, 0xff, 0xff, 0xff]],  #
            ["soc_max", [0x03, 0x22, 0x91, 0xBA, 0xff, 0xff, 0xff, 0xff]],  #

            ["asic1", [0x03, 0x22, 0x92, 0x7B, 0xff, 0xff, 0xff, 0xff]],  #
            ["asic2", [0x03, 0x22, 0x92, 0x7C, 0xff, 0xff, 0xff, 0xff]],  #
            ["asic3", [0x03, 0x22, 0x92, 0x7D, 0xff, 0xff, 0xff, 0xff]],  #
            ["asic4", [0x03, 0x22, 0x92, 0x7E, 0xff, 0xff, 0xff, 0xff]],  #
            ["asic5", [0x03, 0x22, 0x92, 0x7F, 0xff, 0xff, 0xff, 0xff]],  #
        ]

        try:

            for payload in payloads:
                msg = can.Message(
                    arbitration_id=0x18DADBF1, data=payload[1], is_extended_id=True
                )
                self.bus.send(msg)
                time.sleep(0.2)
            return True
        except Exception as e:
            print("Error sending payloads", e)
            return False

    def request_cell_data(self):
        if not self.controller.frame_requesting_allowed:
            return True

        payloads = []
        for i in range(33, 131):  # Cell 1 to 96
            payloads.append([0x03, 0x22, 0x90, i, 0xff, 0xff, 0xff, 0xff])

        while self.do_cell_data:
            try:
                for payload in payloads:  # Takes 30 seconds to run
                    self.bus.send(can.Message(
                        arbitration_id=0x18DADBF1, data=payload, is_extended_id=True
                    ))
                    time.sleep(0.2)
            except Exception as e:
                print("Error sending payloads", e)
            time.sleep(120)  # Wait 120 seconds


class Penthouse:
    relay_pins = [31, 35]
    opto_pins = [36, 37, 38]
    controller = None
    pwm = None

    def __init__(self, controller):
        self.controller = controller
        # Setup relays
        for relay_pin in self.relay_pins:
            initial_GPIO = GPIO.LOW
            if relay_pin == 35 and not self.controller.power_cycle_allowed:
                initial_GPIO = GPIO.HIGH
            GPIO.setup(relay_pin, GPIO.OUT, initial=initial_GPIO)
        # Setup Opto
        for opto_pin in self.opto_pins:
            GPIO.setup(opto_pin, GPIO.IN)
        # Setup PWM
        import Adafruit_PCA9685
        self.pwm = Adafruit_PCA9685.PCA9685()
        self.pwm.set_pwm_freq(1000)


    def disable_contactor(self):
        # print("Opening contactor")
        self.pwm.set_pwm(15, 0, 0)  # Run at 0%

    def enable_contactor(self):
        print("Closing contactor")
        self.pwm.set_pwm(15, 0, 4095)  # Run at 100%

    def stabilise_contactor(self):
        print("Stabilising contactor")
        self.pwm.set_pwm(15, 0, 2048)  # Run at 50%

    def is_contactor_on(self):
        return GPIO.input(38) == 0

    def enable_12v(self):
        print("Enabling 12V")
        GPIO.output(35, GPIO.HIGH)

    def disable_12v(self):
        if self.controller.power_cycle_allowed:
            GPIO.output(35, GPIO.LOW)

    def is_12v_on(self):
        return GPIO.input(36) == 0

    def enable_precharge(self):
        GPIO.output(31, GPIO.HIGH)

    def disable_precharge(self):
        GPIO.output(31, GPIO.LOW)

    def is_precharge_on(self):
        return GPIO.input(37) == 0


class Controller:
    battery_allowed = False
    frame_sending_allowed = False
    frame_requesting_allowed = False
    latch_440 = False
    streaming_373 = False
    power_cycle_allowed = False
    charging_mode = 0
    last_battery_allowed_confirmation = 0
    stage_id_map = {
        0: "Stopped",
        10: "Starting",
        12: "Fatal error",
        20: "Opto check",
        25: "Waiting for 12V allowed",
        30: "Enable 12V",
        35: "Opto check 2",
        40: "Setup Canbus",
        50: "Talk on canbus",
        55: "Waiting for battery allowed",
        60: "Safety Check",
        70: "Precharge On",
        80: "Contactor",
        90: "Precharge off",
        100: "Stabilise Contactor",
        110: "Opto check 3",
        120: "Running",
    };
    stage = 0
    fatal_error = ''

    def __init__(self):
        print("Main controller")
        self.bmsdata = BMSData()
        self.penthouse = Penthouse(self)
        self.zoe_handler = ZoeCanHandler(self)

        self.start_control_loop()

    def set_battery_allowed(self, in_bool):
        self.last_battery_allowed_confirmation = helper.get_timestamp()
        if in_bool and not self.battery_allowed:  # Was disabled, now enabled
            self.battery_allowed = True
            print("Battery allowed")

        elif not in_bool and self.battery_allowed:  # Was enabled, now disabled
            self.battery_allowed = False
            print("Battery not allowed")

    def set_frame_sending_allowed(self, in_bool):
        self.frame_sending_allowed = in_bool

    def set_frame_requesting_allowed(self, in_bool):
        self.frame_requesting_allowed = in_bool

    def set_power_cycle_allowed(self, in_bool):
        self.power_cycle_allowed = in_bool

    def set_charge_discharge_allowed(self, in_bool):
        self.bmsdata.charge_discharge_allowed = in_bool

    def set_440_latch(self, in_bool):
        self.latch_440 = in_bool

    def set_373_streaming(self, in_bool):
        self.streaming_373 = in_bool

    def set_max_soc(self, max_soc):
        if max_soc < 101 and max_soc > 10:
            self.bmsdata.user_limit_maximum_soc = max_soc
        else:
            print("Invalid max SOC")

    def set_charging_mode(self, param):
        if param >= 0:
            self.charging_mode = param
        else:
            print("Invalid charging mode")

    def set_stage(self, stage):
        self.stage = stage
        print("Setting stage to ", stage, ": ", self.stage_id_map[stage])

    def start_control_loop(self):
        self.set_stage(10);
        control_loop_thread = threading.Thread(target=self._do_run)
        control_loop_thread.start()

    def _do_run(self):
        while True:
            self._run()
            time.sleep(1)

    def safety_checks(self):
        bms = self.bmsdata

        # SOC
        if bms.soc is not None and (bms.soc > bms.limit_maximum_soc or bms.soc < bms.limit_minimum_soc):
            return self.set_fatal_error("SOC out of range " + str(bms.soc))
        elif bms.usable_soc is not None and bms.usable_soc > 0 and (
                bms.usable_soc > bms.limit_maximum_soc or bms.usable_soc < bms.limit_minimum_soc):
            return self.set_fatal_error("Usable SOC out of range: " + str(bms.usable_soc))

        # Voltage
        elif bms.pack_voltage is not None and bms.pack_voltage > 1 and (
                bms.pack_voltage < bms.limit_minimum_pack_voltage or bms.pack_voltage > bms.limit_maximum_pack_voltage):
            return self.set_fatal_error("Pack voltage out of range " + str(bms.pack_voltage))
        elif bms.min_cell_voltage is not None and (
                bms.min_cell_voltage < bms.limit_minimum_cell_voltage or bms.min_cell_voltage > bms.limit_maximum_cell_voltage):
            return self.set_fatal_error("Min cell voltage out of range " + str(bms.min_cell_voltage))
        elif bms.max_cell_voltage is not None and (
                bms.max_cell_voltage < bms.limit_minimum_cell_voltage or bms.max_cell_voltage > bms.limit_maximum_cell_voltage):
            return self.set_fatal_error("Max cell voltage out of range " + str(bms.max_cell_voltage))
        elif bms.max_cell_voltage is not None and bms.min_cell_voltage is not None and bms.max_cell_voltage - bms.min_cell_voltage > 0.20:  # 200 mv - 10mv is ideal but needs to be balanced probably
            return self.set_fatal_error(
                "Delta cell voltage out of range " + str(bms.max_cell_voltage - bms.min_cell_voltage))

        # Temp
        elif bms.max_temp is not None and (
                bms.max_temp > bms.limit_maxiumum_temperature or bms.max_temp < bms.limit_miniumum_temperature):
            return self.set_fatal_error("Max temp out of range " + str(bms.max_temp))
        elif bms.avg_temp is not None and (
                bms.avg_temp > bms.limit_maxiumum_temperature or bms.avg_temp < bms.limit_miniumum_temperature):
            return self.set_fatal_error("Avg temp out of range " + str(bms.avg_temp))
        elif bms.min_temp is not None and (
                bms.min_temp > bms.limit_maxiumum_temperature or bms.min_temp < bms.limit_miniumum_temperature):
            return self.set_fatal_error("Min temp out of range " + str(bms.min_temp))

        # Current
        elif bms.current is not None and (
                bms.current > bms.limit_maximum_current or bms.current < bms.limit_minimum_current):
            return self.set_fatal_error("Current out of range " + str(bms.current))
        # This will error when trying to go above 99%
        elif bms.current is not None and bms.max_power is not None and (
                bms.current > (bms.max_power * 1000 / 400)) and bms.soc < 95:
            return self.set_fatal_error("Current out of range (max_power) " + str(bms.current))

        # Other
        elif bms.interlock is not None and bms.interlock != 2:
            return self.set_fatal_error("Interlock out of range " + str(bms.interlock))
        elif bms.kwh_remaining is not None and (bms.kwh_remaining < 1.5):
            return self.set_fatal_error("kwh remaining out of range " + str(bms.kwh_remaining))
        elif self.zoe_handler.last_message_received < helper.get_timestamp() - 120 * 1000 and self.frame_requesting_allowed:
            return self.set_fatal_error("Zoe message older than 120 seconds. Last message " + str(
                self.zoe_handler.last_message_received) + " now " + str(helper.get_timestamp()))
        else:
            return True

    def reset(self):
        self.penthouse.disable_precharge()
        self.penthouse.disable_contactor()
        self.penthouse.disable_12v()
        self.zoe_handler.stop_listening()
        self.zoe_handler.stop_frame_sending()
        self.zoe_handler.stop_cell_data()

    def set_fatal_error(self, error_str):
        print("ERROR: ", error_str)
        self.fatal_error = error_str
        self.reset()
        self.set_stage(0)
        return False

    def set_mild_error(self, error_str):
        print("WARNING: ", error_str)
        print("Sleeping 15 seconds")
        time.sleep(15)
        self.set_stage(0)

    def _run(self):
        if self.stage >= 70:
            self.safety_checks()

        if self.stage <= 10:  # Begin
            self.reset()
            if self.fatal_error == '':
                self.set_stage(20)  # OK
            else:
                self.set_stage(12)  # Fatal
        elif self.stage == 12:
            print("Fatal error has been set: ", self.fatal_error)
            time.sleep(60)
            self.set_stage(0)
        elif self.stage == 20:
            if self.penthouse.is_precharge_on():
                self.set_fatal_error("Precharge was left on")
            elif self.penthouse.is_contactor_on():
                self.set_fatal_error("Contactor was left on")
            else:
                self.set_stage(30)
        elif self.stage == 30:
            self.penthouse.enable_12v()
            time.sleep(0.1)
            if self.penthouse.is_12v_on():
                self.set_stage(35)  # OK
            else:
                self.set_mild_error("12V opto issue")
        elif self.stage == 35:
            if self.penthouse.is_precharge_on():
                self.set_fatal_error("Precharge was left on")
            elif self.penthouse.is_contactor_on():
                self.set_fatal_error("Contactor was left on")
            else:
                self.set_stage(40)
        elif self.stage == 40:
            os.system('ifconfig can0 txqueuelen 65536')
            os.system('ifconfig can1 txqueuelen 65536')
            self.set_stage(50)
        elif self.stage == 50:
            self.zoe_handler.start_frame_sending()
            time.sleep(2)
            self.zoe_handler.begin_listening()
            self.zoe_handler.start_cell_data()
            if not self.zoe_handler.request_data():
                self.set_mild_error("Error requesting data")
            else:
                time.sleep(5)
                self.set_stage(55)
        elif self.stage == 55:  # Wait
            if self.battery_allowed:
                self.set_stage(60)
            else:
                if not self.zoe_handler.request_data():
                    self.set_mild_error("Error requesting zoe data")
                time.sleep(10)
        elif self.stage == 60:  # Safety
            if self.safety_checks():
                self.set_stage(70)
            else:
                self.set_mild_error("Safety check failed")
        elif self.stage == 70:  # Precharge
            self.penthouse.enable_precharge()
            time.sleep(0.1)
            if self.penthouse.is_precharge_on():
                self.set_stage(80)  # OK
            else:
                self.set_fatal_error("Precharge opto issue")
        elif self.stage == 80:
            self.penthouse.enable_contactor()
            time.sleep(0.1)
            if self.penthouse.is_contactor_on():
                self.set_stage(90)  # OK
            else:
                self.set_fatal_error("Contactor opto issue")
        elif self.stage == 90:
            self.penthouse.disable_precharge()
            time.sleep(0.1)
            if self.penthouse.is_precharge_on():
                self.set_fatal_error("Precharge opto issue")
            else:
                self.set_stage(100)
        elif self.stage == 100:
            self.penthouse.stabilise_contactor()
            time.sleep(0.1)
            if self.penthouse.is_contactor_on():
                self.set_stage(110)  # OK
            else:
                self.set_fatal_error("Contactor opto issue")
        elif self.stage == 110:
            if self.penthouse.is_precharge_on():
                self.set_fatal_error("Precharge was left on")
            else:
                self.set_stage(120)
        elif self.stage == 120:
            if not self.zoe_handler.request_data():
                self.set_mild_error("Error requesting zoe data")
            elif not self.penthouse.is_contactor_on():
                self.set_fatal_error("Contactor opto issue")
            elif self.penthouse.is_precharge_on():
                self.set_fatal_error("Precharge was left on")
            elif not self.battery_allowed:
                self.set_mild_error("Battery no longer allowed")

            time.sleep(10)


# Begin running
Controller()