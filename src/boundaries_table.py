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

def df_schedule_assump():

    # Assumptions Table

    df = pd.DataFrame([])

    df['Supplier Assumptions'] = [
                               "PCS Supplier: Time from P.O. to FAT of the first unit = 24 weeks", \
                               "PCS Supplier: Shipment rate = 20 units per week", \
                               "PCS Supplier/Battery Supplier: Transportation time from ex-works to site = 8 weeks", \
                               "Battery Supplier: Time from P.O. to Financial Security received by Prevalon = 45 Days", \
                               "Battery Supplier: Time from P.O. to Financial Security received by Buyer = 60 Days", \
                               "Battery Supplier: Time from P.O. to Drawing Confirmation = 45 Days", \
                               "Battery Supplier: Time from P.O. to manufacturing start = 90 Days", \
                               "Battery Supplier: Manufacturing rate = 20 Containers per 2 weeks", \
                               "FAT is performed 10 days after end of each Manufacturing Batch.", \
                               "Batteries are shipped in batches after FAT.", \
                               ]
    
    df['Project Assumptions'] = [
                               "Site is ready to accept delivery 1 week before first batch of equipment is delivered.", \
                               "First batch of PCSs is delivered 4 weeks before first batch of batteries.", \
                               "Commissioning is performed by Feeder (this is not visible in customer schedule).", \
                               "Backfeed is available 1 week before first feeder installation is complete", \
                               "Earlier commissioning start is when first feeder is installed.", \
                               "Minimum commissioning time per feeder 90 days. (8 PCS & 32 Containers).", \
                               "Total commissioning time will scale as defined in the cost sheet. (Maximum project size 2000 MWh requires 139 days)", \
                               "Provisional Acceptance is atleast 14 days after commissioning completion. At max it is 20 days after commissioning completion", \
                               "Final Acceptance is 60 days after Provisional Acceptance.", \
                               " - ", \
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
                                        style_cell={
                                                    'whiteSpace': 'normal',
                                                    'height': 'auto',
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

