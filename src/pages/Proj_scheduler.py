import dash
from dash import html
import dash_bootstrap_components as dbc
from reportlab.graphics.shapes import *
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
from dash import dcc
import pandas as pd
from datetime import date
import math

from gantt_chart_schedule import scheduler
from proj_schedule_pdf import create_proj_schedule_pdf
from schedule_excel import schedule_excel_op


dash.register_page(__name__, name = "Project Scheduling Tool", order=2)

# Define the layout of the website
layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Project Scheduling Tool", 
                        className='text-center text-primary-emphasis'),
                        xs=12, sm=12, md=12, lg=6, xl=6)
    ], justify='around', align='center'),


    html.Br(),

    dbc.Row([
        dbc.Col([html.P("Notice To Proceed (NTP)", 
                        className='col-form-label col-form-label-sm mt-2'),
                dcc.DatePickerSingle(id="ntp", date=date(2024, 10, 10), className="form-control-sm")
                        ], xs=12, sm=12, md=6, lg=2, xl=2),

        dbc.Col([html.P("Requested COD", 
                        className='col-form-label col-form-label-sm mt-2'),
                dcc.DatePickerSingle(id="intended_cod", date=date(2025, 12, 1), className="form-control-sm")
                        ], xs=12, sm=12, md=6, lg=2, xl=2),
        
        dbc.Col([html.P("Calculated COD", 
                        className='col-form-label col-form-label-sm mt-2'),
                dcc.DatePickerSingle(id="cod", date=date(2025, 12, 1), disabled=True, className="form-control-sm")
                        ], xs=12, sm=12, md=6, lg=2, xl=2),

        dbc.Col([html.P("Number of PCSs", 
                        className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='number_of_PCS', type='number', value=25, min=0, className='form-control form-control-sm'),
                ], xs=12, sm=12, md=6, lg=2, xl=2),

        dbc.Col([html.P("Number of Enclosures", 
                        className='col-form-label col-form-label-sm mt-2'),
                dbc.Input(id='number_of_containers', type='number', value=100, min=0, className='form-control form-control-sm'),
                ], xs=12, sm=12, md=6, lg=2, xl=2),

        dbc.Col([html.P("Gantt Chart Schedule Filter", 
                        className='col-form-label col-form-label-sm mt-2'),
                dcc.Dropdown(
                        options = ["Full Project Schedule", "Customer Schedule", "Battery Supplier Schedule", "PCS Supplier Schedule"],
                        value = "Full Project Schedule",
                        multi=False,
                        id = "ddn_gantt_filter" 
                        
                )
                ], xs=12, sm=12, md=6, lg=2, xl=2), 


    ], justify='around', align='center'),
    

    html.Br(),


    dbc.Row([
        dbc.Col([
            html.P('Generate Project Schedule', id='btn_schedule', className="text-center btn btn-primary m-4")
        ], xs=12, sm=12, md=12, lg=2, xl=2), 

    ], justify='around', align='center'), 

    html.Br(),

    dbc.Row([
        dbc.Col([
            dbc.Spinner(dcc.Graph(id = "schedule_gantt", style = {"height":"100vh"}))
        ], xs=12, sm=12, md=12, lg=10, xl=10),
        
        dbc.Col([
            html.H6("Milestone Dates", className="mb-4 strong"),

            dbc.Container(
                 [
                      html.P(id='df_milestones'), 
                  ]),
            
            html.Br(),
            
            html.H6("Critical Durations", className="mb-4 strong"),

            dbc.Container(
                 [
                      html.P(id='df_critical_durations'), 
                  ]),
                        
            html.Br(),
            
            html.H6("Project Schedule Floats", className="mb-4 strong"),

            dbc.Container(
                 [
                      html.P(id='df_floats'), 
                  ]),

            html.Br(),
        
            ], xs=12, sm=12, md=12, lg=2, xl=2),

    ], justify='center', align='top'),
    
    html.Br(),
    html.Br(),
    
    html.Div(dash.dcc.Store(id = "stored_df")),
    html.Div(dash.dcc.Store(id = "stored_fig")),
    html.Div(dash.dcc.Store(id = "stored_df_milestones")),
    html.Div(dash.dcc.Store(id = "stored_df_critical_durations")),

    dbc.Row([
        dbc.Col([
            html.A([
                html.Button('Step 1 - Generate Project Schedule PDF',  id='generate_sch_pdf', style={'width':'300px'}, className="btn btn-primary mt-4", disabled=False),
                dbc.Spinner(html.A('Step 2 - Download Project Schedule PDF', id='download_sch_pdf', href='',  style={'width':'300px'}, className="btn bg-warning mt-4", disable_n_clicks=False)),
                    ]),
        ], xs=12, sm=12, md=12, lg=4, xl=4), 

        dbc.Col([
            html.P('Download Schedule as an Excel', id='dwnld_excel', className="btn btn-primary mt-4"),
            dcc.Download(id="download_schedule_xlsx")
        ], xs=12, sm=12, md=12, lg=3, xl=3)
        
    ], justify='center', align='center'), 

    html.Br(),
    html.Br(),

    dbc.Row([
        dbc.Col([
            dbc.Container(
                 [
                      html.P(id="df_supplier_assump"),
                  ]),
            ], xs=12, sm=12, md=12, lg=4, xl=4),
        dbc.Col([
            dbc.Container(
                 [
                      html.P(id="df_project_assump"),
                  ]),
            ], xs=12, sm=12, md=12, lg=4, xl=4),
    ], justify='center', align='top'),

    html.Br(),
    html.Br(),

], fluid=True), 

@dash.callback(
    Output("schedule_gantt", "figure"),
    Output("stored_fig", "data"),
    Output("cod", "date"),
    Output("stored_df", "data"),
    Output("df_milestones", "children"),
    Output("stored_df_milestones", "data"),
    Output("df_critical_durations", "children"),
    Output("stored_df_critical_durations", "data"),
    Output("df_floats", "children"),
    Output("df_supplier_assump", "children"),
    Output("df_project_assump", "children"),    
    Output("btn_schedule", "n_clicks"),
    [Input('btn_schedule', 'n_clicks'),
    Input('ntp', 'date'),
    Input('intended_cod', 'date'),
    Input('number_of_PCS', 'value'),
    Input('number_of_containers', 'value'),
    Input('ddn_gantt_filter', 'value'),]
)

def gantt_chart(n_clicks, ntp, intended_cod, number_of_PCS, number_of_containers, scope):
    if n_clicks:
        fig, stored_fig, cod_date, schedule_excel, df_milestones, stored_df_milestones, \
            df_critical_durations, stored_df_critical_durations, df_floats, \
                df_supplier_assump, df_project_assump = scheduler(ntp, intended_cod, number_of_PCS, number_of_containers, scope)
        
        return fig, stored_fig, cod_date, schedule_excel, df_milestones, stored_df_milestones, \
            df_critical_durations, stored_df_critical_durations, df_floats, df_supplier_assump, df_project_assump, 0
    else:
        raise PreventUpdate


@dash.callback(
Output('download_sch_pdf', 'href'),
Output('generate_sch_pdf', 'n_clicks'),
 [Input('generate_sch_pdf', 'n_clicks'),
  Input('stored_fig', 'data'),
  Input('stored_df', 'data'),
  Input('stored_df_milestones', 'data'),
  Input('stored_df_critical_durations', 'data'),
 ]
)

def update_schedule_pdf(n_clicks, stored_fig, stored_df, stored_df_milestones, stored_df_critical_durations):

    if n_clicks:        # Generate PDF
        proj_sch_pdf = '/download/{}'.format(create_proj_schedule_pdf(stored_fig, stored_df, \
                                                                      stored_df_milestones, stored_df_critical_durations))
        n_clicks = 0
    else:
        # If button is not clicked, do nothing
        proj_sch_pdf = ''

    return proj_sch_pdf, n_clicks

@dash.callback(
Output('download_sch_pdf', 'disable_n_clicks'),
Output('download_sch_pdf', 'style'),
Output('generate_sch_pdf', 'disabled'),
 [
  Input('ddn_gantt_filter', 'value'),
 ]
)
def update_button(ddn_gantt_filter):
    if ddn_gantt_filter == "Full Project Schedule":
        style = {'width':'300px', 'cursor':' not-allowed', 'pointer-events': 'none'}
        return True, style, True
    else:
        style = {'width':'300px'}
        return False, style, False



@dash.callback(
    Output("download_schedule_xlsx", "data"),
    Output("dwnld_excel", "n_clicks"),
    [Input("dwnld_excel", "n_clicks"),
     Input("stored_df", "data"),
     Input("ddn_gantt_filter", "value"),]
)
def download_excel(n_clicks, proj_schedule_stored, scope):
    if n_clicks:
        df = schedule_excel_op(proj_schedule_stored, scope)
                
        return dcc.send_data_frame(df.to_excel, "Project Schedule.xlsx"), 0
    else:
        raise PreventUpdate