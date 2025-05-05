import pickle
import random
import string
import zipfile
from datetime import datetime
import colorama
import h5py
import numpy as np
import plotly.graph_objects as go
from dash import dcc
from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
from dash import html
import json
import os
import traceback
import csv


empty_fig = go.Figure()
empty_fig.update_layout(plot_bgcolor="#3a3a3a", paper_bgcolor="#2a2a2a", font=dict(color="#f4f4f4"))
empty_fig.update_xaxes(gridcolor="#444444")
empty_fig.update_yaxes(gridcolor="#444444")

class DataStorage:
    def __init__(self):
        self.voltage: [float] = []
        self.current: [float] = []
        self.load: [int] = []
        self.messages: [dict] = []
        self.max_len: int = 250  # Change to display more / fewer messages in GUI
        self.url = "/"
        self.old_url = "/"
        self.testing = False

    def new_values(self, v: float, c: float, l: float, connected: bool):
        if not self.testing and len(self.voltage) > 1800:
            self.voltage = self.voltage[-10:]
            self.current = self.current[-10:]
            self.load = self.load[-10:]
            msg = "Cleaning values"
            print(colorama.Fore.BLUE, msg, colorama.Fore.RESET)
            self.add_message(msg, BLUE)
        if not connected:
            v = 0
            c = 0
            l = 0
        self.voltage.append(v)
        self.current.append(c)
        self.load.append(l)

    def clear(self):
        self.voltage = []
        self.current = []
        self.load = []

    def add_message(self, text, color):
        timestamp = f"[{datetime.now().strftime('%H:%M:%S')}]"

        if color == "TEST RESULTS":
            self.messages.append({
                    "text": [timestamp] + text,
                    "color": "TEST RESULTS"
                })

        elif "\n" in text:
            # Multi line message
            for line in text.split("\n"):
                self.messages.append({
                    "text": f"{timestamp};{line}",
                    "color": color
                })
                if len(self.messages) > self.max_len:
                    self.messages.pop(0)
        else:
            # Single-line message
            self.messages.append({
                "text": f"{timestamp};{text.strip()}",
                "color": color
            })
            if len(self.messages) > self.max_len:
                self.messages.pop(0)


class AppSettings:
    def __init__(self):
        self.max_current_shutdown = 3.2
        self.per_sec = False
        self.high_res = False
        self.exit_at_safety = True
        self.phase1 = [True, 1]
        self.phase2 = [True, 1]
        self.phase3 = [True, 1, 3]
        self.pwm_mappings = []  # {Current(A): Load(%)}
        self.load_values()

    def new_values(self, mcs, max_exit: bool, ps: bool, hr: bool, p1incl: bool, p1rep, p2incl: bool, p2rep, p3incl: bool, p3rep, p3opp) -> dict:
        msg = ""
        try:
            mcs = float(mcs)
            p1rep = int(p1rep)
            p2rep = int(p2rep)
            p3rep = int(p3rep)
            p3opp = int(p3opp)

            if not 0 < mcs <= 3.2:
                msg = "Max current shutdown must be between 0 and 3.2A"
                raise ValueError

            elif not 1 <= p1rep <= 6:
                msg = "Phase 1 repeats must be between 1 and 5 incl."
                raise ValueError

            elif not 1 <= p2rep <= 6:
                msg = "Phase 2 repeats must be between 1 and 5 incl."
                raise ValueError

            elif not 1 <= p3rep <= 6:
                msg = "Phase 3 repeats must be between 1 and 5 incl."
                raise ValueError

            elif not 3 <= p3opp <= 10:
                msg = "Looking for OPP trip point must be between 3 and 10 incl."
                raise ValueError

        except ValueError:
            self.set_defaults()
            msg = "Check inputted values. And try again. " + msg
            return {
                "msg": msg,
                "parsed": False
            }

        self.max_current_shutdown = mcs
        self.per_sec = ps
        self.high_res = hr
        self.exit_at_safety = max_exit
        self.phase1 = [p1incl, p1rep]
        self.phase2 = [p2incl, p2rep]
        self.phase3 = [p3incl, p3rep, p3opp]

        self.save_values()
        return {
            "msg": "Settings successfully updated",
            "parsed": True
        }

    def load_values(self):
        with open('conf.json', 'r') as f:
            data = json.load(f)
            self.per_sec = data.get('graph_data_per_sec', self.per_sec)
            self.high_res = data.get('high_res_mode', self.high_res)
            self.max_current_shutdown = data.get('max_current_shutdown', self.max_current_shutdown)
            self.exit_at_safety = data.get('exit_at_safety', self.exit_at_safety)
            phases = []
            phases = data.get('phases', phases)
            for phase in phases:
                if phase["phase"] == 1:
                    self.phase1 = [phase["include"], phase["repeat"]]
                elif phase["phase"] == 2:
                    self.phase2 = [phase["include"], phase["repeat"]]
                elif phase["phase"] == 3:
                    self.phase3 = [phase["include"], phase["repeat"], phase["look_for_trip_point"]]
                else:
                    print(colorama.Fore.YELLOW, "Invalid settings, continuing with default settings", colorama.Fore.RESET)
                    self.set_defaults()
                    break
        # Load calibration data
        with open('pwm_mapping_data.csv', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                pwm = float(row['pwm'])
                current = float(row['current'])
                self.pwm_mappings.append((pwm, current))

    def set_defaults(self):
        self.max_current_shutdown = 3.2
        self.per_sec = False
        self.high_res = False
        self.exit_at_safety = True
        self.phase1 = [True, 1]
        self.phase2 = [True, 1]
        self.phase3 = [True, 1, 3]

    def save_values(self):
        config_data = {
            "max_current_shutdown": self.max_current_shutdown,
            "graph_data_per_sec": self.per_sec,
            "high_res_mode": self.high_res,
            "exit_at_safety": self.exit_at_safety,
            "phases": [
                {
                    "phase": 1,
                    "include": self.phase1[0],
                    "repeat": self.phase1[1]
                },
                {
                    "phase": 2,
                    "include": self.phase2[0],
                    "repeat": self.phase2[1]
                },
                {
                    "phase": 3,
                    "include": self.phase3[0],
                    "repeat": self.phase3[1],
                    "look_for_trip_point": self.phase3[2]
                }
            ]
        }

        with open('conf.json', 'w') as f:
            json.dump(config_data, f, indent=4)


class TestableAdapters:
    def __init__(self):
        self.data = []
        self.adapters: [Adapter] = []
        self.selected_adapter: Adapter = None

    def load_values(self):
        with open("adapters.json", "r") as f:
            data = json.load(f)

        self.data = data["adapters"]
        for a in self.data:
            self.adapters.append(Adapter(a["name"], a["max_current"], a["max_voltage"], a["min_voltage"],
                                         a["voltage_tolerance"], a["min_OPP"], a["max_OPP"]))
            # Loading adapter from adapters.json

    def add_new_adapter(self, name, max_current, max_voltage, min_voltage, v_tol, opp_min, opp_max):
        self.adapters.append(Adapter(name, max_current, max_voltage, min_voltage, v_tol, opp_min, opp_max))

        with open("adapters.json", "r") as f:
            data = json.load(f)

        new_adapter = {
            "name": name,
            "max_current": max_current,
            "max_voltage": max_voltage,
            "min_voltage": min_voltage,
            "voltage_tolerance": v_tol,
            "min_OPP": opp_min,
            "max_OPP": opp_max
        }
        data["adapters"].append(new_adapter)
        self.data = data

        with open("adapters.json", "w") as f:
            json.dump(data, f, indent=4)

    def select_adapter(self, index: int):
        if index is not None:
            self.selected_adapter = self.adapters[index]
        else:
            self.selected_adapter = None

    def delete_adapter(self, index: int):
        msg = ""
        code = False
        try:
            if index < 0 or index >= len(self.adapters):
               msg = "Invalid index"

            deleted_adapter = self.adapters.pop(index)
            with open("adapters.json", "r") as file:
                data = json.load(file)

            json_adapters = data.get("adapters", [])
            if index >= len(json_adapters):
                msg = "Index out of bounds in JSON data."

            json_adapters.pop(index)
            with open("adapters.json", "w") as file:
                json.dump(data, file, indent=4)
            msg = f"Successfully deleted adapter: {deleted_adapter.name}"
            code = True

        except Exception as e:
            msg = traceback.format_exc()

        return {"success": code, "msg": msg}


class Adapter:
    def __init__(self, n: str, mc: float, mv: float, nv: float, vt: float, on: int, om: int):
        self.name = n
        self.max_current = mc
        self.max_voltage = mv
        self.min_voltage = nv
        self.v_tol = vt  # Voltage tolerance
        self.OPP_min = on
        self.OPP_max = om


class EvaluateResults:
    def __init__(self, data):
        self.data_storage = data
        self.a_tol = 10  # Tolerance in %
        self.v_tol = 10  # Tolerance in %
        self.phase1_pass: bool = True
        self.phase2_pass: bool = True
        self.phase3_pass: bool = True
        self.test_valid: bool = True
        self.scp_pass: bool = True
        self.print_results: bool = False
        self.OOB_results = []
        self.bottom_border = []
        self.top_border = []
        self.voltage = []  # Trimmed Correctly
        self.voltage_good = [] # for graph
        self.voltage_oob = [] # Voltage out of bounds
        self.current = []  # Trimmed Correctly
        self.load = []  # Trimmed Correctly
        self.OPP_trips = []
        self.phase = []
        self.fin_message = None
        self.test_number = 1
        self.load_id_tracker()

    def load_id_tracker(self, file_name='id_tracker.pkl'):
        current_date = datetime.now().strftime('%Y%m%d')

        try:
            with open(file_name, 'rb') as f:
                data = pickle.load(f)
                stored_date = data.get('date', '')
                stored_test_number = data.get('test_number', 1)

            if stored_date == current_date:
                self.test_number = stored_test_number
            else:
                self.test_number = 1
                with open(file_name, 'wb') as f:
                    pickle.dump({'date': current_date, 'test_number': self.test_number}, f)

        except (FileNotFoundError, EOFError):
            self.test_number = 1
            with open(file_name, 'wb') as f:
                pickle.dump({'date': current_date, 'test_number': self.test_number}, f)

    def eval(self, voltage: list, current: list, load: list, test_values: dict, tested_adapter: Adapter):
        # phase 1 = +- tolerance%
        # phase 2 = +- tolerance%
        # OPP within spec
        # AMC/AMV/AML = adapter max current / voltage
        self.v_tol = tested_adapter.v_tol
        load = load[:test_values[2]["stop_index"]]
        self.load = load
        voltage = voltage[:test_values[2]["stop_index"]]
        self.voltage = voltage
        current = current[:test_values[2]["stop_index"]]
        self.current = current
        self.scp_pass = test_values[2]["short_circuit"]
        v_bottom_bound = tested_adapter.max_voltage * (100 - self.v_tol) / 100
        v_top_bound = tested_adapter.max_voltage * (100 + self.v_tol) / 100
        was_last_ok = True

        # Plot bounds and Evaluate completion of the phases
        for i, l in enumerate(load):
            # From load to amps -> (load / 100) * max
            # Plotting +- v_tolerance window = amv * 100 + v_tol / 100
            # Load is a consistent and shows the expected results for amps
            v = voltage[i]
            a = current[i]
            if i < test_values[1]['stop_index']:
                # Save vals so that we can highlight the range on graph
                self.bottom_border.append(v_bottom_bound)
                self.top_border.append(v_top_bound)
                if a < ((l - self.a_tol) / 100) * tested_adapter.max_current or a > ((l + self.a_tol) / 100) * tested_adapter.max_current:
                    # Current is out of bounds
                    self.add_OOB_result(v, a, l, v_bottom_bound, v_top_bound)
                    self.test_valid = False

                if v < v_bottom_bound or v > v_top_bound:
                    # Voltage is out of bounds
                    if was_last_ok:
                        # Handles transitions from yellow to red line, so that it looks nice. Last value needs to be added to both so that it looks as if its connected
                        try:
                            self.voltage_oob.pop()
                        except IndexError:
                            pass
                        self.voltage_oob.append(voltage[i - 1])
                        
                    self.add_OOB_result(v, a, l, v_bottom_bound, v_top_bound)
                    self.voltage_good.append(None)
                    self.voltage_oob.append(v)
                    was_last_ok = False

                    if i < test_values[0]["stop_index"]:  # If i in phase1
                        self.phase1_pass = False
                    elif i < test_values[1]["stop_index"]:  # If i in phase2
                        self.phase2_pass = False
                    else:
                        raise ValueError("This is not possible")

                else:
                    # Voltage is not out of bounds
                    if not was_last_ok:
                        # Handles transitions from yellow to red line, so that it looks nice. Last value needs to be added to both so that it looks as if its connected
                        self.voltage_oob.append(v)
                    else:
                        self.voltage_oob.append(None)
                    self.voltage_good.append(v)
                    was_last_ok = True
            else:
                self.voltage_good.append(v)
                self.voltage_oob.append(None)
                self.bottom_border.append(None)
                self.top_border.append(None)

            if i < test_values[0]["stop_index"]:
                self.phase.append(1)
            elif i < test_values[1]["stop_index"]:
                self.phase.append(2)
            else:
                self.phase.append(3)

        # Saving OPP results
        # self.OPP_trips = [[voltages: float], [currents: float], [loads: float], [fine: bool]]
        v = []
        a = []
        l = []
        b = []
        for opp in test_values[2]["OPP_trip_index"]:
            v.append(voltage[opp])
            a.append(current[opp])
            l.append(load[opp])
            if tested_adapter.OPP_min < load[opp] < tested_adapter.OPP_max:
                b.append(True)
            else:
                self.phase3_pass = False
                b.append(False)
        if len(test_values[2]["OPP_trip_index"]) == 0:
            self.phase3_pass = False

        self.OPP_trips = [v, a, l, b]
        self.fin_message = [self.phase1_pass, self.phase2_pass, self.phase3_pass, self.scp_pass, self.test_valid, test_values[2]["OPP_trip_load"]]

        # Optional print
        if self.print_results:
            l_phase1 = load[test_values[0]["start_index"]: test_values[0]["stop_index"]]
            l_phase2 = load[test_values[1]["start_index"]: test_values[1]["stop_index"]]
            print(f"voltage: {len(voltage)}, current: {len(current)}, load: {len(load)}")
            print(len(l_phase1))
            for s_index in range(100, 10, -10):
                print(f"sindex = {-s_index} -> {-(s_index - 10)}    |    vals: {l_phase1[-s_index: -(s_index - 10)]}")
            print(l_phase1[-10:])
            print(f"LEN: {len(l_phase2)}    |    100s: {l_phase2.count(100)}    |    "
                  f"0s: {l_phase2.count(0)}    |    First 10: {l_phase2[-130:-110]}")
            for i, x in enumerate(test_values[2]['OPP_trip_index']):
                print(f"load: {load[x]} -> recalcd: {(test_values[2]['OPP_trip_load'])[i]}")

    def write_data_into_file(self, tested_adapter, tested_settings):
        # Open the HDF5 file and write data
        self.test_number += 1
        test_id = f"{tested_adapter.name.upper()}-{datetime.now().strftime('%Y%m%d')}-{self.test_number:03d}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"
        with open('id_tracker.pkl', 'wb') as f:
            pickle.dump({'date': datetime.now().strftime('%Y%m%d'), 'test_number': self.test_number}, f)
        fname = f"TEST_{test_id}.h5"
        with h5py.File("tests/" + fname, 'w') as hdf:

            details_group = hdf.create_group('Test_Details')
            details_group.attrs['ID'] = test_id
            details_group.attrs['File_Name'] = fname
            details_group.attrs['Date'] = datetime.now().strftime('%d.%m.%Y %H:%M')
            details_group.attrs['Tested_Adapter_Name'] = tested_adapter.name
            details_group.attrs['Tested_Adapter_Max_Current'] = tested_adapter.max_current
            details_group.attrs['Tested_Adapter_Expected_Voltage'] = tested_adapter.max_voltage
            details_group.attrs['Tested_Adapter_Min_Set_Voltage'] = tested_adapter.min_voltage
            details_group.attrs['Tested_Adapter_Voltage_Tolerance(%)'] = tested_adapter.v_tol
            details_group.attrs['Tested_Adapter_OPP_Range_Start'] = tested_adapter.OPP_min
            details_group.attrs['Tested_Adapter_OPP_Range_Stop'] = tested_adapter.OPP_max
            details_group.attrs['Phase1_Included'] = tested_settings.phase1[0]
            details_group.attrs['Phase1_No_Reps'] = tested_settings.phase1[1]
            details_group.attrs['Phase1_Passed'] = self.phase1_pass
            details_group.attrs['Phase2_Included'] = tested_settings.phase2[0]
            details_group.attrs['Phase2_No_Reps'] = tested_settings.phase2[1]
            details_group.attrs['Phase2_Passed'] = self.phase2_pass
            details_group.attrs['Phase3_Included'] = tested_settings.phase3[0]
            details_group.attrs['Phase3_No_Reps'] = tested_settings.phase3[1]
            details_group.attrs['Phase3_Look_For_OPP_Trip_times'] = tested_settings.phase3[2]
            details_group.attrs['Phase3_Passed'] = self.phase3_pass
            details_group.attrs['Phase3_Short_Circuit_Passed'] = self.scp_pass
            details_group.attrs['Is_Test_Valid'] = self.test_valid

            # Measured data
            num_rows = len(self.voltage)
            data = np.zeros(num_rows, dtype=[
                ('Voltage Bottom Bound (V)', 'f4'),
                ('Voltage (V)', 'f4'),
                ('Voltage Top Bound (V)', 'f4'),
                ('Current (A)', 'f4'),
                ('Load (%)', 'i4'),
                ('Time (sec)', 'i4'),
                ('Phase', 'i4')
            ])
            # Populate the array
            data['Voltage Bottom Bound (V)'] = np.array(self.bottom_border, dtype=float)
            data['Voltage (V)'] = np.array(self.voltage, dtype=float)
            data['Voltage Top Bound (V)'] = np.array(self.top_border, dtype=float)
            data['Current (A)'] = np.array(self.current, dtype=float)
            data['Load (%)'] = np.array(self.load, dtype=int)
            data['Time (sec)'] = np.array([i for i in range(num_rows)], dtype=int)
            data['Phase'] = np.array(self.phase, dtype=int)
            hdf.create_dataset('Measured_Data', data=data)

            # OPP data
            num_rows = len(self.OPP_trips[0])
            OPP_data = np.zeros(num_rows, dtype=[
                ('Voltage (V)', 'f4'),
                ('Current (A)', 'f4'),
                ('Load (%)', 'f4'),
                ('Within Spec', '?')
            ])
            # Format OPP results
            v = self.OPP_trips[0]
            a = self.OPP_trips[1]
            l = self.OPP_trips[2]
            b = self.OPP_trips[3]
            # Populate the array
            OPP_data['Voltage (V)'] = np.array(v, dtype=float)
            OPP_data['Current (A)'] = np.array(a, dtype=float)
            OPP_data['Load (%)'] = np.array(l, dtype=float)
            OPP_data['Within Spec'] = np.array(b, dtype=bool)
            hdf.create_dataset('OPP_Results', data=OPP_data)
            self.save_graph_to_hdf5(hdf, tested_adapter)

        msg = f"Data successfully saved into file: {fname}"
        print(colorama.Fore.BLUE + msg + colorama.Style.RESET_ALL)
        self.data_storage.add_message(msg, BLUE)

    def save_graph_to_hdf5(self, hdf_file, tested_adapter):
        fig = go.Figure()

        # Voltage interval (shaded area between bounds)
        x_values = [i * 0.1 for i in range(len(self.voltage))]
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.bottom_border,
            mode='lines',
            line=dict(color='darkgray', dash='dash'),
            name='Top Bound'
        ))
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.top_border,
            mode='lines',
            fill='tonexty',  # Fill between this trace and the one before
            fillcolor='rgba(211,211,211,0.5)',  # Light gray with transparency
            line=dict(color='darkgray', dash='dash'),
            name='Bottom Bound'
        ))

        # Voltage (in range)
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.voltage_good,
            mode='lines',
            line=dict(color=YELLOW),
            name='Voltage (V)'
        ))

        # Voltage (out of bounds)
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.voltage_oob,
            mode='lines',
            line=dict(color=RED),
            name='Voltage (V) out of bounds'
        ))

        # Current
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.current,
            mode='lines',
            line=dict(color=BLUE),
            name='Current (A)'
        ))

        # Load (%)
        fig.add_trace(go.Scatter(
            x=x_values,
            y=self.load,
            mode='lines',
            line=dict(color=GREEN),
            name='Load (%)',
            yaxis='y2'
        ))

        # Update layout for dual y-axes
        fig.update_layout(
            xaxis=dict(title='Time (sec)'),
            yaxis=dict(title='Voltage (V) / Current (A)', range=[0, tested_adapter.max_voltage + 1]),
            yaxis2=dict(title='Load (%)', overlaying='y', side='right', range=[0, tested_adapter.OPP_max]),
            legend=dict(x=0, y=-0.2, orientation='h'),
            template='plotly_white'
        )

        fig.update_layout(plot_bgcolor="#3a3a3a", paper_bgcolor="#2a2a2a", font=dict(color="#f4f4f4"))
        fig.update_xaxes(gridcolor="#444444")
        fig.update_yaxes(gridcolor="#444444")

        # Convert the Plotly figure to JSON and store it in h5
        fig_json = json.dumps(fig.to_plotly_json())
        graph_group = hdf_file.create_group('Graph')
        graph_group.create_dataset('Plotly_Figure', data=fig_json)

    def add_OOB_result(self, voltage, current, load, exmin, exmax):
        self.OOB_results.append({
            'voltage': voltage,
            'current': current,
            'load': load,
            'expected_min': exmin,
            'expected_max': exmax
        })


class DisplayedTest:
    def __init__(self, fname):
        self.fname = "tests/" + fname
        self.fig = None
        self.p1 = ""
        self.p2 = ""
        self.p3 = ""
        self.val = ""
        self.scp = ""
        self.test_id = ""
        self.load_info_from_hdf()

    def load_info_from_hdf(self):
        with h5py.File(self.fname, 'r') as hdf:
            details_group = hdf['Test_Details']
            self.p1 = "Passed" if details_group.attrs.get('Phase1_Passed') else "Failed"
            self.p2 = "Passed" if details_group.attrs.get('Phase2_Passed') else "Failed"
            self.p3 = "Passed" if details_group.attrs.get('Phase3_Passed') else "Failed"
            self.val = "Valid" if details_group.attrs.get('Is_Test_Valid') else "Invalid"
            self.scp = "Passed" if details_group.attrs.get('Phase3_Short_Circuit_Passed') else "Failed"
            self.test_id = details_group.attrs.get('ID')

    def load_graph_from_hdf(self):
        with h5py.File(self.fname, 'r') as hdf:
            # Find graph json
            if 'Graph' in hdf and 'Plotly_Figure' in hdf['Graph']:
                fig_json = hdf['Graph']['Plotly_Figure'][()]  # Get json
            else:
                raise ValueError(f"No graph data found in file: {self.fname}")

        # json -> plotly figure
        self.fig = go.Figure(json.loads(fig_json))
        return self.fig

    def download_png(self):
        # Save img as png concert to download and delete the file
        png_file = (self.fname.split("/")[1]).strip(".h5") + ".png"
        self.fig.write_image(png_file, width=1920, height=1080)
        to_sent = dcc.send_file(png_file)
        os.remove(png_file)
        return to_sent

    def download_hdf(self):
        return dcc.send_file(self.fname)

    def download_zip(self):
        zip_name = (self.fname.split("/")[1]).strip(".h5") + ".zip"
        png_file = (self.fname.split("/")[1]).strip(".h5") + ".png"
        self.fig.write_image(png_file, width=1920, height=1080)

        with zipfile.ZipFile(zip_name, 'w') as zipf:
            # Add files to zip
            zipf.write(self.fname, arcname=self.fname.split("/")[-1])
            zipf.write(png_file, arcname=png_file.split("/")[-1])

        to_sent = dcc.send_file(zip_name)
        os.remove(png_file)
        os.remove(zip_name)
        return to_sent

    def delete_hdf(self):
        try:
            os.remove(self.fname)
            # Check if the file still exists
            if not os.path.exists(self.fname):
                return True
            else:
                return False
        except FileNotFoundError:
            return False
        except Exception as e:
            print(f"Error deleting file: {e}")
            return False

