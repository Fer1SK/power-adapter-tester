from dash import Dash, html, dcc, Input, Output, State, callback_context, no_update, page_container, register_page, \
    get_app, get_asset_url
from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
from subclasses import empty_fig
import dash_daq as daq

app = get_app()
register_page(
    name="Adapter Tester",
    module=__name__,
    path="/",
    layout=html.Div([
        html.Header([
            html.Link(href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.1/css/all.min.css", rel="stylesheet")
        ]),
        # Controls section
        html.Div([
            html.Div([
                html.Button([html.I(className="fa fa-power-off")], id="shutdown-btn", className="shutdown-btn", title="Turn the app off"),
            ], className="controls-sub-divider sub-shutdown"),
            # Play / Pause btn
            html.Div([
                html.Button([html.I(className="fa fa-play")], id="start-btn", className="start-btn", title="Start a new test, using selected adapter"),
                html.Button([html.I(className="fa fa-stop")], id="stop-btn", className="stop-btn-off", title="Stop the test if one is running"),
            ], className="controls-sub-divider sub-start-stop"),

            # Main controls
            html.Div([
                html.Div([
                    html.Button([html.I(className="fa fa-file-export")], id="past-tests-btn", className="past-tests-btn", title="View past tests and export graphs and/or data"),
                    html.Button([html.I(className="fa-solid fa-wave-square")], id="ripple-btn", className="ripple-btn", title="View ripple test screen and run a test or export data"),
                    html.Button([html.I(className="fa-solid fa-info")], id="descriptions-btn", className="descriptions-btn", title="Help / Description of the GUI"),
                    html.Button([html.I(className="fa-solid fa-gears")], id="settings-btn", className="settings-btn", title="View settings page"),
                ], className="controls-sub-sub-divider-top"),
                html.Div([
                    dcc.Input(type="number", placeholder="Enter load (A)", className="in load-input", min=0, max=3.2, id="load-input"),
                    html.Button([html.I(className="fa fa-plug-circle-bolt")], id="constant-btn", className="constant-btn", title="Start a constant load on selected adapter. Stop the load using the stop button"),
                ], className="controls-sub-sub-divider-bottom")
            ], className="controls-sub-divider sub-main"),

            # Adapter selection dropdown
            html.Div([
                dcc.Dropdown(id="adapter-type-dropdown", options=app.return_dd_opt(), placeholder="Select Adapter Type", className="dropdown adapter-type-dropdown"),
                html.Button([html.I(className="fa fa-plug-circle-plus")], id="adapter-plus-btn", className="adapter-plus-btn", title="Add new adapter"),
                html.Button([html.I(className="fa fa-plug-circle-minus")], id="adapter-minus-btn", className="adapter-minus-btn", title="Remove one of the existing adapters"),
            ], className="controls-sub-divider sub-adapter"),

        ], className="window controls"),

        # Main graph section
        html.Div([
            html.Div([
                dcc.Store(id="data-store"),
                dcc.Store(id="pause-state", data=False),
                dcc.Interval(id="graph-interval", interval=1000),
                html.Div([
                    html.Div([], id="Adapter-connection-status", className="adapter-connection-status disconnected", title="Green = Adapter connected, Red = Adapter disconnected"),
                    html.Div([
                        html.H4("Voltage", className="data-number", id="voltage"),
                        html.H4("Current", className="data-number", id="current"),
                        html.H4("Load", className="data-number", id="load"),
                    ], className="data-container"),
                    html.Button([html.I(className="")], id="pause-btn", className="pause-btn-active", title="Pause updates, to interact with the graph"),
                ], className="graph-info-container"),
                dcc.Graph(id="dynamic-graph", className="graph")
            ], className="graph-container", id="graph-container"),
            # CMD section
            dcc.Interval(id="cmd-interval", interval=1000),
            html.Div([], className="cmd", id="cmd"),
        ], className="graph-cmd-container", id="graph-cmd-container"),

        # New adapter overlay
        html.Div([
            html.Div([
                html.H3("Add New Adapter"),
                app.x_btn("in-adapter"),
                html.Div(id="adapter-plus-error-message", style={"color": "red", "display": "none"}),
                html.Br(),
                html.Div([
                    dcc.Input(id="adapter-name", type="text", placeholder="Adapter Name", className="in adapter-plus-in"),
                    html.Div([
                        dcc.Input(id="max-current", type="number", placeholder="Max Current",className="in adapter-plus-in"),
                        dcc.Input(id="max-voltage", type="number", placeholder="Max Voltage",className="in adapter-plus-in"),
                    ], className="adapter-plus-in-one-line"),

                    html.Div([
                        dcc.Input(id="min-voltage", type="number", placeholder="Min Voltage",className="in adapter-plus-in"),
                        dcc.Input(id="v-tol", type="number", placeholder="Voltage Tolerance (%)",className="in adapter-plus-in"),
                    ], className="adapter-plus-in-one-line"),

                    html.Div([
                        dcc.Input(id="opp-min", type="number", placeholder="OPP Min", className="in adapter-plus-in"),
                        dcc.Input(id="opp-max", type="number", placeholder="OPP Max", className="in adapter-plus-in"),
                    ], className="adapter-plus-in-one-line"),
                ], className="adapter-plus-in-stacker"),
                html.Div(
                    html.Button([html.I(className="fa fa-check")], id="confirm-adapter-plus-btn", className="confirm-adapter-plus-btn", title="Check submitted info and add new adapter"),
                    style={"display": "flex", "justify-content": "center", "margin-top": "20px"})], className="window adapter-management")

        ], id="adapter", className="overlay", style={"display": "none"}),

        # Delete adapter overlay
        html.Div([
            html.Div([
                html.H3("Delete Adapter", style={"margin": "0 0 10px"}),
                app.x_btn("in-adapter-delete"),
                dcc.Dropdown(
                    id="adapter-to-delete",
                    options=app.return_dd_opt(),
                    placeholder="Select an adapter to delete",
                    className="dropdown adapter-to-delete"
                ),
                html.Div(id="adapter-details", className="details-container", style={"margin-top": "10px"}),
                html.Div(
                    html.Button([html.I(className="fa fa-trash-can")], id="confirm-adapter-minus-btn", className="confirm-adapter-minus-btn", title="Delete selected adapter"),
                    style={"display": "flex", "justify-content": "center", "margin-top": "20px"})
            ], className="window adapter-management")
        ], id="adapter-delete", className="overlay", style={"display": "none"}),

        # Past tests overlay
        html.Div([
            html.Div([
                html.H3("Past Tests"),
                app.x_btn("in-tests"),
                html.Div([
                    # Table
                    html.Table([
                        html.Tr([html.Td("Phase 1:"), html.Td("Pending", id="t-tab-p1"), html.Td("Overall Validity:", className="table-add-left-border"), html.Td("Pending", id="t-tab-val")]),
                        html.Tr([html.Td("Phase 2:"), html.Td("Pending", id="t-tab-p2"), html.Td("Short Circuit Test:", className="table-add-left-border"), html.Td("Pending", id="t-tab-scp")]),
                        html.Tr([html.Td("Phase 3:"), html.Td("Pending", id="t-tab-p3"), html.Td("Test id:", className="table-add-left-border"), html.Td("Pending", id="t-tab-id")]),
                    ], className="table"),

                    # Dropdown and Delete Button
                    html.Div([
                        dcc.Dropdown(
                            id="past-tests-dropdown",
                            options=app.return_tests(),
                            placeholder="Select Test",
                            className="dropdown tests-dropdown"
                        ),
                    ], className="tests-info-group"),

                    # Buttons
                    html.Div([
                        html.Button([html.I(className="fa fa-rotate-right")], id="tests-refresh", className="download-btn", title="Refresh tests"),
                        html.Button([html.I(className="fa fa-chart-line"),html.I(className="fa fa-download")], id="png", className="download-btn", title="Download image of the currently selected graph"),
                        html.Button([html.I(className="fa fa-file-lines"),html.I(className="fa fa-download")], id="h5", className="download-btn", title="Download .h5 file including data and graph"),
                        html.Button([html.I(className="fa fa-file-zipper"),html.I(className="fa fa-download")], id="zip", className="download-btn", title="Download a zip folder containing graph image and .h5 file"),
                        html.Button([html.I(className="fa fa-trash-can")], id="delete", className="download-btn delete", title="Delete the selected test"),
                        dcc.Download(id="png-download"),
                        dcc.Download(id="h5-download"),
                        dcc.Download(id="zip-download"),
                    ], className="tests-info-group")
                ], id="tests-info-container", className="tests-info-container"),
                dcc.Graph(id="past-graph", className="graph", figure=empty_fig)
            ], className="window tests")
        ], id="tests", className="overlay", style={"display": "none"}),

        # Elements description overlay
        html.Div([
            html.Div([
                app.x_btn("in-description"),
                html.Div([
                    dcc.Tabs([
                        dcc.Tab(label="Main Page", children=[
                            html.H3("Main Page Features"),
                            html.Img(src="/assets/buttons_screenshot.png", alt="Main Page Screenshot", className="screenshot"),
                            html.Div([
                                html.P([
                                    html.Span("1. Shutdown: ", style={"color": RED, "font-weight": "bold"}),
                                    "Shuts the app down completely. You will need to restart it to use it again."
                                ]),
                                html.P([
                                    html.Span("2. Start Test: ", style={"color": GREEN, "font-weight": "bold"}),
                                    "Runs the automatic test. Make sure to select an adapter from the dropdown (11) first."
                                ]),
                                html.P([
                                    html.Span("3. Stop Test: ", style={"color": ORANGE, "font-weight": "bold"}),
                                    "Stops the currently running test or constant load. The button color changes based on whether it can be pressed."
                                ]),
                                html.P([
                                    html.Span("4. View Past Tests: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Opens a window to view and manage past tests. You can view, delete, and download data and graphs from previous tests."
                                ]),
                                html.P([
                                    html.Span("5. Ripple menu: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Opens a window displaying ripple test screen, where you can run, view and download data from ran ripple test."
                                ]),
                                html.P([
                                    html.Span("6. Info: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Displays information about the UI. You just pressed this button!"
                                ]),
                                html.P([
                                    html.Span("7. Settings: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Opens settings allowing you to change some parameters of the app, as well as changing resolution modes"
                                ]),
                                html.P([
                                    html.Span("8. Adapter Selection (Dropdown): ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Select an adapter to use for running constant load (no. 9) or a test (2). Buttons won’t work without an adapter selected."
                                ]),
                                html.P([
                                    html.Span("9. Add New Adapter: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Opens a window to add a new adapter, which will be used for evaluation and testing."
                                ]),
                                html.P([
                                    html.Span("10. Delete Adapter: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Opens a window to delete an adapter. You can select the adapter to delete in the window."
                                ]),
                                html.P([
                                    html.Span("11. Enter Load (Input Field): ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Input field for current in amperes (A) to run with constant load. Execute it using Start Constant Load button (9)."
                                ]),
                                html.P([
                                    html.Span("12. Start Constant Load: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "After entering the desired current (0 - 3.2A) in the input field (10), this button starts the constant load. Stop it using the Stop button (4)."
                                ]),
                                html.P([
                                    html.Span("13. Live data: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Displays live data readout, these are also shown on the graph. Yellow: Voltage in Volts (V); Blue: Current in amperes (A); Green: Load in %, where 100% is equal to max current of selected adapter. The color window displays whether the adapter is connected, Green = Connected, Red = Disconnected"
                                ]),
                                html.P([
                                    html.Span("14. Pause Updates: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Pauses updates to the graph below, allowing you to interact with it. Without pausing, the graph refreshes every second and resets interactions. After unpausing, the graph reloads the latest data."
                                ]),
                            ], className="descriptions-container")]),

                        dcc.Tab(label="Tests Page", children=[
                            html.H3("Tests Page Features"),
                            html.Img(src="/assets/tests_screenshot.png", alt="Tests Page Screenshot", className="screenshot smaller-screenshot"),
                            html.Div([
                                html.P([
                                    html.Span("1. Overview Table: ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Displays the pass/fail status of each phase in the test."
                                ]),
                                html.P([
                                    html.Span("2. Select Test (Dropdown): ",style={"color": GRAY, "font-weight": "bold"}),
                                    "Allows you to select a test to display. After selection, the corresponding graph will load, enabling you to interact with it and download the graph and/or test data."
                                ]),
                                html.P([
                                    html.Span("3. Reload: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Refreshes the list of tests available in the dropdown (2)."
                                ]),
                                html.P([
                                    html.Span("4. Download Graph: ",style={"color": BLUE, "font-weight": "bold"}),
                                    "Exports the currently displayed graph as a PNG image."
                                ]),
                                html.P([
                                    html.Span("5. Download Data File: ",style={"color": BLUE, "font-weight": "bold"}),
                                    "Downloads the measured data of the selected test, including detailed test parameters, as an HDF5 file."
                                ]),
                                html.P([
                                    html.Span("6. Download Data and Graph: ",style={"color": BLUE, "font-weight": "bold"}),
                                    "Combines the graph (PNG) and the data file (HDF5) into a ZIP file for download."
                                ]),
                                html.P([
                                    html.Span("7. Delete Selected Test: ",style={"color": RED, "font-weight": "bold"}),
                                    "Permanently deletes the selected test. This action is IRREVERSIBLE."
                                ]),
                            ], className="descriptions-container")]),

                        dcc.Tab(label="Ripple Page", children=[
                            html.H3("Ripple Page Features"),
                            html.Img(src="/assets/ripple_screenshot.png", alt="Ripple Page Screenshot", className="screenshot smaller-screenshot"),
                            html.Div([
                                html.P([
                                    html.Span("1. Start: ", style={"color": GREEN, "font-weight": "bold"}),
                                    "Initiates the ripple test after the required values have been entered in the input fields (3)."
                                ]),
                                html.P([
                                    html.Span("2. Home: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Returns to the home page"
                                ]),
                                html.P([
                                    html.Span("3. Input Fields: ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Enter the required parameters for the ripple test, such as nominal voltage and tolerance. Once completed, use the Start button (1) to initiate the test."
                                ]),
                                html.P([
                                    html.Span("4. Progress bar: ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Shows the progress of the test, after the test is started"
                                ]),
                                html.P([
                                    html.Span("5. Download Graphs: ",style={"color": BLUE, "font-weight": "bold"}),
                                    "Exports the currently displayed graphs as a PNG image."
                                ]),
                                html.P([
                                    html.Span("6. Download Data File: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Downloads the measured data, as an HDF5 file."
                                ]),
                                html.P([
                                    html.Span("7. Download Data and Graph: ", style={"color": BLUE, "font-weight": "bold"}),
                                    "Combines the graph (PNG) and the data file (HDF5) into a ZIP file for download."
                                ]),
                                html.P([
                                    html.Span("8. Delete Selected Test: ", style={"color": RED, "font-weight": "bold"}),
                                    "Permanently deletes the test. This action is IRREVERSIBLE."
                                ]),
                                html.P([
                                    html.Span("9. Results Table: ", style={"color": GRAY, "font-weight": "bold"}),
                                    "Displays the results, once the tests is finished"
                                ]),
                                html.P([
                                    html.Span("10. Graphs (Line, Box): ",style={"color": GRAY, "font-weight": "bold"}),
                                    "Displays the results in a graph form, once the test is finished"
                                ]),
                                html.P([
                                    html.Span("11. Message box: ",style={"color": GRAY, "font-weight": "bold"}),
                                    "Displays messages from ripple tester, similar to the one on the home page"
                                ]),

                            ], className="descriptions-container")])
                    ])
                ], className="overlay-tabs-container")
            ], className="window element-description")
        ], id="description", className="overlay", style={"display": "none"}),

        # Settings sidebar
        html.Div([
            html.Div([
                html.H2("Settings"),
                html.Div([
                    # General settings
                    html.Label("Max Current Shutdown:"),
                    dcc.Input(id="max-current-input", className="in", type="number", value="3.2", step=0.01),
                    html.Br(),
                    html.Label("Max number of displayed messages:"),
                    dcc.Input(id="max-message-num", className="in", type="number", value="250", step=1, min=100, max=5000),
                    html.Br(),html.Br(),

                    html.Div([
                        html.Span("Continue test", className="toggle-label-left", title="Test ends the phase and continues normally"),
                        daq.ToggleSwitch(id='safety-toggle', value=app.tester.settings.exit_at_safety, label='Exit mode', labelPosition='top'),
                        html.Span("Stop test", className="toggle-label-right", title="Test ends with an error message"),
                    ], className="toggle-wrapper"), html.Br(),

                    html.Div([
                        html.Span("Low resolution", className="toggle-label-left", title="9BIT measurements, max 10x a second"),
                        daq.ToggleSwitch(id='resolution-toggle', value=app.tester.settings.high_res, label='Resolution Mode', labelPosition='top'),
                        html.Span("High resolution", className="toggle-label-right", title="12BIT measurements, only 2x a second"),
                    ], className="toggle-wrapper"),html.Br(),

                    html.Div([
                        html.Div([
                            html.Span("10x per second", className="toggle-label-left", title="Data is measured 10x a second, fastest setting"),
                            daq.ToggleSwitch(id="seconds-toggle", value=app.tester.settings.per_sec, label="Graph Data Mode", labelPosition="top"),
                            html.Span("1x per second", className="toggle-label-right", title="Data is measured 1x a second, slowest setting"),
                        ], className="toggle-wrapper"),
                        html.Div(className="freq-disabled" if app.tester.settings.high_res else "freq-enabled", id="overlay-seconds-toggle"), html.Br(),
                    ], className="freq-wrapper"),

                ], className="general-settings"),html.Br(),
                html.Div([
                    html.H3("Phases"),
                    html.Div([
                        html.H4("Phase 1"),
                        dcc.Checklist(options=[{"label": "Include", "value": "include"}], value=["include"] if app.tester.settings.phase1[0] else [], id="phase-1-include"),
                        html.Label("Repeat x times:"),
                        dcc.Input(id="phase-1-repeat", className="in", type="number", value=app.tester.settings.phase1[1], step=1, min=1, max=5),
                        html.Br()
                    ], className="phase"),html.Br(),
                    html.Div([
                        html.H4("Phase 2"),
                        dcc.Checklist(options=[{"label": "Include", "value": "include"}], value=["include"] if app.tester.settings.phase2[0] else [], id="phase-2-include"),
                        html.Label("Repeat x times:"),
                        dcc.Input(id="phase-2-repeat", className="in", type="number", value=app.tester.settings.phase2[1], step=1, min=1, max=5),
                        html.Br()
                    ], className="phase"),html.Br(),
                    html.Div([
                        html.H4("Phase 3"),
                        dcc.Checklist(options=[{"label": "Include", "value": "include"}], value=["include"] if app.tester.settings.phase3[0] else [], id="phase-3-include"),
                        html.Label("Repeat x times:"),
                        dcc.Input(id="phase-3-repeat", className="in", type="number", value=app.tester.settings.phase3[1], step=1, min=1, max=5),
                        html.Label("Look for OPP trip point x times:"),
                        dcc.Input(id="phase-3-opp", className="in", type="number", value=app.tester.settings.phase3[2], step=1, min=1, max=10),
                        html.Br()
                    ], className="phase"),
                ], className="phases-settings"),
                html.Br(),html.Br(),html.Br(),
                html.Button([html.I(className="fa fa-floppy-disk")], id="settings-conf-btn", className="settings-conf-btn", title="Save settings"),
            ], className="settings-content")
        ], id="sidebar", className="sidebar"),

        # Delete confirmation overlays
        app.del_confirm("in-adapter-delete"),
        app.del_confirm("in-tests"),

        ])
)