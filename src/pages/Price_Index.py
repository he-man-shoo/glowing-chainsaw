import dash
from dash import html
import dash_bootstrap_components as dbc
from reportlab.graphics.shapes import *
from dash.dependencies import Input, Output
from dash.exceptions import PreventUpdate
from dash import dcc
import pandas as pd

from price_scraper import price_scraper_function
from trends_plot import trends_plot_fig

# URL of the raw CSV file on GitHub
url = "https://github.com/he-man-shoo/scraper/raw/refs/heads/main/Price%20Data.xlsx"

# Read the CSV file directly from GitHub into a Pandas DataFrame
df = pd.read_excel(url)


dash.register_page(__name__, name = "Price Index", order=2)

# Define the layout of the website
layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Price Index Dashboard", 
                        className='text-center text-primary-emphasis'),
                        xs=12, sm=12, md=12, lg=6, xl=6)
    ], justify='around', align='center'),

    html.Br(),

    dbc.Row([
        dbc.Col([
            html.H4("Lithium Carbonate (99.5% Battery Grade) Price"),
        ], xs=12, sm=12, md=12, lg=10, xl=10),

        dbc.Col([
            html.A("Reference Link", href='https://www.metal.com/Chemical-compound/201102250059', target="_blank"),
        ], xs=12, sm=12, md=12, lg=2, xl=2),

    ], justify='around', align='center'), 

    html.Br(), 

    dbc.Row([
        dbc.Col([
            dbc.Spinner(dcc.Graph(id = "price_trend", figure=trends_plot_fig(df)))
        ], width = {'size':12})
    ], justify='center', align='center'),


    html.Br(),

    dbc.Row([
        dbc.Col([html.P("Original (CNY/mt)", className="card-text"), 
                dbc.Spinner(html.Div(id="original"))], xs=12, sm=12, md=12, lg=3, xl=3),

        dbc.Col([html.P("VAT Included (USD/mt)"), 
                dbc.Spinner(html.Div(id="vat_incl"))], xs=12, sm=12, md=12, lg=3, xl=3),

        dbc.Col([html.P("VAT Excluded (USD/mt)"), 
                dbc.Spinner(html.Div(id="vat_excl"))], xs=12, sm=12, md=12, lg=3, xl=3),

        dbc.Col([html.P("Exchange Rate (USD/CNY)"), 
                dbc.Spinner(html.Div(id="xchange_rt"))], xs=12, sm=12, md=12, lg=3, xl=3),
    ], justify='around', align='center'),

    html.Br(), 
    
    dbc.Row([
        dbc.Col([
            html.P('Get Current Prices', id='current_prices', className="btn btn-primary mt-4")
        ], xs=12, sm=12, md=12, lg=3, xl=3), 

        dbc.Col([
            html.P('Get Raw Data', id='historical_data', className="btn btn-primary mt-4"),
            dcc.Download(id="download_df_xlsx")
        
        ], xs=12, sm=12, md=12, lg=3, xl=3)
    ], justify='center', align='center'), 

], fluid=True), 


@dash.callback(
    Output('original', 'children'),
    Output('vat_incl', 'children'),
    Output('vat_excl', 'children'),
    Output('xchange_rt', 'children'),
    Output('current_prices', 'n_clicks'),
    [Input('current_prices', 'n_clicks')]
)

def scrape(n_clicks):
    if n_clicks:
        output_list = price_scraper_function()
        l = []
        for i in output_list:
            l.append('{:,.2f}'.format(i))

        n_clicks = 0
        

        return l[0], l[1], l[2], l[3], n_clicks
    else:
        raise PreventUpdate

@dash.callback(
    Output("download_df_xlsx", "data"),
    Input("historical_data", "n_clicks"),
)
def download_historic_data(n_clicks):
    if n_clicks:
        return dcc.send_data_frame(df.to_excel, "Historic Price Indices.xlsx")
    else:
        raise PreventUpdate
    