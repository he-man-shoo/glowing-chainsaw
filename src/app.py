import dash
import pandas as pd
from dash import Dash, dash_table, dcc, html, Input, Output, State
import plotly.express as px
import dash_bootstrap_components as dbc

app = Dash(__name__)
server = app.server

url = 'https://github.com/he-man-shoo/glowing-chainsaw/raw/main/Months%20to%20COD.xlsx'
df = pd.read_excel(url)
df = df.head(5)


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
         

df = table_format(df)

# Initialize the Dash app
app = dash.Dash(server=server, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
server = app.server

app.layout = html.Div([

      html.Div([
        html.H2(children='Table'),
        html.Br(),
        html.Button('Generate Technical Proposal', id='generate-table'),
        html.Br(),
        dbc.Container([html.P(id = "table"), 
                  ],className='six columns'),
    ], className='row'),

])


# Define callback to update the output

@app.callback(
 Output('table', 'children'),
 Input('generate-table', 'n_clicks')
)

def update_output(n_clicks):
      if n_clicks:
            return df


if __name__ == "__main__":
    app.run_server(debug=True)