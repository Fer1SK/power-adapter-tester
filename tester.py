import json
import threading
from time import sleep
from datetime import datetime
from rpi_hardware_pwm import HardwarePWM
from subclasses import DataStorage, AppSettings, TestableAdapters, EvaluateResults
from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
import glob
import board
import busio
import adafruit_ina219
import RPi.GPIO as GPIO
import colorama


class Tester:
    def __init__(self):
        self.voltage: float = 0.0
        self.current: float = 0.0
        self.temp: float = 0.0
        self.data_storage = DataStorage()
        self.settings = AppSettings()
        self.testable_adapters = TestableAdapters()
        self.results = EvaluateResults(self.data_storage)
        self.test_values = {}
        self.progress: int = 0
        self.is_running: bool = False
        self.is_measuring: bool = True
        self.debug: bool = False
        self.is_connected: bool = False
        self.update_ptd: bool = True
        self.update_ptd: bool = True
        self.led_pin = 27
        self.connection_pin = 23
        self.running_signal_pin = 24
        self.pwm = None  
        self.ina219 = None
        self.v_a_thread = None
        self.pwm_thread = None
        self.test_thread = None
        self.percent_load_on_adapter: float = 0  # In % I think ?
        self.applied_pwm_duty: float = 0
        self.wait_to_stop = False

    def setup(self):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.connection_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(self.led_pin, GPIO.OUT)
        GPIO.setup(self.running_signal_pin, GPIO.OUT)
        self.ina219 = adafruit_ina219.INA219(busio.I2C(board.SCL, board.SDA))
        if self.settings.high_res:
            self.switch_to_high_res()
        else:
            self.switch_to_low_res()

        self.pwm = HardwarePWM(pwm_channel=0, hz=60, chip=0)
        self.pwm.change_frequency(10000)
        self.v_a_thread = threading.Thread(target=self.get_V_A)
        self.v_a_thread.start()
        self.set_res_list()
        self.testable_adapters.load_values()
        self.flash_LED(1)

    def start(self):
        if not self.is_running and self.is_connected:
            self.is_running = True
            self.turn_on_LED()
            self.turn_on_signal()
            self.pwm.start(0)
            self.pwm_thread = threading.Thread(target=self.change_pwm)
            self.pwm_thread.start()
            self.progress = 1
            self.data_storage.clear()
            self.test_thread = threading.Thread(target=self.phase1)
            self.test_thread.start()

    def start_constant_load(self, load: float):
        if not self.is_running and self.is_connected:
            self.is_running = True
            self.turn_on_LED()
            self.turn_on_signal()
            self.pwm.start(0)
            self.pwm_thread = threading.Thread(target=self.change_pwm)
            self.pwm_thread.start()
            self.percent_load_on_adapter = (load / self.testable_adapters.selected_adapter.max_current) * 100  # Amps to % load

    def switch_to_high_res(self):
        self.ina219.bus_adc_resolution = adafruit_ina219.ADCResolution.ADCRES_12BIT_1S
        self.ina219.shunt_adc_resolution = adafruit_ina219.ADCResolution.ADCRES_12BIT_1S
        msg = "Switched to High Resolution"
        print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, GRAY)

    def switch_to_low_res(self):
        self.ina219.bus_adc_resolution = adafruit_ina219.ADCResolution.ADCRES_9BIT_1S
        self.ina219.shunt_adc_resolution = adafruit_ina219.ADCResolution.ADCRES_9BIT_1S
        msg = "Switched to Low Resolution"
        print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, GRAY)

    def get_V_A(self):
        ts = 0
        while True:
            if not self.is_measuring:
                return
            if ts == 10:
                ts = 0
                self.connected_check()
                if self.debug:
                    msg = f"    Vals: {self.voltage}V; {self.current} A; {self.is_connected}"
                    print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
                    self.data_storage.add_message(msg, GRAY)
                if not self.is_connected:
                    self.voltage = 0.00

            self.voltage = float(self.ina219.bus_voltage)
            self.current = float(self.ina219.current / 1000.0)
            self.data_storage.new_values(self.voltage, self.current, self.percent_load_on_adapter, self.is_connected)
            ts += 1
            # Timeout based on settings
            if self.settings.high_res:
                # Takes about .5 sec between hw measurments
                sleep(.5)
            elif not self.settings.high_res:
                if self.settings.per_sec:
                    # Slower, once per sec
                    sleep(1)

                elif not self.settings.per_sec:
                    # At low res (9BIT), all data
                    sleep(.1)
            else:
                raise AssertionError("This is a big problem. Something is wrong in the settings.")

    def turn_on_signal(self):
        GPIO.output(self.running_signal_pin, GPIO.HIGH)
        if self.debug:
            msg = f"HW signal is now on. Pin: {self.running_signal_pin}"
            print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
            self.data_storage.add_message(msg, GRAY)

    def turn_off_signal(self):
        GPIO.output(self.running_signal_pin, GPIO.LOW)
        if self.debug:
            msg = f"HW signal is now off. Pin: {self.running_signal_pin}"
            print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
            self.data_storage.add_message(msg, GRAY)

    def turn_on_LED(self):
        GPIO.output(self.led_pin, GPIO.HIGH)
        if self.debug:
            msg = "LED is now on"
            print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
            self.data_storage.add_message(msg, GRAY)

    def turn_off_LED(self):
        GPIO.output(self.led_pin, GPIO.LOW)
        if self.debug:
            msg = "LED is now off"
            print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
            self.data_storage.add_message(msg, GRAY)

    def flash_LED(self, t):
        self.turn_on_LED()
        sleep(t)
        self.turn_off_LED()
        sleep(t)

    def connected_check(self):
        if GPIO.input(self.connection_pin) == GPIO.LOW:
            self.is_connected = False
        else:
            self.is_connected = True

    def read_temp_raw(self):
        sensor_files = glob.glob('/sys/bus/w1/devices/28-*/w1_slave')
        if not sensor_files:
            raise Exception("DS18B20 sensor not found")

        sensor_file = sensor_files[0]
        with open(sensor_file, 'r') as f:
            lines = f.readlines()
        return lines

    def get_temp(self):
        lines = self.read_temp_raw()
        while lines[0].strip()[-3:] != 'YES':
            sleep(0.2)
            lines = self.read_temp_raw()
        equals_pos = lines[1].find('t=')
        if equals_pos != -1:
            temp_string = lines[1][equals_pos + 2:]
            temp_c = float(temp_string) / 1000.0
            self.temp = temp_c
            self.data_storage.new_temp(self.temp)
            if self.debug:
                print(colorama.Fore.LIGHTBLACK_EX, "Temperature: {:.1f} °C".format(temp_c), colorama.Fore.RESET)

    def start_calibration(self):
        self.pwm_thread = threading.Thread(target=self.calibrate)
        self.pwm_thread.start()
        return "Started calibration"

    def calibrate(self):
        # keep highest if ==
        calibrated = {}
        self.pwm.start(10)
        sleep(5)
        self.turn_on_LED()
        to_define = [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0, 10.2, 10.4, 10.6, 10.8, 11.0, 11.2, 11.4, 11.6, 11.8, 12.0, 12.2, 12.4, 12.6, 12.8, 13.0, 13.2, 13.4, 13.6, 13.8, 14.0, 14.2, 14.4, 14.6, 14.8, 15.0, 15.2, 15.4, 15.6, 15.8, 16.0, 16.2, 16.4, 16.6, 16.8, 17.0, 17.2, 17.4, 17.6, 17.8, 18.0, 18.2, 18.4, 18.6, 18.8, 19.0, 19.2, 19.4, 19.6, 19.8, 20.0]
        msg = "Calibration In progress DO NOT UNPLUG THE ADAPTER"
        print(colorama.Fore.RED, msg)
        self.data_storage.add_message(msg, RED)
        for pwm_percent in to_define:
            self.pwm.change_duty_cycle(pwm_percent)
            sleep(.2)
            calibrated[round(self.current, 2)] = pwm_percent
            self.progress = self.progress + (100 / len(to_define))
            print(f"{self.progress} % done, please wait")
        with open("calibrated.json", "w") as f:
            json.dump(calibrated, f)
        msg = "Calibration completed successfully"
        print(colorama.Fore.GREEN, msg, colorama.Style.RESET_ALL)
        self.data_storage.add_message(msg, GREEN)
        self.progress = 100
        self.settings.pwm_mappings = calibrated
        self.pwm.stop()
        self.turn_off_LED()
        sleep(2)
        self.progress = 0

    def change_pwm(self):
        last_percent_load_on_adapter = 0
        while self.is_running:
            if last_percent_load_on_adapter != self.percent_load_on_adapter:
                current1 = None
                current2 = None
                target_current = (self.percent_load_on_adapter / 100) * self.testable_adapters.selected_adapter.max_current  # pwm changed from % to amps
                for i in range(len(self.settings.pwm_mappings) - 1):
                    pwm1, current1 = self.settings.pwm_mappings[i]
                    pwm2, current2 = self.settings.pwm_mappings[i + 1]

                    if self.percent_load_on_adapter == 2111333:
                        # Testing shortcircuit
                        self.applied_pwm_duty = 100
                        break
                    elif current1 == target_current:
                        self.applied_pwm_duty = pwm1
                        break
                    elif current2 == target_current:
                        self.applied_pwm_duty = pwm2
                        break
                    elif current1 < target_current < current2:
                        # Interpolate if not exact
                        ratio = (target_current - current1) / (current2 - current1)
                        self.applied_pwm_duty = pwm1 + ratio * (pwm2 - pwm1)
                        if self.applied_pwm_duty > 100:
                            self.applied_pwm_duty = 100
                        break
                    elif 3.2 < target_current < 3.5:
                        self.applied_pwm_duty = 75
                        msg = f"Reached max current of 3.2A"
                        self.data_storage.add_message(msg, RED)
                        print(colorama.Fore.RED, msg, colorama.Style.RESET_ALL)
                        break
                else:
                    msg = f"Error: Wanted current is not within expected range; {current1} < {target_current} < {current2}"
                    self.data_storage.add_message(msg, RED)
                    raise ValueError(msg)


                try:
                    self.pwm.change_duty_cycle(self.applied_pwm_duty)
                    last_percent_load_on_adapter = self.percent_load_on_adapter
                    msg = f"Expected current: {target_current}; Selected PWM: {self.applied_pwm_duty}"
                    self.data_storage.add_message(msg, GRAY)
                    print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Style.RESET_ALL)
                except Exception as e:
                    msg = f"Error: PWM duty cant be changed to {self.applied_pwm_duty}, due to this error: {e}"
                    self.data_storage.add_message(msg, RED)
                    raise ValueError(msg)

            sleep(.1)

    def set_res_list(self):
        self.test_values = None
        self.test_values = [
            {
                "start_index": 0,
                "stop_index": 0,
            },
            {
                "start_index": 0,
                "stop_index": 0,
            },
            {
                "start_index": 0,
                "stop_index": 0,
                "OPP_trip_index": [],
                "OPP_trip_load": [],
                "short_circuit": False,
            }
        ]

    def phase1(self):
        self.progress += 10
        msg = f"Phase 1:\n    - Testing standard load increase\n    - Testing loads between 0% and 100% \n    - Repeating test {self.settings.phase1[1]} times\n"
        print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, GREEN)
        if self.settings.phase1[0]:
            start_index = len(self.data_storage.voltage) - 1

            for reps in range(self.settings.phase1[1]):
                for pwm_val in range(10, 110, 10):
                    self.percent_load_on_adapter = pwm_val
                    while self.data_storage.load.count(pwm_val) < 10 and self.is_running:
                        # To make sure that each load level is exactly 1s
                        sleep(.1)
                    self.progress += 2 / self.settings.phase1[1]

                self.percent_load_on_adapter = 0
                sleep(.1)
            stop_index = len(self.data_storage.voltage) - 1
            # Remove any trailing or preceding 0s in the results
            while self.data_storage.load[start_index] == 0 and self.is_running:
                start_index += 1
            while self.data_storage.load[stop_index] > 0 and self.is_running:
                try:
                    stop_index += 1
                    # This is fine its here to stop the loop
                    self.data_storage.load[stop_index]
                except IndexError:
                    break
            self.test_values[0]["start_index"] = start_index
            self.test_values[0]["stop_index"] = stop_index

        if self.is_running:
            self.phase2()
        else:
            msg = "Test stopped successfully"
            self.data_storage.add_message(msg, BLUE)
            print(colorama.Fore.BLUE, msg, colorama.Fore.RESET)
            self.wait_to_stop = False
            self.progress = 0

    def phase2(self):
        msg = f"Phase 2:\n    - Testing transient load\n    - Testing loads between 0% and 100% \n    - Testing sharp changes in load\n    - Repeating test {self.settings.phase1[1]} times\n"
        print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, GREEN)
        if self.settings.phase2[0]:
            self.percent_load_on_adapter = 0
            sleep(3)
            start_index = len(self.data_storage.voltage) - 1

            for reps in range(self.settings.phase2[1]):
                self.progress += 3.75 / self.settings.phase2[1]
                self.percent_load_on_adapter = 100
                sleep(1)
                while self.data_storage.load[start_index] == 0 and self.is_running:
                    # Remove any preceding 0s in the results
                    start_index += 1
                while self.data_storage.load[start_index:].count(100) < 60 and self.is_running:
                    # To make sure that each load level is exactly 6s
                    sleep(.1)
                self.progress += 8.125 / self.settings.phase2[1]
                self.percent_load_on_adapter = 0
                while self.data_storage.load[start_index:].count(0) <= 60 and self.is_running:
                    # To make sure that each load level is exactly 6s
                    sleep(.1)
                self.progress += 8.125 / self.settings.phase2[1]

            self.test_values[1]["start_index"] = start_index
            self.test_values[1]["stop_index"] = len(self.data_storage.voltage) - 1

        if self.is_running:
            self.phase3()
        else:
            msg = "Test stopped successfully"
            self.data_storage.add_message(msg, BLUE)
            print(colorama.Fore.BLUE, msg, colorama.Fore.RESET)
            self.wait_to_stop = False
            self.progress = 0

    def phase3(self):
        msg = f"Phase 3:\n    - Testing OPP\n    - Testing loads over 100% \n    - Repeating test {self.settings.phase3[1]} times\n    - Looking for {self.settings.phase3[2]} OPP trips\n"
        print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, GREEN)
        test_start_time = datetime.now()
        if self.settings.phase3[0]:
            for reps in range(self.settings.phase3[1]):
                self.test_values[2]["start_index"] = len(self.data_storage.voltage) - 1
                diff = 100
                while self.is_running:
                    # Safety Shutdown
                    # Turn on If:
                    if len(self.test_values[2]["OPP_trip_load"]) >= self.settings.phase3[2]:
                        #   1. We hit the number of set repeats, break, continue normaly
                        break

                    elif (self.percent_load_on_adapter / 100) * self.testable_adapters.selected_adapter.max_current >= self.settings.max_current_shutdown:
                        #   2. The current exceeds 3.2A
                        if self.settings.exit_at_safety:
                            msg = f"Safety shutdown: Current exceeded max set safe value ({self.settings.max_current_shutdown}A), ending test, reducing load"
                            print(colorama.Fore.RED, msg, colorama.Fore.RESET)
                            self.data_storage.add_message(msg, RED)
                            return

                        elif not self.settings.exit_at_safety:
                            msg = f"Safety shutdown: Current exceeded max set safe value ({self.settings.max_current_shutdown}A), continuing test, reducing load"
                            print(colorama.Fore.RED, msg, colorama.Fore.RESET)
                            self.data_storage.add_message(msg, RED)
                            break

                    elif (datetime.now() - test_start_time).total_seconds() > 60:
                        #   3. The test has been on for more than 60sec, meaning its stuck
                        if self.settings.exit_at_safety:
                            msg = "Safety shutdown: Test is stuck, ending test, reducing load"
                            print(colorama.Fore.RED, msg, colorama.Fore.RESET)
                            self.data_storage.add_message(msg, RED)
                            return

                        elif not self.settings.exit_at_safety:
                            msg = "Safety shutdown: Test is stuck, continuing test, reducing load"
                            print(colorama.Fore.RED, msg, colorama.Fore.RESET)
                            self.data_storage.add_message(msg, RED)
                            break
                    if self.voltage < self.testable_adapters.selected_adapter.min_voltage:
                        calcd_load = round((self.current / self.testable_adapters.selected_adapter.max_current) * 100)
                        msg = f"OPP trip point :{calcd_load}%"
                        print(colorama.Fore.YELLOW, msg, colorama.Fore.RESET)
                        self.data_storage.add_message(msg, ORANGE)

                        self.test_values[2]["OPP_trip_index"].append(len(self.data_storage.voltage) - 1)
                        self.test_values[2]["OPP_trip_load"].append(calcd_load)
                        diff -= 15
                        self.percent_load_on_adapter = diff
                        sleep(3)
                    else:
                        diff += 5

                    sleep(.25)
                    self.progress += 1.42587 / self.settings.phase3[1]
                    self.percent_load_on_adapter = diff

            msg = "Testing Short Circuit"
            print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
            self.data_storage.add_message(msg, GREEN)

            # Short circuit protection
            for x in range(self.settings.phase3[2]):
                self.percent_load_on_adapter = 2111333
                sleep(.5)
                if self.voltage < 1.5 and self.current < .1:
                    self.test_values[2]["short_circuit"] = True
                    self.percent_load_on_adapter = 0
                    sleep(3)
                else:
                    self.test_values[2]["short_circuit"] = False
                    break
        self.percent_load_on_adapter = 0
        self.test_values[2]["stop_index"] = len(self.data_storage.voltage) - 1
        sleep(1)
        if self.is_running:
            self.parse_results()
        else:
            msg = "Test stopped successfully"
            self.data_storage.add_message(msg, BLUE)
            print(colorama.Fore.BLUE, msg, colorama.Fore.RESET)
            self.wait_to_stop = False
            self.progress = 0

    def parse_results(self):
        self.progress = 70  # TODO daco musim spravit s tym progressom idk ci to chcem davat do gui
        msg = "Processing results, please wait ..."
        self.data_storage.add_message(msg, GREEN)
        print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
        self.results.eval(self.data_storage.voltage, self.data_storage.current, self.data_storage.load,
                          self.test_values, self.testable_adapters.selected_adapter)
        self.results.write_data_into_file(self.testable_adapters.selected_adapter, self.settings)
        self.progress = 100
        self.stop()
        msg = "Test Finished"
        print(colorama.Fore.BLUE, msg, colorama.Fore.RESET)
        self.data_storage.add_message(msg, BLUE)
        self.data_storage.add_message(self.results.fin_message, "TEST RESULTS")

        sleep(1)
        del self.results
        self.results = EvaluateResults(self.data_storage)
        self.progress = 0
        self.wait_to_stop = False
        self.update_ptd = True

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.data_storage.testing = False
            self.wait_to_stop = True
            self.pwm.stop()
            try:
                self.pwm_thread.join()
            except (AttributeError, RuntimeError):
                pass
            self.percent_load_on_adapter = 0
            self.turn_off_LED()
            self.turn_off_signal()
            self.set_res_list()
            return "stopping"

        elif self.wait_to_stop:
            return "waiting"

        else:
            return "idle"

    def shutdown(self):
        while self.stop() != "idle":
            continue
        self.is_measuring = False
        sleep(1)
        try:
            self.v_a_thread.join()
            self.v_a_thread = None
        except ValueError:
            pass
        GPIO.cleanup()

