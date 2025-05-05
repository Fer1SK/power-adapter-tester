import os

import colorama
from dash import Dash, html, dcc, Input, Output, State, callback_context, no_update, exceptions, register_page, get_app
from colors import BLACK, WHITE, GRAY, RED, GREEN, ORANGE, BLUE, LIGHT_BLUE, YELLOW
from ripple_tester import RippleTester
from subclasses import empty_fig
from pathlib import Path


def return_ripple_tests():
    directory = Path("ripple_tests/")
    # Get all .h5 files and sort by modification time (newest first)
    h5_files = sorted(
        [f for f in directory.iterdir() if f.suffix == '.h5'],
        key=lambda f: f.stat().st_mtime,
        reverse=True
    )
    # Generate options for the dropdown
    options = []
    for i, f in enumerate(h5_files):
        extracted_id = f.stem
        options.append({"label": html.Span(extracted_id), "value": i})

    return options

app = get_app()
register_page(
    name="Ripple Tester",
    module=__name__,
    path="/ripple",
    layout=html.Div([
        html.Header([html.Link(href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.7.1/css/all.min.css", rel="stylesheet")]),
        html.Div([
            dcc.Interval(id="ripple-interval", interval=1000),
            html.Div([
                html.Div("Ripple Tester", className="ripple-title"),
                html.Div([
                    html.Div([
                        dcc.Input(id="ripple-expected-voltage", type="number", placeholder="Expected Voltage (V)", className="in ripple-input", min=0, max=15),
                        dcc.Input(id="ripple-tolerance", type="number", placeholder="Tolerance (%)", className="in ripple-input", min=0, max=100),
                        dcc.Input(id="ripple-duration", type="number", placeholder="Duration (Sec)", className="in ripple-input", min=10, max=120),
                    ], className="ripple-controls-col inputs"),
                    html.Div([
                        html.Button([html.I(className="fa fa-house")], id="in-ripple-home-btn", className="s-btn-in-ripple", title="Back to home page"),
                        html.Button([html.I(className="fa fa-play")], id="start-ripple-test-btn", className="start-btn s-btn-in-ripple", title="Start a new test"),
                    ], className="ripple-controls-col buttons"),
                ], className="ripple-controls"),
                html.Div([html.Div(id="ripple-progress-fill", className="ripple-progress-fill")],id="ripple-progress-bar", className="ripple-progress-bar", title="Progress bar"),
                html.Div(className="ripple-spacer"),
                dcc.Dropdown(id="ripple-test-dropdown", options=return_ripple_tests(), placeholder="Select ripple test", className="dropdown ripple-test-dropdown"),
                html.Div([
                    html.Div([
                        html.Button([html.I(className="fa fa-chart-line"), html.I(className="fa fa-download")], id="download-ripple-graphs-btn", className="download-btn", title="Download images of the currently displayed graphs"),
                        html.Button([html.I(className="fa fa-file-lines"), html.I(className="fa fa-download")], id="download-ripple-data-btn", className="download-btn", title="Download .h5 file including data"),
                        html.Button([html.I(className="fa fa-file-zipper"), html.I(className="fa fa-download")], id="download-ripple-zip-btn", className="download-btn", title="Download a zip folder containing graph images and .h5 file"),
                        html.Button([html.I(className="fa fa-trash-can")], id="ripple-delete-btn", className="download-btn delete", title="Delete the current test"),
                        dcc.Download(id="ripple-png-download-line"),
                        dcc.Download(id="ripple-png-download-box"),
                        dcc.Download(id="ripple-h5-download"),
                        dcc.Download(id="ripple-zip-download"),
                    ], className="ripple-buttons"),
                    # Results Table
                    html.Table([
                            html.Th("Metric", className="table-header"),
                            html.Th("Value", className="table-header"),
                            html.Tr([html.Td("Min Voltage:"), html.Td(id="ripple-min-voltage", className="table-add-left-border")]),
                            html.Tr([html.Td("Max Voltage:"), html.Td(id="ripple-max-voltage", className="table-add-left-border")]),
                            html.Tr([html.Td("Top Quartile:"), html.Td(id="ripple-top-quartile", className="table-add-left-border")]),
                            html.Tr([html.Td("Bottom Quartile:"), html.Td(id="ripple-bottom-quartile", className="table-add-left-border")]),
                            html.Tr([html.Td("Pass / Fail:"), html.Td(id="ripple-pass-fail", className="table-add-left-border")]),
                    ], className="ripple-results-table table"),
                ], className="ripple-results"),
            ], className="ripple-controls-wrapper"),

            html.Div([
                dcc.Graph(id="ripple-line-graph", className="graph ripple-graph", figure=empty_fig),
                dcc.Graph(id="ripple-box-graph", className="graph ripple-graph", figure=empty_fig)
            ], className="ripple-graphs"),

            html.Div([], className="ripple-cmd", id="ripple-cmd"),
            app.del_confirm("in-ripple")
        ], className="ripple"),
    ])
)

# Returning home from ripple page
@app.callback(
    Input("in-ripple-home-btn", "n_clicks"),
    prevent_initial_call=True
)
def manage_ripple_window(n_clicks):
    if n_clicks:
        app.just_delete_ripple_tester()
        app.tester.data_storage.url = "/"

# Callback to handle everything related to ripple testing displaying and storing
@app.callback(
    Output("ripple-cmd", "children"),
    Output("ripple-line-graph", "figure"),
    Output("ripple-box-graph", "figure"),
    Output("ripple-min-voltage", "children"),
    Output("ripple-max-voltage", "children"),
    Output("ripple-top-quartile", "children"),
    Output("ripple-bottom-quartile", "children"),
    Output("ripple-pass-fail", "children"),
    Output("ripple-progress-fill", "style"),
    Output("del_conf-in-ripple", "style"),
    Output("ripple-test-dropdown", "options"),

    Input("start-ripple-test-btn", "n_clicks"),
    Input("ripple-interval", "n_intervals"),
    Input("ripple-delete-btn", "n_clicks"),
    Input("del_conf-in-ripple-exit-btn", "n_clicks"),
    Input("del_conf-in-ripple-delete-btn", "n_clicks"),

    State("ripple-cmd", "children"),
    State("ripple-expected-voltage", "value"),
    State("ripple-tolerance", "value"),
    State("ripple-duration", "value"),
    State("ripple-min-voltage", "children"),
    prevent_initial_call=True
)
def manage_ripple_tests(n_clicks, intervals, del_clicks, conf_exit, conf_del, current_children, expected_v, tol, dur, test):
    #          = [0        , 1        , 2        , 3        , 4        , 5        , 6        , 7        , 8        , 9        , 10       ]
    def_return = [no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update, no_update]
    reset_return = [no_update, empty_fig, empty_fig,      "",        "",        "",        "",   "", {"width": "0"}, no_update, return_ripple_tests()]
    ctx = callback_context
    if not ctx.triggered:
        return def_return

    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

    # Start ripple test button click
    if triggered_id == "start-ripple-test-btn":
        # Start button pressed
        if app.ripple_tester:
            if app.ripple_tester.is_running:
                # Test is runnning
                msg = "Test is running. PLEASE WAIT ...."
                app.ripple_tester.add_message(msg, RED)
                print(colorama.Fore.RED, msg, colorama.Fore.RESET)

            else:
                # Test is done starting new test
                app.delete_and_recreate_ripple_tester()
                app.ripple_start(expected_v, tol, dur)

        elif app.ripple_tester is None:
            # Its not defined either because it got deleted by user or because none has been started / selected yet
            app.delete_and_recreate_ripple_tester()
            app.ripple_start(expected_v, tol, dur)
        return def_return

    # Ripple interval
    elif triggered_id == "ripple-interval" and app.ripple_tester is not None:
        new_children = []
        # First update messages
        for msg in app.ripple_tester.messages:
            timestamp, message = msg["text"].split(";", 1)
            new_children.append(html.Div([
                html.Span(timestamp, style={"color": "#555", "fontWeight": "bold", "fontSize": "13px"}),
                html.Span(message, style={"color": msg["color"], "marginLeft": "5px", "fontSize": "13px"})
            ]))
        combined_children = (current_children or []) + new_children
        combined_children = combined_children[-125:]
        app.ripple_tester.messages.clear()
        def_return[0] = combined_children

        if app.ripple_tester.is_running:
            if app.ripple_tester.timer >= app.ripple_tester.timer_max:
                # The time has elapsed
                msg = "Data gathered, processing results please wait ..."
                app.ripple_tester.add_message(msg, GREEN)
                print(colorama.Fore.GREEN, msg, colorama.Fore.RESET)
                app.ripple_tester.stop(app.tester.data_storage.voltage[-100:])
                return def_return

            else:
                # Still gathering data
                app.ripple_tester.timer += 1
                def_return[8] = {"width": f"{(100 * app.ripple_tester.timer) / app.ripple_tester.timer_max}%"}
                msg = f"Time: {app.ripple_tester.timer}"
                print(colorama.Fore.LIGHTBLACK_EX, msg, colorama.Fore.RESET)
                app.ripple_tester.add_message(msg, GRAY)
                return def_return

        elif app.ripple_tester.is_waiting_to_display:
            # The test is done / is selected and the app is waiting to display new data
            app.ripple_tester.is_not_waiting_to_display()
            return [no_update, app.ripple_tester.line_graph, app.ripple_tester.box_graph, str(app.ripple_tester.min_voltage), str(app.ripple_tester.max_voltage), str(app.ripple_tester.top_quartile), str(app.ripple_tester.bottom_quartile), "PASS" if app.ripple_tester.passed else "FAIL", no_update, no_update, return_ripple_tests()]

    # Ripple interval but test has been unselected
    elif triggered_id == "ripple-interval" and app.ripple_tester is None and test != []:
        return reset_return

    # Delete button click
    elif triggered_id == "ripple-delete-btn" and app.ripple_tester is not None:
        # If test doesnt exists we have no way to delete things
        if not app.ripple_tester.is_running:
            # Not running can delete
            def_return[9] = {"display": "block"}
        else:
            # Is running cant delete
            msg = "Test is running. PLEASE WAIT ...."
            print(colorama.Fore.YELLOW, msg, colorama.Fore.RESET)
            app.ripple_tester.add_message(msg, ORANGE)
        return def_return

    # In delete confirmation window exit button pressed
    elif triggered_id == "del_conf-in-ripple-exit-btn":
        # Cancel button in delete
        def_return[9] = {"display": "none"}
        return def_return

    # In delete confirmation window delete button pressed
    elif triggered_id == "del_conf-in-ripple-delete-btn":
        # Confirmed deletion
        msg = "Ripple test successfully deleted"
        app.tester.data_storage.add_message(msg, RED)
        print(colorama.Fore.RED, msg, colorama.Fore.RESET)
        app.ripple_tester.delete()
        app.just_delete_ripple_tester()
        reset_return[9] = {"display": "none"}
        return reset_return

    return def_return

@app.callback(
    Input("ripple-test-dropdown", "value"),
    State("ripple-test-dropdown", "options"),
    prevent_initial_call=True
)
def handle_test_selection_via_dropdown(selected_value, options):
    # Test is selected in dropdown
    if selected_value is None:
        app.just_delete_ripple_tester()
        return

    # Find the corresponding label from the options
    selected_label = next(
        (option["label"]["props"]["children"] for option in options if option["value"] == selected_value), None
        # The filename is in a span so it needs to be extracted like this
    )
    app.delete_and_recreate_ripple_tester()
    app.ripple_tester.load_from_file(selected_label)
    msg = f"Selected test: {selected_label}"
    print(colorama.Fore.BLUE, msg, colorama.Style.RESET_ALL)
    app.ripple_tester.add_message(msg, BLUE)

# PNG - ripple
@app.callback(
    Output("ripple-png-download-line", "data"),
    Output("ripple-png-download-box", "data"),
    Input("download-ripple-graphs-btn", "n_clicks"),
    prevent_initial_call=True
)
def download_ripple_png(n_clicks):
    if n_clicks and app.ripple_tester is not None and not app.ripple_tester.is_running:
        png1, png2 = app.ripple_tester.download_png()
        png1_send = dcc.send_file(png1)
        png2_send = dcc.send_file(png2)
        os.remove(png1)
        os.remove(png2)
        return png1_send, png2_send
    return no_update, no_update

# H5 - ripple
@app.callback(
    Output("ripple-h5-download", "data"),
    Input("download-ripple-data-btn", "n_clicks"),
    prevent_initial_call=True
)
def download_ripple_hdf(n_clicks):
    if n_clicks and app.ripple_tester is not None and not app.ripple_tester.is_running:
        return dcc.send_file(app.ripple_tester.download_hdf())
    return no_update

# ZIP - ripple
@app.callback(
    Output("ripple-zip-download", "data"),
    Input("download-ripple-zip-btn", "n_clicks"),
    prevent_initial_call=True
)
def download_ripple_zip(n_clicks):
    if n_clicks and app.ripple_tester is not None and not app.ripple_tester.is_running:
        return app.ripple_tester.download_zip()
    return no_update