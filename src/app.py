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


server = Flask(__name__)


# Keep this out of source code repository - save in a file or a database
VALID_USERNAME_PASSWORD_PAIRS = {
    'irish':'whiskey',
    'rocky':'mountains',
    'dim':'sum',
    'pav':'bhaji',
}


# Initialize the Dash app
app = dash.Dash(server=server, use_pages=True, external_stylesheets=["https://cdn.jsdelivr.net/npm/bootswatch@4.5.2/dist/litera/bootstrap.min.css"],
                meta_tags=[{'name': 'viewport',
                            'content': 'width=device-width, initial-scale=1.0'}]
                )
server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)
server.secret_key = 'hello' # Replace with your actual secret key

input_label_style = {'font-size': '0.95em', 'font-weight': 'bolder'}

button_style = {'width':'200px','border-radius': '4px', 'font-size': '1.25rem', 'border': '1px solid navy','background-color': 'dodgerblue', 'color': 'white'}

logo = Image.open("Prevalon Logo.jpg")

page_layout = []

for page in dash.page_registry.values():
    page_layout.append(dbc.NavItem(dbc.NavLink(page["name"], href=page["path"], active="exact")))

# Define the layout of the website
app.layout = dbc.Container([

    dbc.Row([
                dbc.Col(
                    html.A(
                        children=html.Img(src = logo, width=180),
                        href= 'https://prevalonenergy.com/', 
                        target="_blank"
                    ),
                    width = {'size':3}),
                dbc.NavbarSimple(
                    children = page_layout,
                    color="primary",
                    dark=True)
                    ],justify='between'),
    
    dbc.Container([
        dash.page_container
    ], fluid=True), 

], fluid=True)


@app.server.route('/download/<path:path>')
def serve_static(path):
    return send_file(path, as_attachment=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port = 2400)