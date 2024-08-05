import dash
from dash.dependencies import Input, Output
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from flask import send_file
import dash_auth
from flask import Flask
from dash.exceptions import PreventUpdate
from reportlab.graphics.shapes import *

from sizing_calculations import calculation
from tech_proposal import create_tech_proposal
from cost_memo import create_cost_memo
from general_arrangement import create_GA
from sld import create_SLD


server = Flask(__name__)


# Keep this out of source code repository - save in a file or a database
VALID_USERNAME_PASSWORD_PAIRS = {
    'greek': 'spartans',
    'irish':'whiskey',
    'rocky':'mountains',
    'dim':'sum',
    'pav':'bhaji',
}


# Initialize the Dash app
app = dash.Dash(server=server, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

input_label_style = {'font-size': '0.95em', 'font-weight': 'bolder'}

button_style = {'border-radius': '4px', 'font-size': '1.25rem', 'border': '1px solid navy','background-color': 'dodgerblue', 'color': 'white'}

# Define the layout of the website
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
                  dcc.Input(id='inp_projsize', type='number', value=100, min=5),
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
                                {'label': '0.90', 'value': 0.90},
                                {'label': '0.95', 'value': 0.95}
                                ], value= 0.95),]
                ,style = {"textAlign":"center"}, className='two columns'),


        html.Div([html.H5('Max Site Temperature (deg C)', style = input_label_style),
                dcc.Input(id='inp_temp', type='number', value=40, max=50),
                ], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5('BOL Oversize (until End of Year)', style = input_label_style),
                dcc.Input(id='inp_overize', type='number', value=3, min=0),], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5("Project Life (years)", style = input_label_style),
                  dcc.Input(id='inp_projlife', type='number', value=20, min=3, max=20),
                  ], style = {"textAlign":"center"},className='two columns'),

        html.Div([html.H5("Number of Augmentations", style = input_label_style),
                  dcc.Input(id='inp_aug', type='number', value=4, min=0),]
                 ,style = {"textAlign":"center"} ,className='two columns'),


    ], className='row'),

    html.Br(),

    html.Div([html.H5("")], className='three columns'),

            html.Div([html.H5("Technical Proposal to include Flat Energy Guarantees", style = input_label_style),
                  dcc.RadioItems(id='inp_flt_gua', options = ['Yes', 'No'], value = 'No', inline=True)]
                 ,style = {"textAlign":"center"} ,className='five columns'),

    
    html.Br(),

    html.Br(),

    html.Br(),

    html.Div([
        
        html.Div([html.H5("")], className='five columns'),
        
        html.Button('Run Sizing', id='generate_sizing', className='two columns', style = button_style), 

    ]),
    
    

    html.Br(),

    html.Br(),


    html.Div([
        html.Div([html.H5("")], className='one columns'),
        html.H2(children='Energy Plot', className='ten columns'),

    ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        dcc.Loading(dcc.Graph(id = "plot", style = {"height":"80vh"},  className='ten columns')),

    ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        html.H2(children='BOL Configuration Table', className='four columns'),
        html.H2(children='Augmentation Table', className='four columns'),       
                ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        dbc.Container([html.P(id = "bol_config"), 
                    ], className='three columns'),
        html.Div([html.H5("")], className='one columns'),        
        dbc.Container([html.P(id = "aug_energy_table"),
                    ], className='three columns'),
                ], className='row'),


html.Br(),

html.Div([
        html.Div([html.H5("")], className='three columns'),
        html.H2(children='Power Energy and RTE Table', className='four columns'),     
], className='row'), 

html.Div([
        html.Div([html.H5("")], className='three columns'),
        dbc.Container([html.P(id = "power_energy_rte_table"), 
                        ], className='five columns'),
            
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
    dash.dcc.Store(id = "stored_months_to_COD"),
    dash.dcc.Store(id = "stored_block_type"),
    dash.dcc.Store(id = "stored_cost_memo_table"),
    dash.dcc.Store(id = "stored_PCS_kVA_string"),
    dash.dcc.Store(id = "stored_BESS_Rating"),
]),

html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate Technical Proposal', id='generate-pdf-button', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download Technical Proposal', id='download-pdf', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate Cost Memo', id='generate_cost_memo', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download Cost Memo', id='download_cost_memo', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate GA', id='generate_GA', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download GA', id='download_GA', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate SLD', id='generate_SLD', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download SLD', id='download_SLD', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

])



# Define callback to update the output

@app.callback(
    Output('plot', 'figure'),
    Output('bol_config', 'children'),
    Output('aug_energy_table', 'children'),
    Output('power_energy_rte_table', 'children'),
    Output('stored_energy_plot', 'data'),
    Output('stored_bill_of_materials', 'data'),
    Output('stored_design_summary', 'data'),
    Output('stored_losses_table', 'data'),
    Output('stored_bol_design_summary', 'data'),
    Output('stored_aug_energy_table', 'data'),
    Output('stored_power_energy_rte_table', 'data'),
    Output('stored_plot_title', 'data'),
    Output('stored_y_axis_range', 'data'),
    Output('stored_months_to_COD', 'data'),
    Output('stored_block_type', 'data'),
    Output('stored_cost_memo_table', 'data'),
    Output('stored_PCS_kVA_string', 'data'),
    Output('stored_BESS_Rating', 'data'),
    Output('generate_sizing', 'n_clicks'),
    [Input('inp_projloct', 'value'),
     Input('inp_projnm', 'value'),
     Input('inp_projsize', 'value'),
     Input('ddn_duration', 'value'),
     Input('ddn_cyc', 'value'),
     Input('ddn_pom', 'value'),
     Input('ddn_rmu', 'value'),
     Input('ddn_pf', 'value'),
     Input('inp_temp', 'value'),
     Input('inp_overize', 'value'),
     Input('inp_projlife', 'value'),
     Input('inp_aug', 'value'),
     Input('inp_flt_gua', 'value'),
     Input('generate_sizing', 'n_clicks'),]
)
def update_output(proj_location, proj_name, power_req, duration, number_cycles,\
                   point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, \
                    oversize_required, project_life, number_of_augmentations, flat_guarantee, \
                        n_clicks):
    
    if n_clicks:
    
        fig, bol_config, aug_energy_table, power_energy_rte_table, \
            bill_of_materials, design_summary, losses_table, bol_design_summary, \
                plot_title, y_axis_range, months_to_COD, block_type, \
                    cost_memo_table, PCS_kVA_string, BESS_Rating = calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations, flat_guarantee)
    
        def table_format(table):
            return dash.dash_table.DataTable(table.to_dict('records', index=True), 
                                                style_data={
                                                            'color': 'black',
                                                            'backgroundColor': 'white', 
                                                            'font-family':'arial',
                                                            'font-size': '11px',
                                                            'border': '1px solid black',
                                                            'textAlign': 'center',
                                                            },
                                                style_data_conditional=[
                                                                        {
                                                                        'if': {'row_index': 'odd'},
                                                                        'backgroundColor': 'rgb(220, 207, 235)',
                                                                        }, 

                                                                        {
                                                                        'if': {'column_id': 'Total Cost per component ($)', 'row_index': 3},
                                                                        'fontWeight': 'bold',
                                                                        },

                                                                        {
                                                                        'if': {'column_id': 'Component', 'row_index': 3},
                                                                        'fontWeight': 'bold',
                                                                        },

                                                                    ],

                                                style_header={
                                                                'backgroundColor': 'rgb(127, 81, 185)',
                                                                'color': 'white',
                                                                'fontWeight': 'bold',
                                                                'font-family':'Helvetica',
                                                                'font-size': '12px',
                                                                'border': '1px solid black',
                                                                'textAlign': 'center',
                                                            })
            

        bol_config = table_format(bol_config)


        aug_energy_dict = table_format(aug_energy_table)
        
        power_energy_rte_dict = table_format(power_energy_rte_table)

        fig_stored = fig

        bill_of_materials_stored = bill_of_materials.to_dict()

        design_summary_stored = design_summary.to_dict()

        losses_table_stored = losses_table.to_dict()

        bol_design_summary_stored = bol_design_summary.to_dict()

        aug_energy_table_stored = aug_energy_table.to_dict()

        power_energy_rte_table_stored = power_energy_rte_table.to_dict()

        cost_memo_table_stored = cost_memo_table.to_dict()

        n_clicks = 0
        return fig, bol_config, aug_energy_dict, power_energy_rte_dict, fig_stored, bill_of_materials_stored, design_summary_stored, \
    losses_table_stored, bol_design_summary_stored, aug_energy_table_stored, power_energy_rte_table_stored, plot_title, y_axis_range, months_to_COD, block_type, cost_memo_table_stored, PCS_kVA_string, BESS_Rating, n_clicks

    else:
        raise PreventUpdate


@app.callback(
Output('download-pdf', 'href'),
Output('generate-pdf-button', 'n_clicks'),
 [Input('generate-pdf-button', 'n_clicks'),
  Input('inp_projloct', 'value'),
  Input('inp_projnm', 'value'),
  Input('inp_projsize', 'value'),
  Input('ddn_duration', 'value'),
  Input('inp_projlife', 'value'),
  Input('stored_energy_plot', 'data'),
  Input('stored_bill_of_materials', 'data'),
  Input('stored_design_summary', 'data'),
  Input('stored_losses_table', 'data'),
  Input('stored_bol_design_summary', 'data'),
  Input('stored_aug_energy_table', 'data'),
  Input('stored_power_energy_rte_table', 'data'),
  Input('stored_plot_title', 'data'),
  Input('stored_y_axis_range', 'data'),
  Input('stored_months_to_COD', 'data'),
  Input('stored_block_type', 'data'),
 ]
)

def update_pdf(n_clicks ,proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
                                    bol_design_summary, aug_energy_table, power_energy_rte_table, plot_title, y_axis_range, months_to_COD, block_type):
    
    if n_clicks:
        # Generate PDF
        pdf_file = '/download/{}'.format(create_tech_proposal(proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
                                  bol_design_summary, aug_energy_table, power_energy_rte_table, plot_title, y_axis_range, months_to_COD, block_type))
        n_clicks = 0
    else:
        # If button is not clicked, do nothing
        pdf_file = ''
    return pdf_file, n_clicks


@app.callback(
Output('download_cost_memo', 'href'),
Output('generate_cost_memo', 'n_clicks'),
 [Input('generate_cost_memo', 'n_clicks'),
  Input('stored_cost_memo_table', 'data'),
  Input('inp_projloct', 'value'),
  Input('inp_projnm', 'value'),
  Input('inp_projsize', 'value'),
  Input('ddn_duration', 'value'),
  Input('stored_aug_energy_table', 'data'),
 ]
)

def update_cost_memo(n_clicks, cost_memo_table, proj_location, proj_name, power_req, duration, aug_energy_table):
    
    if n_clicks:
        # Generate PDF
        cost_memo_pdf = '/download/{}'.format(create_cost_memo(cost_memo_table, proj_location, proj_name, power_req, \
                                                               duration, aug_energy_table))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        cost_memo_pdf = ''
    return cost_memo_pdf, n_clicks

@app.callback(
Output('download_GA', 'href'),
Output('generate_GA', 'n_clicks'),
 [Input('generate_GA', 'n_clicks'),
  Input('inp_projloct', 'value'),
  Input('inp_projnm', 'value'),
  Input('inp_projsize', 'value'),
  Input('ddn_duration', 'value'),
  Input('stored_bol_design_summary', 'data'),
  Input('stored_PCS_kVA_string', 'data'),
  Input('stored_BESS_Rating', 'data'),
  Input('stored_aug_energy_table', 'data'), 
 ]
)

def update_GA(n_clicks, proj_location, proj_name, power_req, duration, bol, PCS_kVA_string, BESS_Rating, aug):

    if n_clicks:
        # Generate PDF
        GA_PDF = '/download/{}'.format(create_GA(proj_location, proj_name, power_req, duration, bol, PCS_kVA_string, BESS_Rating, aug))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        GA_PDF = ''
    return GA_PDF, n_clicks

@app.callback(
Output('download_SLD', 'href'),
Output('generate_SLD', 'n_clicks'),
 [Input('generate_SLD', 'n_clicks'),
  Input('inp_projloct', 'value'),
  Input('inp_projnm', 'value'),
  Input('inp_projsize', 'value'),
  Input('ddn_duration', 'value'),
  Input('ddn_rmu', 'value'),
  Input('stored_bol_design_summary', 'data'),
  Input('stored_PCS_kVA_string', 'data'),

 ]
)

def update_SLD(n_clicks, proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String):
    
    if n_clicks:
        # Generate PDF
        SLD_PDF = '/download/{}'.format(create_SLD(proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        SLD_PDF = ''

    return SLD_PDF, n_clicks


@app.server.route('/download/<path:path>')
def serve_static(path):
    return send_file(path, as_attachment=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port = 2400)