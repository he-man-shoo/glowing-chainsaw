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
from PIL import Image


from sizing_calculations import calculation
from tech_proposal import create_tech_proposal
from cost_memo import create_cost_memo
from general_arrangement import create_GA
from sld import create_SLD


dash.register_page(__name__, name = "Scraper")

# Define the layout of the website
layout = dbc.Container([
    dbc.Row([
        dbc.Col(html.H2("Price Scraper", 
                        className='text-center text-primary-emphasis'),
                        width = {'size':6})
    ], justify='around', align='center'),

    dbc.Row([
        

    ]), 

    dbc.Row([
        dbc.Col([html.P("Original (CNY/mt)"), 
                html.P("Price")], width = {'size':3}),

        dbc.Col([html.P("VAT Included (USD/mt)"), 
                html.P("Price")], width = {'size':3}),

        dbc.Col([html.P("VAT Excluded (USD/mt)"), 
                html.P("Price")], width = {'size':3}),

        dbc.Col([html.P("Exchange Rate (USD/CNY)"), 
                html.P("Price")], width = {'size':3}),
    ], justify='around', align='center')
    
    

], fluid=True)