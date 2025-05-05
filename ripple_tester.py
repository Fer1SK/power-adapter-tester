import json
import os
import pickle
import random
import string
import threading
import zipfile
from datetime import datetime
from dash import dcc, register_page, html, get_app, Output, Input, no_update
from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
import numpy as np
import h5py
import plotly.graph_objects as go

class RippleTester:
    def __init__(self):
        self.voltage = []
        self.expected_voltage: float = 0.0
        self.tolerance: float = 0.0
        self.min_voltage: float = 0.0
        self.max_voltage: float = 0.0
        self.avg_voltage: float = 0.0
        self.top_quartile: float = 0.0
        self.bottom_quartile: float = 0.0
        self.bottom_limit: float = 0.0
        self.top_limit: float = 0.0
        self.passed: bool = True
        self.line_graph = None
        self.box_graph = None
        self.file = None
        self.is_running: bool = False
        self.is_waiting_to_display: bool = False
        self.timer_max: int = 0
        self.timer: int = 0
        self.graph_data = {
            "v_ok": [],
            "v_oob": [],
            "bottom_border": [],
            "top_border": [],
        }
        self.process_thread = None
        self.messages = []
        self.test_id: str = ""
        self.load_test_id()

    def start(self, ev, t, m):
        try:
            self.expected_voltage = float(ev)
            self.tolerance = float(t)
            self.timer_max = int(m)
            if not 0 < self.expected_voltage <= 15:
                raise TypeError
            if not 0 < self.tolerance <= 100:
                raise TypeError
            if not 10 <= self.timer_max <= 120:
                raise TypeError
        except TypeError:
            return False

        self.is_running = True
        return True

    def stop(self, v: [float]):
        self.timer = 0
        self.voltage = v
        self.process_thread = threading.Thread(target=self.run_test_analysis)
        self.process_thread.start()

    def load_test_id(self, file_name='ripple_id_tracker.pkl'):
        current_date = datetime.now().strftime('%Y%m%d')
        try:
            with open(file_name, 'rb') as f:
                data = pickle.load(f)
                stored_date = data.get('date', '')
                test_number = data.get('test_number', 1)

            if stored_date == current_date:
                test_number += 1
            else:
                test_number = 1
                with open(file_name, 'wb') as f:
                    pickle.dump({'date': current_date, 'test_number': test_number}, f)

        except (FileNotFoundError, EOFError):
            test_number = 1
            with open(file_name, 'wb') as f:
                pickle.dump({'date': current_date, 'test_number': test_number}, f)

        self.test_id = f"ripple-test-{datetime.now().strftime('%Y%m%d')}-{test_number:03d}-{''.join(random.choices(string.ascii_uppercase + string.digits, k=4))}"

    def load_from_file(self, file_name: str):
        with h5py.File(f"ripple_tests/{file_name}.h5", 'r') as hdf:
            details_group = hdf['Test_Details']
            self.test_id = details_group.attrs.get('ID')
            self.expected_voltage = details_group.attrs.get('Tested_Adapter_Expected_Voltage')
            self.tolerance = details_group.attrs.get('Tested_Adapter_Voltage_Tolerance(%)')
            self.timer_max = details_group.attrs.get('Test_length(sec)')
            self.passed = "Passed" if details_group.attrs.get('Pass_Fail') else "Failed"
            self.top_limit = details_group.attrs.get('Top_Limit')
            self.bottom_limit = details_group.attrs.get('Bottom_Limit')
            self.top_quartile = details_group.attrs.get('Top_Quartile')
            self.bottom_quartile = details_group.attrs.get('Bottom_Quartile')
            self.max_voltage = details_group.attrs.get('Max_Voltage')
            self.min_voltage = details_group.attrs.get('Min_Voltage')
            self.voltage = hdf['Measured_Data']['Voltage (V)'][:]
            self.graph_data = json.loads(hdf['Graph_Data'][()])
        self.create_graphs()
        self.wait_to_display()

    def run_test_analysis(self):
        # Calculate the necessary values
        self.min_voltage = np.min(self.voltage)
        self.max_voltage = np.max(self.voltage)
        self.avg_voltage = np.mean(self.voltage)
        self.top_quartile = np.percentile(self.voltage, 75)
        self.bottom_quartile = np.percentile(self.voltage, 25)

        self.bottom_limit = self.expected_voltage * (100 - self.tolerance) / 100
        self.top_limit = self.expected_voltage * (100 + self.tolerance) / 100
        last_v = 0
        was_last_ok = True

        # Plot bounds and Evaluate
        for v in self.voltage:
            self.graph_data["bottom_border"].append(self.bottom_limit)
            self.graph_data["top_border"].append(self.top_limit)
            if not self.bottom_limit < v < self.top_limit:
                # Voltage is out of bounds
                if was_last_ok and len(self.graph_data["v_oob"]) > 0:
                    self.graph_data["v_oob"].pop()
                    self.graph_data["v_oob"].append(last_v)

                self.graph_data["v_ok"].append(None)
                self.graph_data["v_oob"].append(v)
                was_last_ok = False
                self.passed = False

            else:
                # Voltage is not out of bounds
                if not was_last_ok:
                    self.graph_data["v_oob"].append(v)
                else:
                    self.graph_data["v_oob"].append(None)
                self.graph_data["v_ok"].append(v)
                was_last_ok = True

            last_v = v
        self.create_graphs()
        fname = f"ripple_tests/{self.test_id}.h5"
        with h5py.File(fname, 'w') as hdf:
            details_group = hdf.create_group('Test_Details')
            details_group.attrs['ID'] = self.test_id
            details_group.attrs['File_Name'] = fname
            details_group.attrs['Date'] = datetime.now().strftime('%d.%m.%Y %H:%M')
            details_group.attrs['Tested_Adapter_Expected_Voltage'] = self.expected_voltage
            details_group.attrs['Tested_Adapter_Voltage_Tolerance(%)'] = self.tolerance
            details_group.attrs['Test_length(sec)'] = self.timer_max
            details_group.attrs['Pass_Fail'] = self.passed
            details_group.attrs['Top_Limit'] = self.top_limit
            details_group.attrs['Bottom_Limit'] = self.bottom_limit
            details_group.attrs['Top_Quartile'] = self.top_quartile
            details_group.attrs['Bottom_Quartile'] = self.bottom_quartile
            details_group.attrs['Min_Voltage'] = self.min_voltage
            details_group.attrs['Max_Voltage'] = self.max_voltage

            # Measured data
            num_rows = len(self.voltage)
            data = np.zeros(num_rows, dtype=[
                ('Voltage Bottom Bound (V)', 'f4'),
                ('Voltage (V)', 'f4'),
                ('Voltage Top Bound (V)', 'f4'),
                ('Time (sec)', 'i4'),
            ])
            # Populate the array
            data['Voltage Bottom Bound (V)'] = np.array(self.graph_data["bottom_border"], dtype=float)
            data['Voltage (V)'] = np.array(self.voltage, dtype=float)
            data['Voltage Top Bound (V)'] = np.array(self.graph_data["top_border"], dtype=float)
            data['Time (sec)'] = np.array([i for i in range(num_rows)], dtype=int)
            hdf.create_dataset('Measured_Data', data=data)
            hdf.create_dataset('Graph_Data', data=json.dumps(self.graph_data))

        with open('ripple_id_tracker.pkl', 'wb') as f:
            pickle.dump({'date': datetime.now().strftime('%Y%m%d'), 'test_number': int(self.test_id.split("-")[3])}, f)
        self.is_waiting_to_display = True
        self.is_running = False

    def create_graphs(self):
        self.line_graph = go.Figure()

        # Voltage interval (shaded area between bounds)
        x_values = [i * 0.1 for i in range(len(self.voltage))]
        self.line_graph.add_trace(go.Scatter(
            x=x_values,
            y=self.graph_data["top_border"],
            mode='lines',
            line=dict(color='darkgray', dash='dash'),
            name='Top Bound'
        ))
        self.line_graph.add_trace(go.Scatter(
            x=x_values,
            y=self.graph_data["bottom_border"],
            mode='lines',
            fill='tonexty',
            fillcolor='rgba(211,211,211,0.5)',
            line=dict(color='darkgray', dash='dash'),
            name='Bottom Bound'
        ))

        # Voltage (in range)
        self.line_graph.add_trace(go.Scatter(
            x=x_values,
            y=self.graph_data["v_ok"],
            mode='lines',
            line=dict(color=YELLOW),
            name='Voltage (V)'
        ))

        # Voltage (out of bounds)
        self.line_graph.add_trace(go.Scatter(
            x=x_values,
            y=self.graph_data["v_oob"],
            mode='lines',
            line=dict(color=RED),
            name='Voltage (V) out of bounds'
        ))

        # Update layout for dual y-axes
        self.line_graph.update_layout(
            xaxis=dict(title='Time (sec)'),
            yaxis=dict(title='Voltage (V)', range=[
                ((self.min_voltage - 0.1) if self.min_voltage < self.bottom_limit else self.bottom_limit - 0.1),
                ((self.max_voltage + 0.1) if self.max_voltage > self.top_limit else self.top_limit + 0.1)
            ]),
            legend=dict(x=0, y=-0.2, orientation='h'),
            template='plotly_white',
            margin=dict(t=25, b=25, l=25, r=25),
        )
        self.line_graph.update_layout(plot_bgcolor="#3a3a3a", paper_bgcolor="#2a2a2a", font=dict(color="#f4f4f4"))
        self.line_graph.update_xaxes(gridcolor="#444444")
        self.line_graph.update_yaxes(gridcolor="#444444")

        self.box_graph = go.Figure()
        # Create the box plot for voltage distribution
        self.box_graph.add_trace(go.Box(
            y=self.voltage,
            boxmean='sd',
            name="Voltage Distribution",
            marker=dict(color="rgba(0,128,255,0.6)"),
            line=dict(color="blue"),
            whiskerwidth=0.5,
            fillcolor="rgba(0,128,255,0.2)"
        ))

        self.box_graph.update_layout(
            title=dict(text="Voltage Distribution Box Plot", font=dict(size=12)),
            xaxis=dict(title='Voltage (V)'),
            yaxis=dict(title='Voltage (V)', range=[self.min_voltage - .1, self.max_voltage + .1]),
            template='plotly_white',
            plot_bgcolor="#3a3a3a",
            paper_bgcolor="#2a2a2a",
            font=dict(color="#f4f4f4"),
            showlegend=False,
            margin=dict(t=25, b=25, l=25, r=25),
        )
        self.box_graph.update_xaxes(gridcolor="#444444")
        self.box_graph.update_yaxes(gridcolor="#444444")

    def add_message(self, text, color):
        max_len = 25  # Change to display more / fewer messages in GUI
        timestamp = f"[{datetime.now().strftime('%H:%M:%S')}]"
        self.messages.append({
            "text": f"{timestamp};{text.strip()}",
            "color": color
        })
        if len(self.messages) > max_len:
            self.messages.pop(0)

    def wait_to_display(self):
        self.is_waiting_to_display = True

    def is_not_waiting_to_display(self):
        self.is_waiting_to_display = False

    def download_hdf(self):
        return f"ripple_tests/{self.test_id}.h5"

    def download_png(self):
        # Save imgs as pngs concert to download and delete the file
        png_file1 = f"{self.test_id}-line.png"
        png_file2 = f"{self.test_id}-box.png"
        self.line_graph.write_image(png_file1, width=1920, height=1080)
        self.box_graph.write_image(png_file2, width=1920, height=1080)
        return png_file1, png_file2

    def download_zip(self):
        zip_name = f"{self.test_id}.zip"
        h5name = self.download_hdf()
        png1, png2 = self.download_png()

        with zipfile.ZipFile(zip_name, 'w') as zipf:
            # Add files to zip
            zipf.write(h5name, arcname=h5name)
            zipf.write(png1, arcname=png1)
            zipf.write(png2, arcname=png2)

        to_sent = dcc.send_file(zip_name)
        os.remove(png1)
        os.remove(png2)
        os.remove(zip_name)
        return to_sent

    def delete(self):
        os.remove(self.download_hdf())