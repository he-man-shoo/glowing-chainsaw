import dash
from dash.dependencies import Input, Output, State
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from flask import send_file
import dash_auth
from flask import Flask
from dash.exceptions import PreventUpdate
from reportlab.graphics.shapes import *
from PIL import Image


from sizing_calculations import calculation
from tech_proposal import create_tech_proposal
from cost_memo import create_cost_memo
from general_arrangement import create_GA
from sld import create_SLD
from boundaries_table import df_tool_assump, table_format


dash.register_page(__name__, name = "Home", path='/', order=1)

input_label_style = {'font-size': '0.95em', 'font-weight': 'bolder'}

button_style = {'width':'200px','border-radius': '4px', 'font-size': '1.25rem', 'border': '1px solid navy','background-color': 'dodgerblue', 'color': 'white'}

logo = Image.open("Prevalon Logo.jpg")

# Define the layout of the website
layout = dbc.Container([
    
    dbc.Row([
        dbc.Col(html.H2("Indicative Sizing Tool", 
                        className='text-center text-primary-emphasis'),
                        xs=12, sm=12, md=12, lg=10, xl=10)
    ], justify='around', align='center'),
    
    html.Br(),

    dbc.Row([
        dbc.Col([
                html.P("Project Location", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_projloct', value="Lake Mary", className='form-control form-control-sm'),

                html.P("Number of Cycles per Year", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id='ddn_cyc', options=[{'label':x, 'value':x}
                                                         for x in [180, 365, 548, 730]], value = 365, style={'fontSize':'14px'}),

                html.P("Max Site Temperature (deg C)", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_temp', type='number', value=40, max=50, className='form-control form-control-sm'),


        ], xs=12, sm=12, md=12, lg=3, xl=3),
        dbc.Col([
                html.P("Project Name", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_projnm', value="Pilot Project", className='form-control form-control-sm'),

                html.P("Point of Measurement", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id='ddn_pom', value = 'High Side of HV Transformer', 
                             options=[{'label':x, 'value':x}
                                                         for x in ['AC Terminals of Inverter', \
                                                                   'High Side of Medium Voltage Transformer', \
                                                                    'Medium Voltage POM', \
                                                                        'High Side of HV Transformer',\
                                                                            'High Voltage POM']], style={'fontSize':'14px'}),


                html.P("Project Life (Years)", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_projlife', type='number', value=20, min=3, max=20, className='form-control form-control-sm'),


        ], xs=12, sm=12, md=12, lg=3, xl=3),
    dbc.Col([

                html.P("Project Size (MW)", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_projsize', type='number', value=100, min=5, className='form-control form-control-sm'),

                html.P("Power Factor", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id = 'ddn_pf', options=[{'label':x, 'value':x}
                                                         for x in [0.90, 0.95]], value = 0.95, style={'fontSize':'14px'}),
                
                html.P("BOL Oversize (until End of Year)", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_overize', type='number', value=3, min=0, className='form-control form-control-sm'),
 

        ], xs=12, sm=12, md=12, lg=3, xl=3),

    dbc.Col([
                html.P("Project Duration (hrs)", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id='ddn_duration', options=[{'label':x, 'value':x}
                                                         for x in [2, 3, 4, 5, 6, 8]], value = 4, style={'fontSize':'14px'}),

                html.P("Compliance Code", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id = 'ddn_rmu', options=[{'label':x, 'value':x}
                                                         for x in ["UL", "IEC"]], value = "UL", style={'fontSize':'14px'}),

                html.P("Number of Augmentations", className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='inp_aug', type='number', value=4, min=0, className='form-control form-control-sm'),

        ], xs=12, sm=12, md=12, lg=3, xl=3),

    ], justify='around'),

    dbc.Row([
        dbc.Col([
                html.P("Technical Proposal to include Flat Energy Guarantees", className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(id = 'inp_flt_gua', options=[{'label':x, 'value':x}
                                                         for x in ["Yes", "No"]], value = "No", style={'fontSize':'14px'}),

        ], xs=12, sm=12, md=12, lg=4, xl=4)
    ], justify='center'),
    
    dbc.Row([
        dbc.Col(   
            html.Div(
                        [
                            html.P("Tool Boundaries", \
                                        id="open", n_clicks=0, className='btn btn-warning mt-4'),
                            dbc.Modal(
                                [
                                    dbc.ModalHeader(dbc.ModalTitle("Any requests outside these boundaries \
                                                                   should be directed to App Eng team")),
                                    dbc.ModalBody(table_format(df_tool_assump())),
                                    dbc.ModalFooter(
                                        dbc.Button(
                                            "Close", id="close", className="ms-auto", n_clicks=0
                                        )
                                    ),
                                ],
                                id="modal",
                                size="xl",
                                is_open=True,
                            ),
                        ]
                    ), xs=12, sm=12, md=12, lg=2, xl=2),

        dbc.Col([
            html.P('Run Sizing', id='generate_sizing', className="btn btn-primary mt-4")
        ], xs=12, sm=12, md=12, lg=2, xl=2)

    ], justify='center'),

    dbc.Row([
        dbc.Col([
            html.H4('Energy Plot', className = "mt-4"),
            dbc.Spinner(dcc.Graph(id = "plot", style = {"height":"80vh"}))
        ], xs=12, sm=12, md=12, lg=9, xl=9),

        dbc.Col([
            html.H4('Downloads Section:', className = "mt-4"),

            html.A([
                html.Button('Step 1 - Generate Technical Proposal',  id='generate_pdf', style={'width':'230px'},className="btn btn-primary mt-4"),
                dbc.Spinner(html.A('Step 2 - Download Technical Proposal', id='download_pdf', href='',  style={'width':'230px'}, className="btn bg-warning mt-4")),
                    ]),
            html.Br(),
            html.A([
                html.Button('Step 1 - Generate Cost Memo',  id='generate_cost_memo', style={'width':'230px'},className="btn btn-primary mt-4"),
                dbc.Spinner(html.A('Step 2 - Download Cost Memo', id='download_cost_memo', href='',  style={'width':'230px'}, className="btn bg-warning mt-4")),
                    ]),
            html.Br(),
            html.A([
                html.Button('Step 1 - Generate GA',  id='generate_GA', style={'width':'230px'},className="btn btn-primary mt-4"),
                dbc.Spinner(html.A('Step 2 - Download GA', id='download_GA', href='',  style={'width':'230px'}, className="btn bg-warning mt-4")),
                    ]),
            html.Br(),
            html.A([
                html.Button('Step 1 - Generate SLD',  id='generate_SLD', style={'width':'230px'},className="btn btn-primary mt-4"),
                dbc.Spinner(html.A('Step 2 - Download SLD', id='download_SLD', href='',  style={'width':'230px'}, className="btn bg-warning mt-4")),
                    ]),

        ], xs=12, sm=12, md=12, lg=3, xl=3),

    ], justify='around'),

html.Br(),
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
    dash.dcc.Store(id = "stored_PCS_AC_Voltage"),
    dash.dcc.Store(id = "stored_PCS_model"),


]),

], fluid=True)


# Define callback to update the output

@dash.callback(
    Output('plot', 'figure'),
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
    Output('stored_PCS_AC_Voltage', 'data'),
    Output('stored_PCS_model', 'data'),
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
                    cost_memo_table, PCS_kVA_string, BESS_Rating, PCS_AC_Voltage, PCS_model = calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations, flat_guarantee)
    
        
        bol_config = table_format(bol_config)


        fig_stored = fig

        bill_of_materials_stored = bill_of_materials.to_dict()

        design_summary_stored = design_summary.to_dict()

        losses_table_stored = losses_table.to_dict()

        bol_design_summary_stored = bol_design_summary.to_dict()

        aug_energy_table_stored = aug_energy_table.to_dict()

        power_energy_rte_table_stored = power_energy_rte_table.to_dict()

        cost_memo_table_stored = cost_memo_table.to_dict()

        n_clicks = 0

        return fig, fig_stored, bill_of_materials_stored, design_summary_stored, \
    losses_table_stored, bol_design_summary_stored, aug_energy_table_stored, power_energy_rte_table_stored, plot_title, y_axis_range, \
        months_to_COD, block_type, cost_memo_table_stored, PCS_kVA_string, BESS_Rating, PCS_AC_Voltage, PCS_model, n_clicks

    else:
        raise PreventUpdate


@dash.callback(
Output('download_pdf', 'href'),
Output('generate_pdf', 'n_clicks'),
 [Input('generate_pdf', 'n_clicks'),
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

def update_pdf(n_clicks, proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
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


@dash.callback(
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

    if n_clicks:        # Generate PDF
        cost_memo_pdf = '/download/{}'.format(create_cost_memo(cost_memo_table, proj_location, proj_name, power_req, \
                                                               duration, aug_energy_table))
        n_clicks = 0
    else:
        # If button is not clicked, do nothing
        cost_memo_pdf = ''
    return cost_memo_pdf, n_clicks

@dash.callback(
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

@dash.callback(
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
  Input('stored_PCS_AC_Voltage', 'data'),
  Input('stored_PCS_model', 'data'),
 ]
)

def update_SLD(n_clicks, proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String, PCS_AC_Voltage, PCS_model):
    
    if n_clicks:
        # Generate PDF
        SLD_PDF = '/download/{}'.format(create_SLD(proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String, PCS_AC_Voltage, PCS_model))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        SLD_PDF = ''

    return SLD_PDF, n_clicks

@dash.callback(
    Output("modal", "is_open"),
    [Input("open", "n_clicks"), Input("close", "n_clicks")],
    [State("modal", "is_open")],
)
def toggle_modal(n1, n2, is_open):
    if n1 or n2:
        return not is_open
    return is_open