import dash
import pandas as pd
from dash import Dash, dash_table, dcc, html, Input, Output, State
import plotly.express as px
import dash_bootstrap_components as dbc

app = Dash(__name__)
server = app.server



app = dash.Dash(external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
server = app.server

# auth = dash_auth.BasicAuth(
#     app,
#     VALID_USERNAME_PASSWORD_PAIRS
# )


# Define the layout of the website

input_label_style = {'font-size': '0.95em', 'font-weight': 'bolder'}

button_style = {'border-radius': '4px', 'font-size': '1.25rem', 'border': '1px solid navy','background-color': 'dodgerblue', 'color': 'white'}


app.layout = html.Div([

    html.H1(children='Level 1 Sizing Tool', style={'textAlign': 'center', 'font-family':'Helvetica', 'font-size': '3.5em'}),
                html.Br(),
    
    
    html.Div([
        
        html.Div([html.H5("Project Location", style = input_label_style),
                  dcc.Input(id='inp_projloct', type='text', value="Lake Mary"),
                  ], style = {"textAlign":"center", 'font-size': '1em'}, className='two columns'),
        
        html.Div([html.H5("Project Name", style = input_label_style),
                  dcc.Input(id='inp_projnm', type='text', value="Pilot Project"),
                  ],style = {"textAlign":"center"} ,className='two columns'),
        
        html.Div([html.H5('Project Size (MW)', style = input_label_style),
                  dcc.Input(id='inp_projsize', type='number', value=100),
                  ], style = {"textAlign":"center"}, className='two columns'),
        
        html.Div([html.H5(children = 'Duration (hrs):', style = input_label_style),
            dcc.Dropdown(id='ddn_duration', options=[
                {'label': '2', 'value': 2},
                {'label': '3', 'value': 3},
                {'label': '4', 'value': 4},
                {'label': '5', 'value': 5},
                {'label': '6', 'value': 6},
                {'label': '8', 'value': 8},
                ], value= 4),
        ], style = {"textAlign":"center"}, className='two columns'),

        html.Div([
            html.H5(children = 'Number of Cycles per Year', style = input_label_style),
            dcc.Dropdown(id='ddn_cyc', options=[
                        {'label': '180', 'value': 180},
                        {'label': '365', 'value': 365},
                        {'label': '548', 'value': 548},
                        {'label': '730', 'value': 730},
                        ], value= 365),
        ], style = {"textAlign":"center", 'font-size': '1em'}, className='two columns'),

        html.Div([
            html.H5('Point of Measurement', style = input_label_style),
            dcc.Dropdown(id='ddn_pom', options=[
                {'label': 'AC Terminals of Inverter', 'value': 'AC Terminals of Inverter'},
                {'label': 'High Side of Medium Voltage Transformer', 'value': 'High Side of Medium Voltage Transformer'},
                {'label': 'Medium Voltage POM', 'value': 'Medium Voltage POM'},
                {'label': 'High Side of HV Transformer', 'value': 'High Side of HV Transformer'},
                {'label': 'High Voltage POM', 'value': 'High Voltage POM'},
                ], value= 'High Side of HV Transformer', style = {'font-size': '0.94em'}),
        ], style = {"textAlign":"center"}, className='two columns'),

    ], className='row'),

html.Br(),


    html.Div([
          
        html.Div([html.H5('Compliance Code', style = input_label_style),
            dcc.Dropdown(id='ddn_rmu', options=[
                        {'label': 'UL', 'value': 'UL'},
                        {'label': 'IEC', 'value': 'IEC'}
                        ], value= 'UL'),
                        ],style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5('Power Factor', style = input_label_style),
                    dcc.Dropdown(id='ddn_pf', options=[
                                {'label': '0.9', 'value': 0.90},
                                {'label': '0.95', 'value': 0.95}
                                ], value= 0.95),]
                ,style = {"textAlign":"center"}, className='two columns'),


        html.Div([html.H5('Max Site Temperature (deg C)', style = input_label_style),
                dcc.Input(id='inp_temp', type='number', value=40, max=50),
                ], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5('BOL Oversize (until End of Year)', style = input_label_style),
                dcc.Input(id='inp_overize', type='number', value=3),], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5("Project Life (years)", style = input_label_style),
                  dcc.Input(id='inp_projlife', type='number', value=20),
                  ], style = {"textAlign":"center"},className='two columns'),

        html.Div([html.H5("Number of Augmentations", style = input_label_style),
                  dcc.Input(id='inp_aug', type='number', value=4),]
                 ,style = {"textAlign":"center"} ,className='two columns'),


    ], className='row'),

    html.Br(),

    html.Br(),

    html.Div([
        
        html.Div([html.H5("")], className='five columns'),
        
        html.Button('Run Sizing', id='generate_sizing', className='two columns', style = button_style), 



    ]),
    
    

    html.Br(),

    html.Br(),


    html.Div([
        
        html.H2(children='Energy Plot'),
             dcc.Graph(id = "plot", className='six columns'),
                
        html.H2(children='BOL Configuration Table'),
        dbc.Container([html.P(id = "bol_config"), 
                    ], className='six columns')        
                
                ], className='row'),

html.Br(),

    html.Div([
        html.H2(children='Augmentation Table'),
        dbc.Container([html.P(id = "aug_energy_table"),
                    ], className='six columns'),

        html.H2(children='Power Energy and RTE Table'),
        dbc.Container([html.P(id = "power_energy_rte_table"), 
                        ], className='six columns'),
            
                ],  className='row'),

html.Br(),

html.Div([
    dash.dcc.Store(id = "stored_energy_plot"),
    dash.dcc.Store(id = "stored_bill_of_materials"),
    dash.dcc.Store(id = "stored_design_summary"),
    dash.dcc.Store(id = "stored_losses_table"),
    dash.dcc.Store(id = "stored_bol_design_summary"),
    dash.dcc.Store(id = "stored_aug_energy_table"),
    dash.dcc.Store(id = "stored_power_energy_rte_table"),
    dash.dcc.Store(id = "stored_plot_title"),
    dash.dcc.Store(id = "stored_y_axis_range"),
]),

html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Generate Technical Proposal', id='generate-pdf-button', style=button_style, className='three columns'),
    html.A('Download Technical Proposal', id='download-pdf', href='', className='three columns', style= {"textAlign":"center", 'border-radius': '4px', 'border': '1px solid navy','background-color': 'rgb(127, 81, 185)', 'color': 'white', 'height': '38px', 'padding': '8px'})
        ]),

html.Br(),

])

if __name__ == "__main__":
    app.run_server(debug=True)