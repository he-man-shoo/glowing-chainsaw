import dash
import pandas as pd
from dash import Dash, dash_table, dcc, html, Input, Output, State
import io
import requests

import pandas as pd

url = 'https://github.com/he-man-shoo/glowing-chainsaw/raw/main/Months%20to%20COD.xlsx'
df = pd.read_excel(url)
print(df.head(5))