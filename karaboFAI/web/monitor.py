"""
Offline and online data analysis and visualization tool for azimuthal
integration of different data acquired with various detectors at
European XFEL.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import argparse

import dash
import dash_core_components as dcc
import dash_table as dt
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go

from ..config import config
from ..database import Metadata, MetaProxy, MonitorProxy
from ..database import Metadata as mt


class Color:
    BKG = '#3AAFA9'
    SHADE = '#2B7A78'
    TEXT = '#17252A'
    TITLE = '#DEF2F1'
    INFO = '#FEFFFF'
    GRAPH = '#FBEEC1'


# update intervals in second
FAST_UPDATE = 1.0
SLOW_UPDATE = 2.0

app = dash.Dash(__name__)
# We use the default CSS style here:
# https://codepen.io/chriddyp/pen/bWLwgP?editors=1100
# app.css.append_css({
#     "external_url": "https://codepen.io/chriddyp/pen/bWLwgP.css"
# })
app.css.config.serve_locally = True
app.scripts.config.serve_locally = True
app.config['suppress_callback_exceptions'] = True

meta_proxy = MetaProxy()
proxy = MonitorProxy()


def get_top_bar_cell(name, value):
    """Get cell for the top bar.

    :param str name: parameter name.
    :param str/int/float value: parameter value.
    """
    return html.Div(
        className="three-col",
        children=[
            html.P(className="p-top-bar", children=name),
            html.P(id=name, className="display-none", children=value),
            html.P(children=value),
        ],
    )


def get_top_bar():
    """Get Div for the top bar."""
    ret = proxy.get_last_tid()

    if not ret:
        # [] or None
        tid = '0' * 9
    else:
        _, tid = ret

    sess = meta_proxy.get_all(mt.SESSION)

    return [
        get_top_bar_cell("Detector", sess['detector']),
        get_top_bar_cell("Topic", sess['topic']),
        get_top_bar_cell("Train ID", tid),
    ]


def get_analysis_types():
    """Query and parse analysis types."""
    query = proxy.get_all_analysis()
    ret = []
    for k, v in query.items():
        if k != 'AnalysisType.UNDEFINED' and int(v) > 0:
            ret.append({'type': k.split(".")[-1], 'count': v})
    return ret


def get_processor_params(proc=None):
    """Query and parse processor metadata."""
    if proc is None:
        return []
    query = proxy.get_processor_params(proc)
    if query is None:
        return []
    return [{'param': k, 'value': v} for k, v in query.items()]


# define callback functions

@app.callback(output=Output('top_bar', 'children'),
              inputs=[Input('fast_interval1', 'n_intervals')])
def update_top_bar(n_intervals):
    return get_top_bar()


@app.callback(output=Output('analysis_type_table', 'data'),
              inputs=[Input('fast_interval2', 'n_intervals')])
def update_analysis_types(n_intervals):
    return get_analysis_types()


@app.callback(output=Output('processor_params_table', 'data'),
              inputs=[Input('fast_interval3', 'n_intervals')],
              state=[State('processor_dropdown', 'value')])
def update_processor_params(n_intervals, proc):
    return get_processor_params(proc)


@app.callback(output=Output('performance', 'figure'),
              inputs=[Input('slow_interval', 'n_intervals')])
def update_performance(n_intervals):
    ret = proxy.get_latest_tids()

    tids = []
    freqs = []
    prev_timestamp = None
    for timestamp, tid in ret:
        tids.append(tid)
        float_timestamp = float(timestamp)
        if not freqs:
            freqs.append(0)
        else:
            freqs.append(1. / (prev_timestamp - float_timestamp))

        prev_timestamp = float_timestamp

    traces = [go.Bar(x=tids, y=freqs,
                     marker=dict(color=Color.GRAPH))]
    figure = {
        'data': traces,
        'layout': {
            'xaxis': {
                'title': 'Train ID',
            },
            'yaxis': {
                'title': 'Processing rate (Hz)',
            },
            'font': {
                'family': 'Courier New, monospace',
                'size': 16,
                'color': Color.INFO,
            },
            'margin': {
                'l': 100, 'b': 50, 't': 50, 'r': 50,
            },
            'paper_bgcolor': Color.SHADE,
            'plot_bgcolor': Color.SHADE,
        }
    }

    return figure


# define content and layout of the web page
app.layout = html.Div(
    children=[
        dcc.Interval(
            id='fast_interval1', interval=FAST_UPDATE * 1000, n_intervals=0,
        ),
        dcc.Interval(
            id='fast_interval2', interval=FAST_UPDATE * 1000, n_intervals=0,
        ),
        dcc.Interval(
            id='fast_interval3', interval=FAST_UPDATE * 1000, n_intervals=0,
        ),
        dcc.Interval(
            id='slow_interval', interval=SLOW_UPDATE * 1000, n_intervals=0,
        ),
        html.Div([
            html.H4(
                className='header-title',
                children="karaboFAI status monitor",
            ),
        ]),
        html.Div(
            id="top_bar",
            className="div-top-bar",
            children=get_top_bar(),
        ),
        html.Div(
            children=[dcc.Graph(
                id='performance',
            )]
        ),
        html.Div(
            children=[
                html.Div(
                    id='processor_list',
                    className='display-inlineblock',
                    children=[
                        dcc.Dropdown(
                            id='processor_dropdown',
                            options=[
                                {'label': n.replace('_', ' '), 'value': n}
                                for n in Metadata.processors
                            ]
                        ),
                        dt.DataTable(
                            id='processor_params_table',
                            columns=[{'name': 'Parameter', 'id': 'param'},
                                     {'name': 'Value', 'id': 'value'}],
                            data=get_processor_params(),
                            style_header={
                                'color': Color.TEXT,
                            },
                            style_cell={
                                'backgroundColor': Color.BKG,
                                'color': Color.INFO,
                                'fontWeight': 'bold',
                                'fontSize': '18px',
                                'text-align': 'left',
                            },
                        ),
                    ],
                ),
                html.Div(
                    id='analysis_type',
                    className='display-inlineblock',
                    children=[
                        dt.DataTable(
                            id='analysis_type_table',
                            columns=[{'name': 'Analysis type', 'id': 'type'},
                                     {'name': 'Count', 'id': 'count'}],
                            data=get_analysis_types(),
                            style_header={
                                'color': Color.TEXT,
                            },
                            style_cell={
                                'backgroundColor': Color.BKG,
                                'color': Color.INFO,
                                'fontWeight': 'bold',
                                'fontSize': '18px',
                                'text-align': 'left',
                            },
                        ),
                    ]
                ),
            ]
        ),
    ]
)


def web_monitor():
    """Start a Flask server for the monitor.

    This function is for the command line tool: karaboFAI-monitor.
    """
    ap = argparse.ArgumentParser(prog="karaboFAI-monitor")
    ap.add_argument("port", help="TCP port to run server on")

    args = ap.parse_args()

    app.run_server(port=args.port)