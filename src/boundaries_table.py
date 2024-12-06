import pandas as pd
import dash

def df_tool_assump():
        
    df = pd.DataFrame([])

    df['Parameters'] = [
                                "Project Size", \
                                "Battery Enclosure", \
                                "PCS Selection", \
                                "BESS Interconnection Voltage", \
                                "Design Life", \
                                "Maximum Number of Augmentations", \
                                "Ambient Temperature", \
                                "Site altitude", \
                                "Corossion rating", \
                                "Wind loads (per ASCE 7-16, Risk Category III)", \
                                "IEEE693 Seismic Category", \
                                "Noise", \
                                ]

    df['Tool Boundaries'] = [
                                "up to 3.2GWh (Limited by Calendar Degradation data)", \
                                "HD5 with 314Ah Cells (up to 5.02 MWh per Enclosure)", \
                                "Sungrow 5MVA (default), Sungrow 4MVA (IEC or 6hr Projects), Sungrow 3.45MVA (8hr Projects)", \
                                "34.5kV (by default)", \
                                "up to 20 Years", \
                                "1 augmentation every other year", \
                                "-20 deg C to 50 deg C", \
                                "<=1000 m from Mean Sea Level", \
                                "C4", \
                                "<=110 mph", \
                                "Medium", \
                                "<= 75dBA @ 1 meter from the Equipment", \
                                ]
    
    return df


def table_format(table):
    return dash.dash_table.DataTable(table.to_dict('records', index=True), 
                                        style_data={
                                                    'color': 'black',
                                                    'backgroundColor': 'white', 
                                                    'font-family':'arial',
                                                    'font-size': '14px',
                                                    'border': '1px solid black',
                                                    'textAlign': 'left',
                                                    },
                                        style_data_conditional=[
                                                                {
                                                                'if': {'row_index': 'odd'},
                                                                'backgroundColor': 'rgb(220, 207, 235)',
                                                                }, 

                                                            ],

                                        style_header={
                                                        'backgroundColor': 'rgb(127, 81, 185)',
                                                        'color': 'white',
                                                        'fontWeight': 'bold',
                                                        'font-family':'Helvetica',
                                                        'font-size': '15px',
                                                        'border': '1px solid black',
                                                        'textAlign': 'center',
                                                    })

