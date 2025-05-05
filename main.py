import os
import signal
import sys
import colorama
import plotly.graph_objects as go
import dash_daq as daq

from time import sleep
from dash import Dash, html, dcc, Input, Output, State, callback_context, no_update, page_container, register_page, \
    get_asset_url
from flask import send_from_directory

from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
from ripple_tester import RippleTester
from subclasses import DisplayedTest, empty_fig
from tester import Tester
from pathlib import Path


class Dashboard(Dash):
    def __init__(self):
        self.tester = Tester()
        self.tester.setup()
        self.update_adapter_dropdowns = False
        self.disp_test = None
        self.adapter_to_delete = None
        self.ripple_tester = None
        super().__init__(use_pages=True, suppress_callback_exceptions=True)
        self.layout = self.create_layout()
        self.register_callbacks()

    def create_graph(self, voltages, currents, load):
        fig = go.Figure()
        if self.tester.settings.high_res:
            x_values = [i * .5 for i in range(len(voltages))]
        elif self.tester.settings.per_sec:
            x_values = [i for i in range(len(voltages))]
        else:
            x_values = [i * .1 for i in range(len(voltages))]

        fig.add_trace(go.Scatter(
            x=x_values,
            y=voltages,
            mode="lines",
            name="Voltage",
            line=dict(color=YELLOW),
            yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=x_values,
            y=currents,
            mode="lines",
            name="Current",
            line=dict(color=BLUE),
            yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=x_values,
            y=load,
            mode="lines",
            name="Load",
            line=dict(color=GREEN),
            yaxis="y2"
        ))
        fig.update_layout(
            xaxis_title="Time (seconds)",
            yaxis=dict(
                title="Voltage (V) / Current (A)",
                range=[0, 6 if self.tester.data_storage.voltage[-1] <= 6 else 12.5]
            ),
            yaxis2=dict(
                title="Load (%)",
                overlaying="y",
                side="right",
                range=[0, 100],
                showgrid=False
            ),
            plot_bgcolor="#3a3a3a",
            paper_bgcolor="#2a2a2a",
            font=dict(color="#f4f4f4")
        )
        fig.update_xaxes(gridcolor="#444444")
        fig.update_yaxes(gridcolor="#444444")

        return fig

    def return_dd_opt(self):
        return [{"label": html.Span(adt.name), "value": str(i)} for i, adt in enumerate(self.tester.testable_adapters.adapters)]

    def return_tests(self):
        directory = Path("tests/")
        # Get all .h5 files and sort by modification time (newest first)
        h5_files = sorted(
            [f for f in directory.iterdir() if f.suffix == '.h5'],
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        # Generate options for the dropdown
        options = []
        for i, f in enumerate(h5_files):
            extracted_id = f.stem.removeprefix('TEST_')
            options.append({"label": html.Span(extracted_id), "value": i})

        return options

    def x_btn(self, id_name: str):
        return html.Button([html.I(className="fa fa-xmark")],id=id_name + "-x-btn",className="x-btn")

    def del_confirm(self, id_name: str):
        return html.Div([
            html.Div([
                html.Span("Are you sure you want to proceed? This action CANNOT be reversed.",
                    style={"color": RED, "text-align": "center", "font-size": "16px", "margin-bottom": "20px", "line-height": "1.5"}
                ),
                html.Div([
                    html.Button("Exit",
                        id="del_conf-" + id_name + "-exit-btn",
                        style={"border": "none", "margin-right": "10px", "color": "white"}
                    ),
                    html.Button("Delete",
                        id="del_conf-" + id_name + "-delete-btn",
                        style={"background-color": RED, "margin-left": "10px", "color": "white"}
                    )
                ], style={"display": "flex", "justify-content": "center", "align-items": "center", "margin-top": "50px"})
            ], className="window delete-conf")
        ], id="del_conf-" + id_name, className="overlay", style={"display": "none"})

    def create_layout(self):
        return html.Div([
            dcc.Interval(id="url-interval", interval=250),
            dcc.Location(id='url', refresh=True),
            page_container
        ])

    def say_starting_message(self, text):
        msg = "To stop the test please use the ORANGE STOP button"
        print(colorama.Fore.BLUE, text, colorama.Style.RESET_ALL)
        self.tester.data_storage.add_message(text, BLUE)
        print(colorama.Fore.LIGHTBLUE_EX, msg, colorama.Style.RESET_ALL)
        self.tester.data_storage.add_message(msg, LIGHT_BLUE)

    def delete_and_recreate_ripple_tester(self):
        self.just_delete_ripple_tester()
        self.ripple_tester = RippleTester()

    def just_delete_ripple_tester(self):
        del self.ripple_tester
        self.ripple_tester = None

    def ripple_start(self, expected_v: str, tol: str, dur: str):
        if self.ripple_tester.start(expected_v, tol, dur):
            msg = f"Starting test, with these values: Voltage:{expected_v}V, Tolerance:{tol}%, Duration:{dur}sec"
            print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
            self.ripple_tester.add_message(msg, GREEN)

        else:
            msg = "Couldn't start test, please check inputted values and try again"
            print(colorama.Fore.RED, msg, colorama.Fore.RESET)
            self.ripple_tester.add_message(msg, RED)

    # Callbacks
    def register_callbacks(self):
        # URL updater
        @self.callback(
            Output("url", "href"),
            Input("url-interval", "n_intervals"),
            prevent_initial_call=True
        )
        def update_url(n):
            # This has to be here or it constantly refreshes the page and you cant output into the same object twice
            if self.tester.data_storage.url == self.tester.data_storage.old_url:
                new_location = no_update
            else:
                new_location = self.tester.data_storage.url
                self.tester.data_storage.old_url = self.tester.data_storage.url
            return new_location

        # Toggle pause state and button color
        @self.callback(
            Output("pause-state", "data"),
            Output("pause-btn", "className"),
            Input("pause-btn", "n_clicks"),
            State("pause-state", "data")
        )
        def toggle_pause(n_clicks, is_paused):
            # Flip the pause state
            if n_clicks:
                is_paused = not is_paused
            # Change button color
            button_class = "fa fa-play" if is_paused else "fa fa-pause"
            msg = "Updates paused" if is_paused else "Updates un-paused"
            self.tester.data_storage.add_message(msg, GRAY)
            print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Style.RESET_ALL)
            return is_paused, button_class

        # Update data-store with the latest data if not paused
        @self.callback(
            Output("data-store", "data"),
            Input("graph-interval", "n_intervals"),
            State("pause-state", "data")
        )
        def update_data_store(n_intervals, is_paused):
            if is_paused:
                return no_update

            return {
                "voltages": self.tester.data_storage.voltage,
                "currents": self.tester.data_storage.current,
                "load": self.tester.data_storage.load,
                "connected": self.tester.is_connected
            }


        # Update the graph and displayed values based on changes in data-store
        @self.callback([
            Output("dynamic-graph", "figure"),
            Output("voltage", "children"),
            Output("current", "children"),
            Output("load", "children"),
            Output("Adapter-connection-status", "className")
            ],
            Input("data-store", "data")
        )
        def update_graph(data):
            g = self.create_graph(data["voltages"], data["currents"], data["load"])
            try:
                res = (g,
                       f"{round(data['voltages'][-1], 2)}V",
                       f"{round(data['currents'][-1], 2)}A",
                       f"{round(data['load'][-1])}%",
                       "Adapter-connection-status connected" if data["connected"] else "Adapter-connection-status disconnected")
            except IndexError:
                res = (g, "Voltage", "Current", "Load", "Adapter-connection-status disconnected")
            return res

        # Get value from adapter-dropdown on change
        @self.callback(
            Input("adapter-type-dropdown", "value")
        )
        def on_adapter_type_change(selected_value):
            msg = f"    Selected adapter : {selected_value}"
            print(colorama.Fore.BLUE, msg, colorama.Style.RESET_ALL)
            self.tester.data_storage.add_message(msg, BLUE)
            if selected_value:
                self.tester.testable_adapters.select_adapter(int(selected_value))
            else:
                self.tester.testable_adapters.select_adapter(None)

        # Single callback to handle both opening/closing adapter management overlay and confirmation
        @self.callback([
                Output("adapter", "style"),
                Output("adapter-plus-error-message", "children"),
                Output("adapter-plus-error-message", "style"),
            ], [
                Input("adapter-plus-btn", "n_clicks"),
                Input("confirm-adapter-plus-btn", "n_clicks"),
                Input("in-adapter-x-btn", "n_clicks")
            ], [
                State("adapter-name", "value"),
                State("max-current", "value"),
                State("max-voltage", "value"),
                State("min-voltage", "value"),
                State("v-tol", "value"),
                State("opp-min", "value"),
                State("opp-max", "value"),
                State("adapter", "style")
            ]
        )
        def manage_adapters(add_clicks, confirm_clicks, x_clicks, name, max_current, max_voltage, min_voltage, v_tol, opp_min, opp_max, style):
            # Determine which input triggered the callback
            ctx = callback_context
            if not ctx.triggered:
                return style, "", {"display": "none"}
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # Handle adapter-plus-btn click (Main page button to open add adapter window)
            if triggered_id == "adapter-plus-btn":
                style["display"] = "block"
                return style, "", {"display": "none"}

            # Handle in-adapter-x-btn click (x button in the overlay)
            elif triggered_id == "in-adapter-x-btn":
                style["display"] = "none"
                return style, "", {"display": "none"}

            # Handle confirm-adapter-plus-btn button click (Confirming submitted data in overlay)
            elif triggered_id == "confirm-adapter-plus-btn":
                parsed = True
                error_message = ""

                # Validate input values
                try:
                    max_current = float(max_current)
                    max_voltage = float(max_voltage)
                    min_voltage = float(min_voltage)
                    v_tol = float(v_tol)
                    opp_min = int(opp_min)
                    opp_max = int(opp_max)
                except ValueError:
                    parsed = False
                    error_message = "Please enter valid numeric values."

                if parsed:
                    if min_voltage < 0 or max_voltage < 0 or max_current < 0:
                        parsed = False
                        error_message = "Please check the values, no negative values allowed"
                    elif max_current > 3.2:
                        parsed = False
                        error_message = "Max current cannot exceed 3.2A."
                    elif max_voltage > 15:
                        parsed = False
                        error_message = "Max voltage cannot exceed 15V."
                    elif min_voltage > max_voltage:
                        parsed = False
                        error_message = "Min voltage needs to be smaller than max voltage."
                    elif opp_min < 100 or opp_min > 250:
                        parsed = False
                        error_message = "OPP min cannot be below 100%."
                    elif opp_max > 250 or opp_max < opp_min:
                        parsed = False
                        error_message = "OPP max cannot exceed 250%, and needs to be bigger than OPP min"
                    elif 0 < v_tol > 100:
                        parsed = False
                        error_message = "Voltage tolerance must be between 0 and 100%."

                if parsed:
                    # Validation successful
                    self.tester.testable_adapters.add_new_adapter(name, max_current, max_voltage, min_voltage, v_tol, opp_min, opp_max)
                    self.update_adapter_dropdowns = True
                    self.tester.data_storage.add_message(f"Adapter with the name: {name}, was added successfully", GREEN)
                    style["display"] = "none"
                    return style, "", {"display": "none"}

                else:
                    # Validation failed
                    return style, error_message, {"color": "red", "display": "block"}

        # Opening / Closing Delete adapter window and deleting the adapter
        @self.callback(
            Output("adapter-delete", "style"),
            Output("adapter-details", "children"),
            Output("del_conf-in-adapter-delete", "style"),
            Input("adapter-minus-btn", "n_clicks"),
            Input("in-adapter-delete-x-btn", "n_clicks"),
            Input("confirm-adapter-minus-btn", "n_clicks"),
            Input("adapter-to-delete", "value"),
            Input("del_conf-in-adapter-delete-exit-btn", "n_clicks"),
            Input("del_conf-in-adapter-delete-delete-btn", "n_clicks"),
            State("adapter-delete", "style"),
            prevent_initial_call=True
        )
        def manage_adapter_delete(add_clicks, x_clicks, del_clicks, selected_value, conf_del_clicks, conf_conf_clicks, style):
            # Determine which input triggered the callback
            children = no_update
            ctx = callback_context
            conf_style = {"display": "none"}
            if not ctx.triggered:
                return style, children, conf_style
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # Handle adapter-minus-btn click (opening from main page)
            if triggered_id == "adapter-minus-btn":
                style["display"] = "block"

            # Handle in-adapter-delete-x-btn click (x button in the overlay)
            elif triggered_id == "in-adapter-delete-x-btn":
                style["display"] = "none"

            # Handle adapter-to-delete dropdown (adapter selection dropdown)
            elif triggered_id == "adapter-to-delete":
                if not selected_value:
                    children = html.P("Select an adapter to view details.", style={"color": GRAY})

                else:
                    selected_value = int(selected_value)
                    adapter = self.tester.testable_adapters.adapters[selected_value]
                    self.adapter_to_delete = selected_value
                    children = html.Table(
                        children=[
                            html.Tr([html.Th("Name"), html.Td(adapter.name, className="table-add-left-border")]),
                            html.Tr([html.Th("Max Current (A)"), html.Td(f"{adapter.max_current:.2f}", className="table-add-left-border")]),
                            html.Tr([html.Th("Max Voltage (V)"), html.Td(f"{adapter.max_voltage:.2f}", className="table-add-left-border")]),
                            html.Tr([html.Th("Min Voltage (V)"), html.Td(f"{adapter.min_voltage:.2f}", className="table-add-left-border")]),
                            html.Tr([html.Th("Voltage Tolerance (%)"), html.Td(f"{adapter.v_tol:.2f}", className="table-add-left-border")]),
                            html.Tr([html.Th("OPP Min"), html.Td(f"{adapter.OPP_min}", className="table-add-left-border")]),
                            html.Tr([html.Th("OPP Max"), html.Td(f"{adapter.OPP_max}", className="table-add-left-border")]),
                        ],
                        style={"width": "100%", "border-collapse": "collapse", "margin-top": "10px"},
                        className="adapter-details-table table"
                    )

            # Handle confirm-adapter-minus-btn click (delete btn in the overlay)
            elif triggered_id == "confirm-adapter-minus-btn":
                if not self.adapter_to_delete:
                    children = html.P("Please select an adapter to delete", style={"color": YELLOW})
                else:
                    conf_style["display"] = "block"

            # Handle del_conf-in-adapter-delete-delete-btn click (confirm delete button in the confirmation overlay)
            elif triggered_id == "del_conf-in-adapter-delete-delete-btn":
                adapter_del_result = self.tester.testable_adapters.delete_adapter(self.adapter_to_delete)
                conf_style["display"] = "none"

                if adapter_del_result["success"]:
                    # Successful deletion of the adapter
                    self.update_adapter_dropdowns = True
                    self.adapter_to_delete = None
                    style["display"] = "none"
                    print(colorama.Fore.RED, adapter_del_result["msg"], colorama.Style.RESET_ALL)
                    self.tester.data_storage.add_message(adapter_del_result['msg'], RED)

                else:
                    children = [
                        html.Span("The adapter couldnt be deleted due to this error. Please try again", style={"color": RED}),
                        html.Span(adapter_del_result["msg"], style={"color": RED}),
                            ]

            elif triggered_id == "del_conf-in-adapter-delete-exit-btn":
                conf_style["display"] = "none"

            return style, children, conf_style

        # Opening / Closing of the past test window
        @self.callback(
            Output("tests", "style"),
            Input("past-tests-btn", "n_clicks"),
            Input("in-tests-x-btn", "n_clicks"),
            State("tests", "style"),
            prevent_initial_call=True
        )
        def manage_tests(add_clicks, x_clicks, style):
            # Determine which input triggered the callback
            ctx = callback_context
            if not ctx.triggered:
                return style
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # Handle past-tests-btn click (opening from main page)
            if triggered_id == "past-tests-btn":
                style["display"] = "block"

            # Handle in-tests-x-btn click (x button in the overlay)
            elif triggered_id == "in-tests-x-btn":
                style["display"] = "none"

            return style

        # Start Button Callback
        @self.callback(
            Input("start-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def handle_start_button(n_clicks):
            # Adapter is not connected
            if not self.tester.is_connected:
                msg = "Adapter isn't connected, please connect an adapter ..."
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            # Adapter isnt selected
            elif self.tester.testable_adapters.selected_adapter is None:
                msg = "Adapter isn't selected"
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            # Test is running or stopping
            elif self.tester.wait_to_stop or self.tester.is_running:
                msg = "Test is still running, PLEASE WAIT ..."
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            # Starting test
            else:
                self.say_starting_message("Starting test ...")
                self.tester.start()

        # Stop Button Callback
        @self.callback(
            Input("stop-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def handle_stop_button(n_clicks):
            res = self.tester.stop()
            if res == "stopping":
                msg = "Stopping test ..."
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            elif res == "waiting":
                msg = "Waiting for the test to stop, PLEASE WAIT ..."
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            elif res == "idle":
                msg = "Test isnt running => cant stop anything"
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

        # Shutdown Button Callback
        @self.callback(
            Input("shutdown-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def handle_shutdown_button(n_clicks):
            msg = "Shutting down ..."
            print(colorama.Fore.RED, msg, colorama.Style.RESET_ALL)
            self.tester.data_storage.add_message(msg, RED)
            self.tester.shutdown()
            os.kill(os.getpid(), signal.SIGTERM)

        # Constant load Button Callback
        @self.callback(
            Output("load-input", "value"),
            Input("constant-btn", "n_clicks"),
            State("load-input", "value"),
            prevent_initial_call=True
        )
        def handle_constant_load_button(n_clicks, value):
            try:
                value = float(value)
            except (TypeError, ValueError):
                return no_update

            # Adapter isnt selected
            if self.tester.testable_adapters.selected_adapter is None:
                msg = "Adapter isn't selected"
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            # Adapter is not connected
            elif not self.tester.is_connected:
                msg = "Adapter isnt connected, please connect an adapter ..."
                print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, ORANGE)

            # Starting constant load
            else:
                self.say_starting_message(f"Running with constant load: {value}A")
                self.tester.start_constant_load(value)
            return ""

        # Managing (test) files window
        # Get value from past-tests-dropdown on change and handle delete
        @self.callback([
            Output("past-graph", "figure"),
            Output("past-tests-dropdown", "value"),
            Output("t-tab-p1", "children"),
            Output("t-tab-p2", "children"),
            Output("t-tab-p3", "children"),
            Output("t-tab-val", "children"),
            Output("t-tab-scp", "children"),
            Output("t-tab-id", "children"),
            Output("del_conf-in-tests", "style")
            ], [
            Input("past-tests-dropdown", "value"),
            Input("delete", "n_clicks"),
            Input("tests-refresh", "n_clicks"),
            Input("del_conf-in-tests-exit-btn", "n_clicks"),
            Input("del_conf-in-tests-delete-btn", "n_clicks"),
            ],
            State("past-tests-dropdown", "options"),
            prevent_initial_call=True
        )
        def on_past_tests_change(selected_value, del_clicks, ref_clicks, del_exit_clicks, del_del_clicks, options):
            default_return = [no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update]
            ctx = callback_context
            conf_style = {"display": "none"}
            if not ctx.triggered:
                return default_return
            trigger_id = ctx.triggered[0]["prop_id"]

            if "past-tests-dropdown" in trigger_id:
                if selected_value is None:
                    self.disp_test = None
                    default_return[0] = empty_fig
                    default_return[1] = None
                    return default_return

                # Find the corresponding label from the options
                selected_label = next(
                    (option["label"]["props"]["children"] for option in options if option["value"] == selected_value), None  # The filename is in a span so it needs to be extracted like this
                )
                msg = f"    Selected test: {selected_label}"
                print(colorama.Fore.BLUE, msg, colorama.Style.RESET_ALL)
                self.tester.data_storage.add_message(msg, BLUE)
                self.disp_test = DisplayedTest(f"TEST_{selected_label}.h5")
                return self.disp_test.load_graph_from_hdf(), no_update, self.disp_test.p1, self.disp_test.p2, self.disp_test.p3, self.disp_test.val, self.disp_test.scp, self.disp_test.test_id, no_update

            elif trigger_id == "delete.n_clicks":
                if self.disp_test is None:
                    msg = "There is no test currently selected"
                    self.tester.data_storage.add_message(msg, ORANGE)
                    print(colorama.Fore.YELLOW, msg, colorama.Style.RESET_ALL)
                else:
                    conf_style["display"] = "block"
                    default_return[-1] = conf_style

            elif trigger_id == "del_conf-in-tests-delete-btn.n_clicks":
                if self.disp_test.delete_hdf():
                    self.disp_test = None
                    default_return[0] = empty_fig
                    default_return[1] = None
                    default_return[-1] = conf_style
                    self.tester.update_ptd = True
                    return default_return

                else:
                    msg = "There was an error deleting the test"
                    default_return[-1] = conf_style

            elif trigger_id == "tests-refresh.n_clicks":
                self.tester.update_ptd = True
                return default_return

            elif trigger_id == "del_conf-in-tests-exit-btn.n_clicks":
                default_return[-1] = conf_style

            return default_return

        # PNG
        @self.callback(
            Output("png-download", "data"),
            Input("png", "n_clicks"),
            prevent_initial_call=True
        )
        def download_png(n_clicks):
            if n_clicks and self.disp_test is not None:
                return self.disp_test.download_png()
            return no_update

        # H5
        @self.callback(
            Output("h5-download", "data"),
            Input("h5", "n_clicks"),
            prevent_initial_call=True
        )
        def download_hdf(n_clicks):
            if n_clicks and self.disp_test is not None:
                return self.disp_test.download_hdf()
            return no_update

        # ZIP
        @self.callback(
            Output("zip-download", "data"),
            Input("zip", "n_clicks"),
            prevent_initial_call=True
        )
        def download_zip(n_clicks):
            if n_clicks and self.disp_test is not None:
                return self.disp_test.download_zip()
            return no_update

        # CMD interval, also handles other visual updates
        @self.callback(
            Output("cmd", "children"),
            Output("stop-btn", "className"),
            Output("adapter-type-dropdown", "options"),
            Output("adapter-to-delete", "options"),
            Output("past-tests-dropdown", "options"),
            Input("cmd-interval", "n_intervals"),
            State("cmd", "children"),
            State("stop-btn", "className"),
            prevent_initial_call=True
        )
        def update_cmd(n_intervals, current_children, bc):
            # Some other things that update with this interval
            dd1 = no_update
            dd2 = no_update
            if self.update_adapter_dropdowns:
                self.update_adapter_dropdowns = False
                dd1 = self.return_dd_opt()
                dd2 = self.return_dd_opt()

            # Stop button color change
            btnclass = no_update
            if bc == "stop-btn-off" and self.tester.is_running:
                # If test is running enable button
                btnclass = "stop-btn"
            elif bc == "stop-btn" and not self.tester.is_running:
                # If test is not running disable button
                btnclass = "stop-btn-off"

            new_children = []
            for msg in self.tester.data_storage.messages:
                # Check if the message is an html.Div
                if msg['color'] == "TEST RESULTS":
                    # msg['text'] structure: [timestamp, p1_pass, p2_pass, p3_pass, scp_pass, test_valid, OPP_trips]
                    msg_style = {"color": LIGHT_BLUE, "fontSize": "13px"}
                    pass_style = {"fontSize": "13px", "font-weight": "bold"}
                    timestamp, p1_pass, p2_pass, p3_pass, scp_pass, test_valid, OPP_trips = msg['text']
                    new_children.append(html.Div([
                        html.Span(timestamp, style={"color": "#888", "fontWeight": "bold", "fontSize": "13px", "margin-right": "25px"}),
                        html.Div([
                            html.Span("Test summary:", style={"color": BLUE, "fontSize": "13px"}), html.Br(), html.Br(),
                            html.Div([
                                html.Span("  Phase 1:                  ", style=msg_style),
                                html.Span(f"{'PASS' if p1_pass else 'FAIL'}", style={"color": GREEN if p1_pass else RED} | pass_style)
                            ]),
                            html.Div([
                                html.Span("  Phase 2:                  ", style=msg_style),
                                html.Span(f"{'PASS' if p2_pass else 'FAIL'}", style={"color": GREEN if p2_pass else RED} | pass_style)
                            ]),
                            html.Div([
                                html.Span("  Phase 3:                  ", style=msg_style),
                                html.Span(f"{'PASS' if p3_pass else 'FAIL'}", style={"color": GREEN if p3_pass else RED} | pass_style)
                            ]),
                            html.Div([
                                html.Span("  Short Circuit protection: ", style=msg_style),
                                html.Span(f"{'PASS' if scp_pass else 'FAIL'}", style={"color": GREEN if scp_pass else RED} | pass_style)
                            ]),
                            html.Div([
                                html.Span("  Test Validity:            ", style=msg_style),
                                html.Span(f"{'VALID' if test_valid else 'INVALID'}", style={"color": GREEN if test_valid else RED} | pass_style)
                            ]),
                            html.Div([
                                html.Span("  OPP trips:                ", style=msg_style),
                                html.Span(f"{', '.join([str(x) for x in OPP_trips]) if OPP_trips else 'N/A'}",style={"color": YELLOW} | pass_style)
                            ]),
                        ], style={}),
                    ], className="fin-message"))

                else:
                    # Process the message as a string
                    timestamp, message = msg["text"].split(";", 1)
                    new_children.append(html.Div([
                        html.Span(timestamp, style={"color": "#555", "fontWeight": "bold", "fontSize": "13px"}),
                        html.Span(message, style={"color": msg["color"], "marginLeft": "5px", "fontSize": "13px"})
                    ]))

            combined_children = (current_children or []) + new_children
            combined_children = combined_children[-250:]
            self.tester.data_storage.messages.clear()
            if self.tester.update_ptd:
                self.tester.update_ptd = False
                tests = self.return_tests()
            else:
                tests = no_update
            return combined_children, btnclass, dd1, dd2, tests

        # Opening / Closing of the descriptions window
        @self.callback(
            Output("description", "style"),
            Input("descriptions-btn", "n_clicks"),
            Input("in-description-x-btn", "n_clicks"),
            State("description", "style"),
            prevent_initial_call=True
        )
        def manage_tests_window(add_clicks, x_clicks, style):
            # Determine which input triggered the callback
            ctx = callback_context
            if not ctx.triggered:
                return style
            triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

            # Handle descriptions-btn click (opening from main page)
            if triggered_id == "descriptions-btn":
                style["display"] = "block"

            # Handle in-description-x-btn click (x button in the overlay)
            elif triggered_id == "in-description-x-btn":
                style["display"] = "none"

            return style

        # Opening ripple page
        @self.callback(
            Input("ripple-btn", "n_clicks"),
            prevent_initial_call=True
        )
        def manage_ripple_window(n_clicks):
            if n_clicks:
                self.tester.data_storage.url = "/ripple"

        # Opening / Closing settings window
        @self.callback(
            Output("sidebar", "className"),
            Input("settings-btn", "n_clicks"),
            State("sidebar", "className"),
        )
        def toggle_sidebar(n_clicks, current_class):
            if n_clicks:
                return "sidebar sidebar-active" if "sidebar-active" not in current_class else "sidebar"
            return "sidebar"

        # Validating and saving settings
        @self.callback(
            Output("overlay-seconds-toggle", "className"),
            Input("settings-conf-btn", "n_clicks"),

            State("max-current-input", "value"),
            State("safety-toggle", "value"),
            State("seconds-toggle", "value"),
            State("resolution-toggle", "value"),
            State("phase-1-include", "value"),
            State("phase-1-repeat", "value"),
            State("phase-2-include", "value"),
            State("phase-2-repeat", "value"),
            State("phase-3-include", "value"),
            State("phase-3-repeat", "value"),
            State("phase-3-opp", "value"),
            State("max-message-num", "value"),
            prevent_initial_call=True
        )
        def toggle_sidebar(n_clicks, mcs_val, sf_val, ps_val, hr_val, p1incl_val, p1rep_val, p2incl_val, p2rep_val, p3incl_val, p3rep_val, p3opp_val, max_message):
            if n_clicks:
                res = self.tester.settings.new_values(mcs_val, sf_val, ps_val, hr_val,
                                                      p1incl_val == ["include"], p1rep_val,
                                                      p2incl_val == ["include"], p2rep_val,
                                                      p3incl_val == ["include"], p3rep_val, p3opp_val)
                try:
                    max_message = int(max_message)
                    if 99 > max_message > 5000:
                        raise TypeError
                    self.tester.data_storage.max_len = max_message
                except TypeError:
                    self.tester.data_storage.add_message("Max number of messages needs to be a number between 100 and 5000", RED)
                    return no_update
                if res["parsed"]:
                    self.tester.data_storage.add_message(res["msg"], GREEN)
                    self.tester.data_storage.clear()
                    if self.tester.settings.high_res:
                        self.tester.switch_to_high_res()
                        return "freq-disabled"

                    else:
                        self.tester.switch_to_low_res()
                        return "freq-enabled"

                else:
                    self.tester.data_storage.add_message(res["msg"], RED)
                    return no_update

            return no_update


if __name__ == "__main__":
    app = Dashboard()
    app.run_server(host="0.0.0.0", port=8050, debug=True)

