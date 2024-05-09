import dash
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
from scipy import interpolate
import math
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from flask import send_file
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from flask import send_from_directory
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import requests
from PIL import Image
from reportlab.platypus import Image as PlatypusImage
from io import BytesIO
import os
import plotly.graph_objects as go
import plotly.io as pio
import dash_auth
from reportlab.platypus import SimpleDocTemplate, Paragraph
from flask import Flask


server = Flask(__name__)


# # Keep this out of source code repository - save in a file or a database
# VALID_USERNAME_PASSWORD_PAIRS = {
#     'hello': 'world'
# }


def calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations):
    pd.set_option('display.max_colwidth', 200)
        
    energy_req = power_req*duration #MWh
    battery_model = 'HD 511' # Option to Choose Clou AC or Clou LC or HD 511 based on Batteries.xlsx
    r_SOC = 0.5 # % resting SOC

    PCS_model = 'Sungrow SC5000UD-MV-US' # Option to Choose based on PCS.xlsx

    design_margin = 0.01 #1% Margin
    rte_margin = 0.01 #1% Margin

    if duration == 4:
        aux_energy_percentage = 0.0105
    else:
        aux_energy_percentage = 0.01666

    aux_power_percentage = 0.0310569

    def get_DC_RTE(battery_model,duration):
        df = pd.read_excel('DC RTE.xlsx')
        df.index = df["End of Year"]
        df = df.loc[0:] 

        l = []
        for i in df[str(battery_model+' | '+str(duration))]:
            l.append(math.sqrt(i))
        df.loc[:, "Discharge Efficiency"] = l
        df = df[[str(battery_model+' | '+str(duration)), 'Discharge Efficiency']]
        return pd.DataFrame(df)

    ## Get relevant degradation curve from the Excel Library
    #### And if HD 511, multiply with discharge efficiency

    def get_deg_curve(battery_model,number_cycles,duration,r_SOC):
        df = pd.read_excel('Degradation Curves.xlsx')
        df.index = df["End of Year"]
        df = df.loc[0:25,  str(battery_model+' | '+str(number_cycles)+' | '+str(duration)+' | '+str(r_SOC))]
        df = pd.DataFrame(df)

        if battery_model == "HD 511":
            df["Degradation Curve"] = df[str(battery_model+' | '+str(number_cycles)+' | '+str(duration)+' | '+str(r_SOC))]*get_DC_RTE(battery_model,duration)["Discharge Efficiency"]
        else:
            df["Degradation Curve"] = df[str(battery_model+' | '+str(number_cycles)+' | '+str(duration)+' | '+str(r_SOC))]
        return df


    ## Get relevant Battery Data from Excel File

    def get_batt_data(battery_model):
        df = pd.read_excel('Batteries.xlsx')
        df.index = df["Model"]
        df = df[battery_model]
        batt_nameplate = df['Nameplate Energy']
        batt_max_voltage = df['Rack Vmax (V)']
        batt_min_voltage = df['Rack Vmin (V)']
        batt_short_circuit_current = df['DC Short circuit current (kA)']
        max_racks_per_container = df['Maximum Racks per Container']
        usable_capacity_ratio = df['usable_capacity_ratio_at_'+str(1/duration)+'C']
        peak_aux_power_per_container = df['peak_aux_power_per_container (kW)']
        aux_energy_per_container = df['aux_energy_per_container (kWh)']
        
        return batt_nameplate, batt_max_voltage, batt_min_voltage, batt_short_circuit_current, max_racks_per_container, usable_capacity_ratio, peak_aux_power_per_container, aux_energy_per_container

    ## Get relevant PCS Data from Excel File

    def get_PCS_data(PCS_model, max_site_temp):
        df = pd.read_excel('PCS.xlsx')
        df.index = df["Model"]
        df = df[PCS_model]

        # Building Interpolator
        x = [25, 40, 45, 50]
        y = df[:4]
        f = interpolate.interp1d(x, y)

        PCS_kVA_at_max_site_temp = float(f(max_site_temp))

        PCS_min_voltage = df['Vdc minimum']
        PCS_max_voltage = df['Vdc maximum']
        PCS_short_circuit_capability = df['DC short circuit current per Input']
        PCS_AC_Voltage = df['rated Vac']
        PCS_efficiency = df['efficiency']
        PCS_kVA = float(f(25))
        
        return PCS_kVA_at_max_site_temp, PCS_min_voltage, PCS_max_voltage, PCS_short_circuit_capability, PCS_AC_Voltage, PCS_efficiency, PCS_kVA


    ## Create Losses Table and Find One Way Efficiency
    def get_losses_table(point_of_measurement):
        loss_to_POM = pd.read_excel('Losses Table.xlsx', header=None)

        Inverter_Losses = pd.DataFrame([['Inverter', 1 - PCS_efficiency]],index=[1])
        loss_to_POM = pd.concat([loss_to_POM.iloc[:1], Inverter_Losses, loss_to_POM.iloc[1:]]).reset_index(drop=True)
        loss_to_POM.columns = ['Parameter', 'Losses(%)']
        loss_to_POM['Efficiency(%)'] = 1 - loss_to_POM['Losses(%)']

        if point_of_measurement == 'AC Terminals of Inverter':
            loss_to_POM = loss_to_POM.iloc[:2, :]
        if point_of_measurement == 'High Side of Medium Voltage Transformer':
            loss_to_POM = loss_to_POM.iloc[:3, :]
        if point_of_measurement == 'Medium Voltage POM':
            loss_to_POM = loss_to_POM.iloc[:4, :]
        if point_of_measurement == 'High Side of HV Transformer':
            loss_to_POM = loss_to_POM.iloc[:5, :]
        if point_of_measurement == 'High Voltage POM':
            loss_to_POM = loss_to_POM.iloc[:6, :]

        return loss_to_POM

    ## Calculate Calendar Losses to COD

    def get_calendar_loss_table(energy_req):
        df = pd.read_excel('Months to COD.xlsx')
        

        df = df.loc[df['Rated energy (MWh)']>energy_req].iloc[0]

        months_to_COD = df['Shipment & Commissioning Duration']
        calendar_loss_to_COD = df['Capacity Loss']

        return months_to_COD, calendar_loss_to_COD

    batt_nameplate, batt_max_voltage, batt_min_voltage, batt_short_circuit_current, max_racks_per_container, usable_capacity_ratio, peak_aux_power_per_container, aux_energy_per_container = get_batt_data(battery_model)

    PCS_kVA_at_max_site_temp, PCS_min_voltage, PCS_max_voltage, PCS_short_circuit_capability, PCS_AC_Voltage, PCS_efficiency, PCS_kVA = get_PCS_data(PCS_model, max_site_temp)

    loss_to_POM = get_losses_table(point_of_measurement)
    one_way_eff = loss_to_POM['Efficiency(%)'].product()

    months_to_COD, calendar_loss_to_COD = get_calendar_loss_table(energy_req)

    ## Usable DC at Battery Terminals

    #### If DC Voltage Range of Batteries is outside that of PCS Input Voltage Range, the usable_capacity_ratio will be derated
    if PCS_min_voltage >  batt_min_voltage or PCS_max_voltage < batt_max_voltage:
        if battery_model == 'Clou AC':
            usable_capacity_ratio = usable_capacity_ratio * 0.997
        if battery_model == 'Clou LC':
            usable_capacity_ratio = usable_capacity_ratio * 0.996

    batt_usable = batt_nameplate*(1-calendar_loss_to_COD)*usable_capacity_ratio*(1-design_margin)
    batt_usable_ac = batt_usable*(1-aux_energy_percentage)*one_way_eff

    aux_energy_per_stack = batt_usable - batt_usable*(1-aux_energy_percentage)

    ## Number of Stacks required
    energy_req_at_bol = energy_req/get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"][oversize_required]
    min_number_of_stacks = math.ceil(energy_req_at_bol*1000/batt_usable_ac)

    ## Number of PCSs
    one_way_eff_from_Inverter_to_POI = loss_to_POM.iloc[2:, :]['Efficiency(%)'].product()
    kW_required_at_Inverter = power_req*(1+aux_power_percentage)*1000/one_way_eff_from_Inverter_to_POI

    aux_power = power_req*(1+aux_power_percentage) - power_req

    ### PCS oversize required due to Reactive Power requirement

    kVAR_required_at_POM = math.sqrt((power_req*1000/PF_required_at_POM)**2 - (power_req*1000)**2)
    kVAR_required_at_Inverter = kVAR_required_at_POM * 1.64186

    ### kVA Required at PCS Terminals 
    kVA_required_at_Inverter = math.sqrt(kW_required_at_Inverter**2 + kVAR_required_at_Inverter**2)

    ### Minimum Number of PCS Required
    min_number_of_Inverters_required = math.ceil(kVA_required_at_Inverter/PCS_kVA_at_max_site_temp)

    ### Get Cost for Components
    def get_financials_table(PCS_model):
        df = pd.read_excel('f.xlsx', index_col="Component")


        cost_container = df.loc[df.index == 'Containers']["Cost"]['Containers']
        cost_stack = df.loc[df.index == 'Stacks']["Cost"]['Stacks']

        if RMU_Required == "IEC":
            cost_pcs = df.loc[df.index == str(PCS_model + " | RMU")]["Cost"][str(PCS_model + " | RMU")]
            PCS_model = str(PCS_model) + " | RMU"
        else:
            cost_pcs = df.loc[df.index == str(PCS_model)]["Cost"][str(PCS_model)]


        return cost_container, cost_stack, cost_pcs

    cost_container, cost_stack, cost_pcs = get_financials_table(PCS_model)

    # Optimize Number Cost
    stacks_config = [8, 10, 12, 16, 20, 24, 26, 28, 30, 32, 34, 36, 40, 44, 48]

    container_config = [1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 3, 4, 4, 4]

    for i in range (len(stacks_config)):
        actual_number_of_pcs = math.ceil(min_number_of_stacks/stacks_config[i])
        actual_number_of_stacks = actual_number_of_pcs * stacks_config[i]
        actual_number_of_containers = actual_number_of_pcs*container_config[i]
        cost = actual_number_of_pcs*cost_pcs + actual_number_of_stacks*batt_nameplate*cost_stack + actual_number_of_containers*cost_container

        #print(actual_number_of_pcs, actual_number_of_stacks, actual_number_of_containers, cost)
    
        if i == 0: minimized_cost = cost

        if cost <= minimized_cost and actual_number_of_pcs >= min_number_of_Inverters_required: 
            minimized_cost = cost
            optimized_number_of_pcs = actual_number_of_pcs
            optimized_number_of_stacks = actual_number_of_stacks
            optimized_number_of_containers = actual_number_of_containers

            #print(optimized_number_of_pcs, optimized_number_of_stacks, optimized_number_of_containers, minimized_cost)

    bol_config = pd.DataFrame({"Parameter" : ["Number of Stacks | "+str(math.ceil(batt_nameplate)) + " kWh", "Number of "+ str(battery_model) + " Containers", "Number of PCS | " + str(PCS_model)], 
                               "Quantities (#)" : [optimized_number_of_stacks, optimized_number_of_containers, optimized_number_of_pcs]}) 


    #bol_design_table = pd.DataFrame({})

    # bol_config.loc[3, "Parameter"] = "Months from FAT to COD"
    # bol_config.loc[3, "Quantities (#)"] = months_to_COD
    
    # bol_config.loc[4, "Parameter"] = "BESS Peak Aux Power (kW)"
    # bol_config.loc[4, "Quantities (#)"] = '{:,.2f}'.format(aux_power*1000)
    
    # bol_config.loc[5, "Parameter"] = "Aux Energy during discharge (kWh)"
    # bol_config.loc[5, "Quantities (#)"] = '{:,.2f}'.format(aux_energy_per_stack*optimized_number_of_stacks)


    financial_table = pd.DataFrame({})
    financial_table["Component"] = ["Stacks | "+str(math.ceil(batt_nameplate)*optimized_number_of_stacks) + " kWh", str(battery_model) + " Containers", "PCS | " + str(PCS_model)]

    financial_table["Per Unit Cost ($)"] =['${:,.2f}'.format(cost_stack), '${:,.2f}'.format(cost_container), '${:,.2f}'.format(cost_pcs)]

    financial_table["Total Cost per component ($)"] =[ '${:,.2f}'.format(math.ceil(optimized_number_of_stacks*cost_stack)), '${:,.2f}'.format(math.ceil(optimized_number_of_containers*cost_container)), '${:,.2f}'.format(math.ceil(optimized_number_of_pcs*cost_pcs))]

    financial_table.loc[3, "Component"] = "Total Equipment Cost Ex-Works ($)"
    financial_table.loc[3, "Total Cost per component ($)"] = '${:,.2f}'.format(math.ceil(optimized_number_of_stacks*cost_stack) + math.ceil(optimized_number_of_containers*cost_container) + math.ceil(optimized_number_of_pcs*cost_pcs))

    ## Power - Energy Table
    power_energy_table = pd.DataFrame(optimized_number_of_stacks*batt_usable_ac*get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"])
    power_energy_table = power_energy_table.rename(columns={"Degradation Curve": 'Net Energy @ BOL at '+ str(point_of_measurement)+ ' (kWh)'})
    power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'] = power_energy_table['Net Energy @ BOL at '+ str(point_of_measurement)+ ' (kWh)']

    i = 0

    aug_energy_table = pd.DataFrame({})

    year_of_next_augmentation = 0

    if number_of_augmentations > 0 :

        while year_of_next_augmentation < project_life:

            year_of_augmentation = power_energy_table.loc[power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'] < energy_req*1000].index.values[0]
            if i ==0:
                year_of_next_augmentation = math.ceil((project_life - year_of_augmentation)/number_of_augmentations) + year_of_augmentation
                augmentation_gap = year_of_next_augmentation - year_of_augmentation
            else:
                year_of_next_augmentation = year_of_next_augmentation + augmentation_gap


            if year_of_next_augmentation > project_life:
                year_of_next_augmentation = project_life
            
            #print(year_of_augmentation, year_of_next_augmentation, augmentation_gap)
            
            augmentation_energy_required = (energy_req*1000 - power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][year_of_next_augmentation])/get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"][year_of_next_augmentation - year_of_augmentation]
            augmentation_energy_nameplate = augmentation_energy_required/get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"][0]*batt_nameplate/batt_usable_ac
            
            power_energy_table['Net Energy after Augmentation ' + str(i+1) +' at '+ str(point_of_measurement)+ ' (kWh)'] = augmentation_energy_required*get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"]
            power_energy_table['Net Energy after Augmentation ' + str(i+1) +' at '+ str(point_of_measurement)+ ' (kWh)'] = power_energy_table['Net Energy after Augmentation ' + str(i+1) +' at '+ str(point_of_measurement)+ ' (kWh)'].shift(year_of_augmentation, fill_value = 0)
            power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'] = power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'] + power_energy_table['Net Energy after Augmentation ' + str(i+1) +' at '+ str(point_of_measurement)+ ' (kWh)']

            aug_energy_table.loc[i, "Augmentation Number"] = i+1
            aug_energy_table.loc[i, "Augmentation Year"] = year_of_augmentation
            aug_energy_table.loc[i, "Augmentation Nameplate Energy (kWh)"] = augmentation_energy_nameplate
            

            i = i + 1
        
        aug_energy_table["Augmentation Nameplate Energy (kWh)"] = aug_energy_table["Augmentation Nameplate Energy (kWh)"].apply(lambda x:'{:,.2f}'.format(x))

    power_energy_rte_table = pd.DataFrame({})

    power_energy_rte_table["End of Year"] = power_energy_table.index

    power_energy_rte_table["Usable AC Power at POM (MW)"] = '{:,.2f}'.format(power_req)

    power_energy_rte_table["Usable AC Energy at POM (MWh)"] = power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)']*0.001
    power_energy_rte_table["Usable AC Energy at POM (MWh)"] = power_energy_rte_table["Usable AC Energy at POM (MWh)"].apply(lambda x:'{:,.2f}'.format(x))

    power_energy_rte_table["AC RTE including Aux at POM (%)"] = (get_DC_RTE(battery_model, duration).loc[:, str(battery_model) + " | " + str(duration)]*one_way_eff*one_way_eff*(1-aux_energy_percentage)*(1-aux_energy_percentage)-rte_margin)*100
    power_energy_rte_table["AC RTE including Aux at POM (%)"] = power_energy_rte_table["AC RTE including Aux at POM (%)"].apply(lambda x:'{:,.2f}%'.format(x))

    power_energy_rte_table = power_energy_rte_table.loc[:project_life, :]
    

    bill_of_materials = pd.DataFrame({})

    if RMU_Required == "IEC":
        pcs_string ="Power Conversion System (PCS) stations \n" \
                     "(includes Inverter, \n Medium Voltage (MV) Transformer \n" \
                      " and Ring Main Unit (RMU))"
    else:
        pcs_string ="Power Conversion System (PCS) stations \n" \
                "(includes Inverter and \n Medium Voltage (MV) Transformer)"

    bill_of_materials["Component"] = "LFP Cooled \nBattery Enclosures", \
                                     pcs_string, \
                                     "EMS / SCADA", \
                                     "Master Fire Panel"

    bill_of_materials["Description"] = "Standard-sized ISO 20’ NEMA 3R enclosure with battery modules pre-installed, featuring: \n" \
                                        " 1) Up to " + '{:,.2f}'.format(max_racks_per_container*batt_nameplate*0.001) + "MWh DC Nameplate Energy per enclosure.  \n" \
                                        " 2) Dimensions: 20’ (L) x 9.5’ (H) x 8’ (W) or 6,058mm (L) x 2,896mm (H) x 2,438mm (W)", \
                                        "1) Integrated skid containing "+ '{:,.0f}'.format(PCS_kVA*0.001) +"MVA Inverter and mineral oil-filled transformer -  \n" \
                                        "2) AC Output Power: " + '{:,.0f}'.format(PCS_kVA_at_max_site_temp) + "kVA @ "+ '{:,.0f}'.format(max_site_temp) +" deg C  \n" \
                                        "3) " + '{:,.0f}'.format(PCS_kVA) + "kVA " +'{:,.2f}'.format(PCS_AC_Voltage*0.001) + "kV/34.5kV mineral oil (PCB free) filled MV Transformer\n" \
                                        "4) Dimensions: 20’ (L) x 9.5’ (H) x 8’ (W) or 6,058mm (L) x 2,896mm (H) x 2,438mm (W)", \
                                        "Energy Management System with SCADA interface for BESS Dispatch and Control", \
                                        "Environmentally controlled NEMA 3R enclosure housing \n" \
                                        "master fire panel with battery backup"
    
    bill_of_materials["Quantity"] = optimized_number_of_containers, optimized_number_of_pcs, "Included", "Included"

    design_summary = pd.DataFrame({})

    design_summary["Parmeter"] = "Power Required at Point of Measurement (POM) in kW AC", \
                                    "Energy Required at POM in kWh AC", \
                                    "Point of Measurement (POM)", \
                                    "Performance Period (Years)", \
                                    "Number of cycles per year", \
                                    "Average Resting State of Charge (rSOC)", \
                                    "Operating Temperature Range (°C)", \
                                    "Altitude", \
                                    "Power Factor Required at POM "
    
    design_summary["Value"] = '{:,.0f}'.format(power_req*1000), '{:,.0f}'.format(energy_req*1000), point_of_measurement, project_life, \
                                "up to " + str(number_cycles) + " cycles/year" , "≤ 50%", "-20 deg C to " + str(max_site_temp) + " deg C", \
                                "≤ 1000 meters above Mean Sea Level (MSL)", '{:,.2f}'.format(PF_required_at_POM)



    

    losses_table = get_losses_table(point_of_measurement)

    losses_table = losses_table.replace("DC Cables", "DC Cables*")
    losses_table = losses_table.replace("Medium Voltage AC Cables", "Medium Voltage AC Cables*")
    losses_table = losses_table.replace("High Voltage Transformer", "High Voltage Transformer*")
    losses_table = losses_table.replace("High Voltage AC Cables", "High Voltage AC Cables*")

    losses_table = losses_table.drop(["Efficiency(%)"], axis=1)
    
    losses_table["Losses(%)"] = losses_table["Losses(%)"]*100
    losses_table["Losses(%)"] = losses_table["Losses(%)"].apply(lambda x:'{:,.2f}%'.format(x))

    
    bol_design_summary = pd.DataFrame({})

    bol_design_summary["Parmeter"] = "Total Number of Battery Enclosures", \
                                    "Number of PCS/Transformers", \
                                    "PCS/Transformer Model", \
                                    "BESS Peak Aux Power (kW) \n(included in Total BESS AC Power Required at POM)", \
                                    "Aux Energy during discharge (kWh) \n(included in Total BESS BOL AC Usable Energy Required at POM)", \
                                    "BESS BOL AC Usable Energy net of Aux Energy at POM (kWh AC)"
    
    bol_design_summary["Value"] = '{:,.0f}'.format(optimized_number_of_containers), '{:,.0f}'.format(optimized_number_of_pcs), PCS_model, '{:,.2f}'.format(aux_power*1000), \
                                '{:,.2f}'.format(aux_energy_per_stack*optimized_number_of_stacks) , '{:,.2f}'.format(float(power_energy_rte_table["Usable AC Energy at POM (MWh)"][0])*1000)

                                        


    x_param = power_energy_table[:project_life+1].index.values.tolist()
    y_param = power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][:project_life+1]*0.001
    fig = go.Figure()
    fig.add_trace(go.Scatter(x = x_param, y = y_param, name= "Net Energy @ POM", mode = "markers", marker=dict(symbol = "circle", color='purple', size = 10)))

    fig.add_trace(go.Line(x = x_param, y = len(x_param)*[energy_req],  name= "Net Energy Required @ POM", marker=dict(color ="red")))

    fig.update_layout(title={"text": str(proj_location) + " | " + str(proj_name) + " | " + str(energy_req) + " MWh Energy Capacity @ "+ str(point_of_measurement) + " | " + str(number_cycles) + " cycles/year", "x" : 0.5, "y" : 0.9},#,"y"：8.97，"x"：8.5，"anchor": "center","yanchor": "top"}, 
        
        xaxis=dict(showgrid=False, zeroline=True, showline=True, mirror= True, gridcolor='#bdbdbd', gridwidth=1, zerolinecolor='#969696', zerolinewidth=2, linecolor='#636363', linewidth=2, showticklabels=True, dtick = 1, range=["-0.5", str(project_life+0.5)]),
        yaxis=dict(showgrid=True, zeroline=True, showline=True, mirror=True, gridcolor='#bdbabd', gridwidth=1, zerolinecolor='#969696', zerolinewidth=2, linecolor='#636363', linewidth=2, showticklabels=True, range=[str(power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][project_life]*0.001 - power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][project_life]*0.001/10), str(batt_nameplate*optimized_number_of_stacks*0.001)]),
        xaxis_title='End of Year',
        yaxis_title= 'Energy (MWh)',
        
        

        plot_bgcolor = "white",
        legend=dict(
                    x=0.8,
                    y=-0.25,
                    traceorder="reversed",
                    title_font_family="arial",
                    font=dict(
                        family="arial",
                        size=12,
                        color="black"),
                    bgcolor="white",
                    bordercolor="Black",
                    borderwidth=1.5
                    ),
        font=dict(family="arial", size=18))
    


    return fig, bol_config, aug_energy_table, power_energy_rte_table, financial_table, bill_of_materials, design_summary, losses_table, bol_design_summary




# Initialize the Dash app
app = dash.Dash(server=server, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
server = app.server

# auth = dash_auth.BasicAuth(
#     app,
#     VALID_USERNAME_PASSWORD_PAIRS
# )


# Define the layout of the website
app.layout = html.Div([
    
    html.H1(children='Level 1 Sizing Tool', style={'textAlign': 'center'}),
                html.Br(),
    
    
    html.Div([
        
        html.Div([html.H5("Project Location"),
                  dcc.Input(id='inp_projloct', type='text', value="Lake Mary"),
                  ], style = {"textAlign":"center"}, className='three columns'),
        
        html.Div([html.H5("Project Name"),
                  dcc.Input(id='inp_projnm', type='text', value="Pilot Project"),
                  ],style = {"textAlign":"center"} ,className='three columns'),
        
        html.Div([html.H5('Project Size (MW)'),
                  dcc.Input(id='inp_projsize', type='number', value=100),
                  ], style = {"textAlign":"center"}, className='three columns'),
        
        html.Div([html.H5('Duration (hrs):'),
            dcc.Dropdown(id='ddn_duration', options=[
                {'label': '2', 'value': 2},
                {'label': '3', 'value': 3},
                {'label': '4', 'value': 4},
                {'label': '5', 'value': 5},
                {'label': '6', 'value': 6},
                {'label': '8', 'value': 8},
                ], value= 4),
        ], style = {"textAlign":"center"}, className='three columns')
    ], className='row'),

html.Br(),


    html.Div([

        html.Div([
            html.H5('Number of Cycles per Year'),
            dcc.Dropdown(id='ddn_cyc', options=[
                        {'label': '180', 'value': 180},
                        {'label': '365', 'value': 365},
                        {'label': '548', 'value': 548},
                        {'label': '730', 'value': 730},
                        ], value= 365),
        ], style = {"textAlign":"center"}, className='three columns'),

        html.Div([
            html.H5('Point of Measurement'),
            dcc.Dropdown(id='ddn_pom', options=[
                {'label': 'AC Terminals of Inverter', 'value': 'AC Terminals of Inverter'},
                {'label': 'High Side of Medium Voltage Transformer', 'value': 'High Side of Medium Voltage Transformer'},
                {'label': 'Medium Voltage POM', 'value': 'Medium Voltage POM'},
                {'label': 'High Side of HV Transformer', 'value': 'High Side of HV Transformer'},
                {'label': 'High Voltage POM', 'value': 'High Voltage POM'},
                ], value= 'High Side of HV Transformer'),
        ], style = {"textAlign":"center"}, className='three columns'),
          
        html.Div([html.H5('Compliance Code'),
            dcc.Dropdown(id='ddn_rmu', options=[
                        {'label': 'UL', 'value': 'UL'},
                        {'label': 'IEC', 'value': 'IEC'}
                        ], value= 'UL'),
                        ],style = {"textAlign":"center"}, className='three columns'),

        html.Div([html.H5('Power Factor'),
                    dcc.Dropdown(id='ddn_pf', options=[
                                {'label': '0.9', 'value': 0.90},
                                {'label': '0.95', 'value': 0.95}
                                ], value= 0.95),]
                ,style = {"textAlign":"center"}, className='three columns'),    
    ], className='row'),

html.Br(),

  html.Div([

        html.Div([html.H5('Temperature (deg C)'),
                dcc.Input(id='inp_temp', type='number', value=40),
                ], style = {"textAlign":"center"}, className='three columns'),

        html.Div([html.H5('BOL Oversize (years)'),
                dcc.Input(id='inp_overize', type='number', value=3),], style = {"textAlign":"center"}, className='three columns'),

        html.Div([html.H5("Project Life (years)"),
                  dcc.Input(id='inp_projlife', type='number', value=20),
                  ], style = {"textAlign":"center"},className='three columns'),

        html.Div([html.H5("Number of Augmentations"),
                  dcc.Input(id='inp_aug', type='number', value=4),]
                 ,style = {"textAlign":"center"} ,className='three columns'),

                ], className='row'),

html.Br(),

    html.Div([
        html.H2(children='Energy Plot'),
            dcc.Graph(id = "plot", style = {"height":"90vh"}), #"width":"120vh"})
                ], className='row'),

html.Br(),

    html.Div([
        html.H2(children='BOL Configuration Table'),
        html.Br(),
        dbc.Container([html.P(id = "bol_config"), 
                    ], fluid=True, className='six columns'), 
                ],  className='row'),

html.Br(),

    html.Div([
        html.H2(children='Augmentation Table'),
        html.Br(),
        dbc.Container([html.P(id = "aug_energy_table"),
                    ], className='six columns'),
                ],  className='row'),

html.Br(),

    html.Div([
        html.H2(children='Power Energy and RTE Table'),
        html.Br(),
        dbc.Container([html.P(id = "power_energy_rte_table"), 
                        ], className='six columns'),
                ], style = {'center': "auto"}, className='row'),

html.Br(),

html.Br(),

html.Div([
    # dash.dcc.Store(id = "stored_energy_plot"),
    dash.dcc.Store(id = "stored_bill_of_materials"),
    dash.dcc.Store(id = "stored_design_summary"),
    dash.dcc.Store(id = "stored_losses_table"),
    dash.dcc.Store(id = "stored_bol_design_summary"),
    dash.dcc.Store(id = "stored_aug_energy_table"),
    dash.dcc.Store(id = "stored_power_energy_rte_table"),
]),

html.Br(),

html.Div([
    html.Button('Generate Technical Proposal', id='generate-pdf-button'),
    html.A('Download Technical Proposal', id='download-pdf', href='', style= {"background-color": "rgb(127, 81, 185)", "color": "white", "padding": "7px 10px"})
        ]),

html.Br(),


])



# Define callback to update the output

@app.callback(
    Output('plot', 'figure'),
    Output('bol_config', 'children'),
    Output('aug_energy_table', 'children'),
    Output('power_energy_rte_table', 'children'),
    # Output('financial_table', 'children'),
    # Output('stored_energy_plot', 'data'),
    Output('stored_bill_of_materials', 'data'),
    Output('stored_design_summary', 'data'),
    Output('stored_losses_table', 'data'),
    Output('stored_bol_design_summary', 'data'),
    Output('stored_aug_energy_table', 'data'),
    Output('stored_power_energy_rte_table', 'data'),
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
     Input('inp_aug', 'value'),]
)
def update_output(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations):
    fig, bol_config, aug_energy_table, power_energy_rte_table, financial_table, bill_of_materials, design_summary, losses_table, bol_design_summary = calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations)
    
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

    # financial_table_dict = table_format(financial_table)

    fig_stored = fig

    bill_of_materials_stored = bill_of_materials.to_dict()

    design_summary_stored = design_summary.to_dict()

    losses_table_stored = losses_table.to_dict()

    bol_design_summary_stored = bol_design_summary.to_dict()

    aug_energy_table_stored = aug_energy_table.to_dict()

    power_energy_rte_table_stored = power_energy_rte_table.to_dict()

    return fig, bol_config, aug_energy_dict, power_energy_rte_dict, bill_of_materials_stored, design_summary_stored, \
    losses_table_stored, bol_design_summary_stored, aug_energy_table_stored, power_energy_rte_table_stored



@app.callback(
Output('download-pdf', 'href'),
Output('generate-pdf-button', 'n_clicks'),
 [Input('generate-pdf-button', 'n_clicks'),
  Input('inp_projloct', 'value'),
  Input('inp_projnm', 'value'),
  Input('inp_projsize', 'value'),
  Input('ddn_duration', 'value'),
  Input('inp_projlife', 'value'),
#   Input('stored_energy_plot', 'data'),
  Input('stored_bill_of_materials', 'data'),
  Input('stored_design_summary', 'data'),
  Input('stored_losses_table', 'data'),
  Input('stored_bol_design_summary', 'data'),
  Input('stored_aug_energy_table', 'data'),
  Input('stored_power_energy_rte_table', 'data'),
 ]
)

def update_pdf(n_clicks ,proj_location, proj_name, power_req, duration, project_life, bill_of_materials, design_summary, losses_table, \
                                    bol_design_summary, aug_energy_table, power_energy_rte_table):
    
    def create_pdf_with_header_footer(proj_location, proj_name, power_req, duration, project_life, bill_of_materials, design_summary, losses_table, \
                                    bol_design_summary, aug_energy_table, power_energy_rte_table):

        # Define Colors 
        prevalon_lavendar = colors.Color(220/256,207/256,235/256)
        prevalon_purple = colors.Color(127/256,81/256,185/256)
        # Create a list to hold the contents of the PDF
        content = []

        # Define styles
        styles = getSampleStyleSheet()
        style_normal = styles["Normal"]

        # folder_path = "images"
        # if not os.path.exists(folder_path):
        #     os.makedirs(folder_path)

        # # Save the Plotly graph as an image file
        # image_path = os.path.join(folder_path, "plot.png")
        # pio.write_image(fig, image_path, height = 650, width=1400)

        # Define header and footer function with image from URL
        def header(canvas, doc):
            
            canvas.saveState()
            url = "https://power.widen.net/content/kutz5pgcjw/jpeg/Prevalon-Logo-RGB-C+.jpeg?w=300"  # Replace with the URL of your image
            response = requests.get(url)
            img = Image.open(BytesIO(response.content))
            img_reader = ImageReader(img)
            
            header_left_size = 1*inch
            canvas.drawImage(img_reader, 25, doc.bottomMargin + doc.height + doc.topMargin - header_left_size, width=header_left_size*1.827852998065764, height=header_left_size)  # Adjust image dimensions and position as needed

            # Define the text to be wrapped
            text = "400 International Parkway, Suite 200, Heathrow, FL 32746"

            # Set the position and dimensions for drawing the text
            width = 150
            x = doc.leftMargin + doc.width + doc.rightMargin - width - 25
            y = doc.bottomMargin + doc.height + doc.topMargin - 25
            
            line_spacing = 12

            # Set font size and color
            canvas.setFont("Helvetica", 8)  # Set font to Helvetica with size 12
            canvas.setFillColorRGB(0, 0, 0)  # Set fill color to red (RGB: 1, 0, 0)

            # Split the text into lines based on the width
            lines = []
            current_line = ''
            for word in text.split():
                
                if canvas.stringWidth(current_line + ' ' + word) < width:
                    current_line += ' ' + word
                else:
                    lines.append(current_line.strip())
                    current_line = word
            lines.append(current_line.strip())

            # Draw each line individually
            for line in lines:
                text_width = canvas.stringWidth(line)
                x_adjusted = x + (width - text_width)  # Adjust x position for right indentation
                canvas.drawString(x_adjusted, y, line)
                y -= line_spacing

            # Set font size and color
            canvas.setFont("Helvetica", 8)  # Set font to Helvetica with size 12
            canvas.setFillColorRGB(84/256, 50/256, 122/256)  # Set fill color to red (RGB: 1, 0, 0)

            y -= line_spacing

            canvas.drawString(x_adjusted, y, "PrevalonEnergy.com")
            canvas.restoreState()

            # Footer

            canvas.saveState()

            footer_x = 0
            footer_y = 25
            canvas.setFillColorRGB(252/256, 215/256, 87/256)

            # Set border color to transparent
            canvas.setStrokeColorRGB(1, 1, 1, 0)  # Set border color to transparent (RGB: 1, 1, 1) and alpha (opacity) to 0
            canvas.setFont("Helvetica", 12)

            canvas.rect(footer_x, footer_y, 25, 25, fill=1)

            page_num = canvas.getPageNumber()

            canvas.setFillColorRGB(0, 0, 0)
            canvas.drawString(25, 25+6, "%d" % page_num)

            canvas.restoreState()

        pdf_file = str(proj_name) + " example.pdf"
        # Create a PDF document
        doc = SimpleDocTemplate(
            pdf_file,
            pagesize=letter,
        )
            #     pdf_file = str(proj_name) + "example.pdf"
    #     doc = SimpleDocTemplate(pdf_file, pagesize=letter)
        # Table data

        bill_of_materials = pd.DataFrame.from_dict(bill_of_materials)

        bill_of_materials_data = []
        bill_of_materials_data.append(bill_of_materials.columns.tolist())
        for i in bill_of_materials.values.tolist():
            bill_of_materials_data.append(i)
        

        design_summary = pd.DataFrame.from_dict(design_summary)

        design_summary_data = []
        design_summary_data.append(design_summary.columns.tolist())
        for i in design_summary.values.tolist():
            design_summary_data.append(i)

        losses_table = pd.DataFrame.from_dict(losses_table)

        losses_table_data = []
        losses_table_data.append(losses_table.columns.tolist())
        for i in losses_table.values.tolist():
            losses_table_data.append(i)


        bol_design_summary = pd.DataFrame.from_dict(bol_design_summary)

        bol_design_summary_data = []
        bol_design_summary_data.append(bol_design_summary.columns.tolist())
        for i in bol_design_summary.values.tolist():
            bol_design_summary_data.append(i)


        aug_energy_table = pd.DataFrame.from_dict(aug_energy_table)

        aug_energy_data = []
        aug_energy_data.append(aug_energy_table.columns.tolist())
        for i in aug_energy_table.values.tolist():
            aug_energy_data.append(i)


        power_energy_rte_table = pd.DataFrame.from_dict(power_energy_rte_table)

        power_energy_rte_data = []
        power_energy_rte_data.append(power_energy_rte_table.columns.tolist())
        for i in power_energy_rte_table.values.tolist():
            power_energy_rte_data.append(i)

        
        # Add content to Technical Proposal
        # Add title
        title_text = str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW/"+ str('{:,.2f}'.format(power_req*duration)) +"MWh Battery Energy Storage System"
        
        title_paragraph_style = ParagraphStyle("title", fontSize = 14, fontName = "Helvetica-Bold", leading = 15)
        section_paragraph_style = ParagraphStyle("section", fontSize = 12, fontName = "Helvetica-Bold")

        # Define styles

        def table_styles(table): 
            table_style = [ ('BACKGROUND', (0, 0), (-1, 0), prevalon_purple), # Header Background
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white), # Header Text Color
                            ('ALIGN', (0, 0), (-1, 0), 'CENTER'), # Allign Header Text Center
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), # Header Text Bold
                            ("FONTSIZE", (0, 0), (-1, 0), 8),  # Header Font Size
                            ('BOTTOMPADDING', (0, 0), (-1, 0), 3),  # Header Bottom Padding
                            
                            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'), # Table Font
                            ("FONTSIZE", (0, 1), (-1, -1), 8),   # Table Font Size
                            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black), # Table Text Color
                            ('ALIGN', (1, 1), (-1, -1), 'LEFT'), # Allign Table Text Center
                        
                            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), # Table Text Color
                            ('BOX', (0, 0), (-1, -1), 1, colors.black),
                            ('WORDWRAP', (0, 0), (-1, -1)), 
                            ]
            
            # Set different background colors for odd and even rows
            for i in range(1, len(table)):
                if i % 2 == 0:
                    table_style.append(("BACKGROUND", (0, i), (-1, i), prevalon_lavendar))  # Light blue background color for even rows
                else:
                    table_style.append(("BACKGROUND", (0, i), (-1, i), colors.white))  # Light cyan background color for odd rows
            
            # Set BOX for columns
            for i in range(len(table[0])):
                table_style.append(("BOX", (i, 0), (i, -1), 0.1, colors.black))  # Light cyan background color for odd rows
            
            return table_style

        title_paragraph = Paragraph(title_text, title_paragraph_style)

        content.append(title_paragraph)

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("1. Bill of Materials", section_paragraph_style))

        content.append(Paragraph("The table below describes the hardware included within Prevalon’s scope at the beginning of life:", style_normal))

        content.append(Paragraph("<br/><br/>", style_normal))
        
        table = Table(bill_of_materials_data, colWidths=[160, 330, 60], rowHeights=[20, 40, 60, 20, 30])
        table_style = table_styles(bill_of_materials_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("2. Design Summary", section_paragraph_style))

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("The system requirements and BOL performance for the " + str('{:,.2f}'.format(power_req)) + "MW/"+ \
                                str('{:,.2f}'.format(power_req*duration)) +"MWh BESS "\
                                "are summarized in the tables below. This follows the planned augmentation schedule.", style_normal))

        content.append(Paragraph("<br/><br/>", style_normal))

        table = Table(design_summary_data)
        table_style = table_styles(design_summary_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(PageBreak())

        content.append(Paragraph("Following losses to the Point of Measurement (POM) are considered in the BESS design \n \n", style_normal))

        table = Table(losses_table_data)
        table_style = table_styles(losses_table_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(Paragraph("*Losses outside of Prevalon's Scope. To be confirmed by the Buyer", style_normal))

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph(str('{:,.2f}'.format(power_req)) + "MW/"+ \
                                str('{:,.2f}'.format(power_req*duration)) +"MWh Proposed BOL Solution", section_paragraph_style))
        
        content.append(Paragraph("<br/><br/>", style_normal))
        
        table = Table(bol_design_summary_data)
        table_style = table_styles(bol_design_summary_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("3. System Augmentation Plan", section_paragraph_style))

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("To maintain the discharge energy delivered at the POM throughout the " \
                                + str('{:,.0f}'.format(project_life)) + "-year non-degrading energy period, \n" \
                                "Prevalon recommends augmenting the BESS by periodically installing additional battery storage in parallel with the original system. \
                                This results in a more attractive CAPEX. <br/><br/>" \
                                "Planned augmentation also allows Buyer to take advantage of expected future battery performance improvements and price reductions. \
                                It also provides the additional flexibility of being able to size the system based on actual usage in case it differs from the original \
                                plan.", style_normal))

        
        content.append(Paragraph("<br/><br/>", style_normal))

        table = Table(aug_energy_data)
        table_style = table_styles(aug_energy_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(PageBreak())
        
        content.append(Paragraph("4. BESS Annual Energy Capacity", section_paragraph_style))

        content.append(Paragraph("<br/><br/> The curve below shows AC Usable Energy including auxiliary consumption at POM throughout \
                                the "  + str('{:,.0f}'.format(project_life)) + "-year Project Life.", style_normal))

        # Add image to PDF
        # content.append(PlatypusImage(image_path, width=600, height=320))

        content.append(Paragraph("<br/><br/>", style_normal))
        content.append(Paragraph("5. Estimated BESS Annual Performance", section_paragraph_style))
        content.append(Paragraph("<br/><br/>", style_normal))

        table = Table(power_energy_rte_data)
        table_style = table_styles(power_energy_rte_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)
        
        doc.build(content, header, header)
        # Return the URL for the download link
        return pdf_file

    if n_clicks:
        # Generate PDF
        pdf_file = f'/download/{create_pdf_with_header_footer(proj_location, proj_name, power_req, duration, project_life, bill_of_materials, design_summary, losses_table, \
                                  bol_design_summary, aug_energy_table, power_energy_rte_table)}'
        n_clicks = 0
    else:
        # If button is not clicked, do nothing
        pdf_file = ''


    return pdf_file, n_clicks


@app.server.route('/download/<path:path>')
def serve_static(path):
    return send_file(path, as_attachment=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port = 2400)