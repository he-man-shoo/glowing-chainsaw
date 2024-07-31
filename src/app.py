import dash
from dash.dependencies import Input, Output
from dash import dcc
from dash import html
import pandas as pd
from scipy import interpolate
import math
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from flask import send_file
from reportlab.lib.pagesizes import letter, A1, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.utils import ImageReader
from reportlab.lib import colors
import PIL.Image
from reportlab.platypus import Image as PlatypusImage
import plotly.graph_objects as go
import dash_auth
from flask import Flask
from dash.exceptions import PreventUpdate

from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import *
from datetime import date



server = Flask(__name__)


# Keep this out of source code repository - save in a file or a database
VALID_USERNAME_PASSWORD_PAIRS = {
    'greek': 'spartans',
    'irish':'whiskey',
    'rocky':'mountains',
    'dim':'sum',
    'pav':'bhaji',
}


def calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations, flat_guarantee):
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

    
        if i == 0: minimized_cost = cost

        if cost <= minimized_cost and actual_number_of_pcs >= min_number_of_Inverters_required: 
            minimized_cost = cost
            optimized_number_of_pcs = actual_number_of_pcs
            optimized_number_of_stacks = actual_number_of_stacks
            optimized_number_of_containers = actual_number_of_containers

    # print(optimized_number_of_pcs, optimized_number_of_stacks, optimized_number_of_containers, minimized_cost)

    for i in range (len(stacks_config)):
        actual_number_of_pcs = min_number_of_Inverters_required + i - 1

        for j in range (len(stacks_config)):
            actual_number_of_stacks = actual_number_of_pcs * stacks_config[j]
            actual_number_of_containers = actual_number_of_pcs*container_config[j]
            cost = actual_number_of_pcs*cost_pcs + actual_number_of_stacks*batt_nameplate*cost_stack + actual_number_of_containers*cost_container

            if cost <= minimized_cost and actual_number_of_stacks >= min_number_of_stacks: 
                minimized_cost = cost
                optimized_number_of_pcs = actual_number_of_pcs
                optimized_number_of_stacks = actual_number_of_stacks
                optimized_number_of_containers = actual_number_of_containers
    
    # print(optimized_number_of_pcs, optimized_number_of_stacks, optimized_number_of_containers, minimized_cost)


    bol_config = pd.DataFrame({"Parameter" : ["Number of Strings | "+str(math.ceil(batt_nameplate)) + " kWh", "Number of "+ str(battery_model) + " Containers", "Number of PCS | " + str(PCS_model)], 
                               "Quantities (#)" : [optimized_number_of_stacks, optimized_number_of_containers, optimized_number_of_pcs]}) 


    ## Power - Energy Table
    power_energy_table = pd.DataFrame(optimized_number_of_stacks*batt_usable_ac*get_deg_curve(battery_model,number_cycles,duration,r_SOC)["Degradation Curve"])
    power_energy_table = power_energy_table.rename(columns={"Degradation Curve": 'Net Energy @ BOL at '+ str(point_of_measurement)+ ' (kWh)'})
    power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'] = power_energy_table['Net Energy @ BOL at '+ str(point_of_measurement)+ ' (kWh)']

    i = 0

    aug_energy_table = pd.DataFrame({})

    aug_energy_start_of_year = [None]*project_life

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

            aug_energy_start_of_year[year_of_augmentation-1] = (power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][year_of_augmentation-1] + augmentation_energy_required)*0.001 

            aug_energy_table.loc[i, "Augmentation Number"] = i+1
            aug_energy_table.loc[i, "Augmentation Year"] = year_of_augmentation
            aug_energy_table.loc[i, "Augmentation Nameplate Energy (kWh)"] = augmentation_energy_nameplate
            

            i = i + 1
        
        aug_energy_table["Augmentation Nameplate Energy (kWh)"] = aug_energy_table["Augmentation Nameplate Energy (kWh)"].apply(lambda x:'{:,.0f}'.format(x))

    power_energy_rte_table = pd.DataFrame({})

    power_energy_rte_table["End of Year"] = power_energy_table.index

    power_energy_rte_table["Usable AC Power at POM (MW)"] = '{:,.2f}'.format(power_req)

    if flat_guarantee == 'No':
        power_energy_rte_table["Usable AC Energy at POM (MWh)"] = power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)']*0.001
    else:
        power_energy_rte_table["Usable AC Energy at POM (MWh)"] = [energy_req]*len(power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'])
    
    power_energy_rte_table["Usable AC Energy at POM (MWh)"] = power_energy_rte_table["Usable AC Energy at POM (MWh)"].apply(lambda x:'{:,.2f}'.format(x))

    power_energy_rte_table["AC RTE including Aux at POM (%)"] = (get_DC_RTE(battery_model, duration).loc[:, str(battery_model) + " | " + str(duration)]*one_way_eff*one_way_eff*(1-aux_energy_percentage)*(1-aux_energy_percentage)-rte_margin)*100
    power_energy_rte_table["AC RTE including Aux at POM (%)"] = power_energy_rte_table["AC RTE including Aux at POM (%)"].apply(lambda x:'{:,.2f}%'.format(x))

    power_energy_rte_table = power_energy_rte_table.loc[:project_life, :]
    

    bill_of_materials = pd.DataFrame({})

    if RMU_Required == "IEC":
        pcs_string ="Power Conversion System (PCS) stations \n" \
                     "(includes Inverter, \n Medium Voltage (MV) Transformer \n" \
                      " and Ring Main Unit (RMU))"
        
        pcs_description = "MVA Inverter, mineral oil-filled transformer and a RMU"

    else:
        pcs_string ="Power Conversion System (PCS) stations \n" \
                "(includes Inverter and \n Medium Voltage (MV) Transformer)"
        
        pcs_description = "MVA Inverter and mineral oil-filled transformer"

    bill_of_materials["Component"] = "LFP Liquid Cooled \nBattery Enclosures", \
                                     pcs_string, \
                                     "EMS / SCADA", \
                                     "Master Fire Panel"

    bill_of_materials["Description"] = "Standard-sized ISO 20’ NEMA 3R enclosure with battery modules pre-installed, featuring: \n" \
                                        " 1) Up to " + '{:,.2f}'.format(max_racks_per_container*batt_nameplate*0.001) + "MWh DC Nameplate Energy per enclosure.  \n" \
                                        " 2) Dimensions: 20’ (L) x 9.5’ (H) x 8’ (W) or 6,058mm (L) x 2,896mm (H) x 2,438mm (W)", \
                                        "1) Integrated skid containing "+ '{:,.0f}'.format(PCS_kVA*0.001) + pcs_description + " \n" \
                                        "2) AC Output Power: " + '{:,.0f}'.format(PCS_kVA_at_max_site_temp) + "kVA @ "+ '{:,.0f}'.format(max_site_temp) +" deg C  \n" \
                                        "3) " + '{:,.0f}'.format(PCS_kVA) + "kVA " +'{:,.2f}'.format(PCS_AC_Voltage*0.001) + "kV/34.5kV mineral oil (PCB free) filled MV Transformer\n" \
                                        "4) Dimensions: 20’ (L) x 9.5’ (H) x 8’ (W) or 6,058mm (L) x 2,896mm (H) x 2,438mm (W)", \
                                        "Energy Management System with SCADA interface for BESS Dispatch and Control", \
                                        "Environmentally controlled NEMA 3R enclosure housing \n" \
                                        "master fire panel with battery backup"
    
    bill_of_materials["Quantity"] = optimized_number_of_containers, optimized_number_of_pcs, "Included", "Included"

    design_summary = pd.DataFrame({})

    design_summary["Parameter"] = "Power Required at Point of Measurement (POM) in kW AC", \
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
                                    "BESS Peak Aux Power (kW)\n(included in Total BESS AC Power Required at POM)", \
                                    "Aux Energy during discharge (kWh) @ " +str(max_site_temp) + " deg C\n(included in Total BESS BOL AC Usable Energy Required at POM)", \
                                    "BESS BOL AC Usable Energy net of Aux Energy at POM (kWh AC)"
    
    bol_design_summary["Value"] = '{:,.0f}'.format(optimized_number_of_containers), '{:,.0f}'.format(optimized_number_of_pcs), '{:,.2f}'.format(aux_power*1000), \
                                '{:,.2f}'.format(aux_energy_per_stack*optimized_number_of_stacks) , '{:,.2f}'.format((float(power_energy_rte_table["Usable AC Energy at POM (MWh)"][0].replace(',', ''))*1000))


#--------------------------------------------------- Cost Memo

    number_of_strings_per_PCS = optimized_number_of_stacks/optimized_number_of_pcs

    i = stacks_config.index(int(number_of_strings_per_PCS))

    container_config_8_strings =  [1, 0, 0, 2, 0, 0, 2, 1, 0, 0, 0, 0, 0, 0, 0]
    container_config_10_strings = [0, 1, 0, 0, 2, 0, 1, 2, 3, 2, 1, 0, 4, 2, 0]
    container_config_12_strings = [0, 0, 1, 0, 0, 2, 0, 0, 0, 1, 2, 3, 0, 2, 4]

                                        

    cost_memo_table = pd.DataFrame({})
    cost_memo_table["Parameter"] = "Project Location", "Project Name", "Required Power (MW)", \
                                      "Required Energy (MWh)", "Nameplate Energy (kWh)", "AC Usable Energy at POM (kWh)",\
                                        "Qty Strings", "Qty Containers (12 Strings)", "Qty Containers (10 Strings)", \
                                            "Qty Containers (8 Strings)", "Total Qty Containers", "Qty PCS", "PCS Model"

    cost_memo_table["Value"] = proj_location, proj_name, '{:,.2f}'.format(power_req), '{:,.2f}'.format(energy_req), \
                               '{:,.2f}'.format(batt_nameplate*optimized_number_of_stacks), '{:,.2f}'.format((float(power_energy_rte_table["Usable AC Energy at POM (MWh)"][0].replace(',', ''))*1000)), \
                                optimized_number_of_stacks, container_config_12_strings[i]*optimized_number_of_pcs, container_config_10_strings[i]*optimized_number_of_pcs, \
                                container_config_8_strings[i]*optimized_number_of_pcs, optimized_number_of_containers, optimized_number_of_pcs, PCS_model
    

    x_param = power_energy_table[:project_life+1].index.values.tolist()
    y_param = power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][:project_life+1]*0.001
    fig = go.Figure()

    fig.add_trace(go.Scatter(x = x_param, y = y_param, name= "Net Energy @ POM", mode = "markers", marker=dict(symbol = "circle", color='purple', size = 10)))
    
    fig.add_trace(go.Scatter(x = x_param, y = aug_energy_start_of_year, name= "Net Energy @ POM 1", mode = "markers", marker=dict(symbol = "circle", color='purple', size = 10), showlegend=False))

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
    
    plot_title = str(proj_location) + " | " + str(proj_name) + " | " + '{:,.2f}'.format(energy_req) + " MWh Energy Capacity @ "+ str(point_of_measurement) + " | " + str(number_cycles) + " cycles/year"
    y_axis_range = [str(power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][project_life]*0.001 - power_energy_table['Total Net Energy at '+ str(point_of_measurement)+ ' (kWh)'][project_life]*0.001/10), str(batt_nameplate*optimized_number_of_stacks*0.001)]

    block_type = int(optimized_number_of_containers/optimized_number_of_pcs)

    PCS_kVA_string = '{:,.0f}'.format(PCS_kVA_at_max_site_temp) + "kVA @ "+ '{:,.0f}'.format(max_site_temp) +" deg C"

    BESS_Rating = max_racks_per_container*batt_nameplate

    return fig, bol_config, aug_energy_table, power_energy_rte_table, bill_of_materials, design_summary, losses_table, \
        bol_design_summary, plot_title, y_axis_range, months_to_COD, block_type, cost_memo_table, PCS_kVA_string, BESS_Rating




# Initialize the Dash app
app = dash.Dash(server=server, external_stylesheets=["https://codepen.io/chriddyp/pen/bWLwgP.css"])
server = app.server

auth = dash_auth.BasicAuth(
    app,
    VALID_USERNAME_PASSWORD_PAIRS
)

input_label_style = {'font-size': '0.95em', 'font-weight': 'bolder'}

button_style = {'border-radius': '4px', 'font-size': '1.25rem', 'border': '1px solid navy','background-color': 'dodgerblue', 'color': 'white'}

# Define the layout of the website
app.layout = html.Div([

    html.H1(children='Level 1 Sizing Tool', style={'textAlign': 'center', 'font-family':'Helvetica', 'font-size': '3.5em'}),
                html.Br(),
    
    
    html.Div([
        
        html.Div([html.H5("Project Location", style = input_label_style),
                  dcc.Input(id='inp_projloct', type='text', value="Lake Mary"),
                  ], style = {"textAlign":"center", 'font-size': '1em'}, className='two columns'),
        
        html.Div([html.H5("Project Name", style = input_label_style),
                  dcc.Input(id='inp_projnm', type='text', value="Pilot Project"),
                  ],style = {"textAlign":"center"} ,className='two columns'),
        
        html.Div([html.H5('Project Size (MW)', style = input_label_style),
                  dcc.Input(id='inp_projsize', type='number', value=100, min=5),
                  ], style = {"textAlign":"center"}, className='two columns'),
        
        html.Div([html.H5(children = 'Duration (hrs):', style = input_label_style),
            dcc.Dropdown(id='ddn_duration', options=[
                {'label': '2', 'value': 2},
                {'label': '3', 'value': 3},
                {'label': '4', 'value': 4},
                {'label': '5', 'value': 5},
                {'label': '6', 'value': 6},
                {'label': '8', 'value': 8},
                ], value= 4),
        ], style = {"textAlign":"center"}, className='two columns'),

        html.Div([
            html.H5(children = 'Number of Cycles per Year', style = input_label_style),
            dcc.Dropdown(id='ddn_cyc', options=[
                        {'label': '180', 'value': 180},
                        {'label': '365', 'value': 365},
                        {'label': '548', 'value': 548},
                        {'label': '730', 'value': 730},
                        ], value= 365),
        ], style = {"textAlign":"center", 'font-size': '1em'}, className='two columns'),

        html.Div([
            html.H5('Point of Measurement', style = input_label_style),
            dcc.Dropdown(id='ddn_pom', options=[
                {'label': 'AC Terminals of Inverter', 'value': 'AC Terminals of Inverter'},
                {'label': 'High Side of Medium Voltage Transformer', 'value': 'High Side of Medium Voltage Transformer'},
                {'label': 'Medium Voltage POM', 'value': 'Medium Voltage POM'},
                {'label': 'High Side of HV Transformer', 'value': 'High Side of HV Transformer'},
                {'label': 'High Voltage POM', 'value': 'High Voltage POM'},
                ], value= 'High Side of HV Transformer', style = {'font-size': '0.94em'}),
        ], style = {"textAlign":"center"}, className='two columns'),

    ], className='row'),

html.Br(),


    html.Div([
          
        html.Div([html.H5('Compliance Code', style = input_label_style),
            dcc.Dropdown(id='ddn_rmu', options=[
                        {'label': 'UL', 'value': 'UL'},
                        {'label': 'IEC', 'value': 'IEC'}
                        ], value= 'UL'),
                        ],style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5('Power Factor', style = input_label_style),
                    dcc.Dropdown(id='ddn_pf', options=[
                                {'label': '0.90', 'value': 0.90},
                                {'label': '0.95', 'value': 0.95}
                                ], value= 0.95),]
                ,style = {"textAlign":"center"}, className='two columns'),


        html.Div([html.H5('Max Site Temperature (deg C)', style = input_label_style),
                dcc.Input(id='inp_temp', type='number', value=40, max=50),
                ], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5('BOL Oversize (until End of Year)', style = input_label_style),
                dcc.Input(id='inp_overize', type='number', value=3, min=0),], style = {"textAlign":"center"}, className='two columns'),

        html.Div([html.H5("Project Life (years)", style = input_label_style),
                  dcc.Input(id='inp_projlife', type='number', value=20, min=3, max=20),
                  ], style = {"textAlign":"center"},className='two columns'),

        html.Div([html.H5("Number of Augmentations", style = input_label_style),
                  dcc.Input(id='inp_aug', type='number', value=4, min=0),]
                 ,style = {"textAlign":"center"} ,className='two columns'),


    ], className='row'),

    html.Br(),

    html.Div([html.H5("")], className='three columns'),

            html.Div([html.H5("Technical Proposal to include Flat Energy Guarantees", style = input_label_style),
                  dcc.RadioItems(id='inp_flt_gua', options = ['Yes', 'No'], value = 'No', inline=True)]
                 ,style = {"textAlign":"center"} ,className='five columns'),

    
    html.Br(),

    html.Br(),

    html.Br(),

    html.Div([
        
        html.Div([html.H5("")], className='five columns'),
        
        html.Button('Run Sizing', id='generate_sizing', className='two columns', style = button_style), 

    ]),
    
    

    html.Br(),

    html.Br(),


    html.Div([
        html.Div([html.H5("")], className='one columns'),
        html.H2(children='Energy Plot', className='ten columns'),

    ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        dcc.Loading(dcc.Graph(id = "plot", style = {"height":"80vh"},  className='ten columns')),

    ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        html.H2(children='BOL Configuration Table', className='four columns'),
        html.H2(children='Augmentation Table', className='four columns'),       
                ], className='row'),

    html.Div([
        html.Div([html.H5("")], className='one columns'),
        dbc.Container([html.P(id = "bol_config"), 
                    ], className='three columns'),
        html.Div([html.H5("")], className='one columns'),        
        dbc.Container([html.P(id = "aug_energy_table"),
                    ], className='three columns'),
                ], className='row'),


html.Br(),

html.Div([
        html.Div([html.H5("")], className='three columns'),
        html.H2(children='Power Energy and RTE Table', className='four columns'),     
], className='row'), 

html.Div([
        html.Div([html.H5("")], className='three columns'),
        dbc.Container([html.P(id = "power_energy_rte_table"), 
                        ], className='five columns'),
            
                ],  className='row'),

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
]),

html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate Technical Proposal', id='generate-pdf-button', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download Technical Proposal', id='download-pdf', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate Cost Memo', id='generate_cost_memo', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download Cost Memo', id='download_cost_memo', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate GA', id='generate_GA', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download GA', id='download_GA', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

html.Div([
    html.Div([html.H5("")], className='three columns'),
    html.Button('Step 1 - Generate SLD', id='generate_SLD', style=button_style, className='three columns'),
    dcc.Loading(children = html.A('Step 2 - Download SLD', id='download_SLD', href='', \
                                  className='three columns', style= {"textAlign":"center", 'border-radius': '4px', \
                                                                     'border': '1px solid navy','background-color': 'rgb(127, 81, 185)',\
                                                                          'color': 'white', 'height': '38px', 'padding': '8px'}), type="circle")
        ]),

html.Br(),
html.Br(),
html.Br(),

])



# Define callback to update the output

@app.callback(
    Output('plot', 'figure'),
    Output('bol_config', 'children'),
    Output('aug_energy_table', 'children'),
    Output('power_energy_rte_table', 'children'),
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
                    cost_memo_table, PCS_kVA_string, BESS_Rating = calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations, flat_guarantee)
    
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

        fig_stored = fig

        bill_of_materials_stored = bill_of_materials.to_dict()

        design_summary_stored = design_summary.to_dict()

        losses_table_stored = losses_table.to_dict()

        bol_design_summary_stored = bol_design_summary.to_dict()

        aug_energy_table_stored = aug_energy_table.to_dict()

        power_energy_rte_table_stored = power_energy_rte_table.to_dict()

        cost_memo_table_stored = cost_memo_table.to_dict()

        n_clicks = 0
        return fig, bol_config, aug_energy_dict, power_energy_rte_dict, fig_stored, bill_of_materials_stored, design_summary_stored, \
    losses_table_stored, bol_design_summary_stored, aug_energy_table_stored, power_energy_rte_table_stored, plot_title, y_axis_range, months_to_COD, block_type, cost_memo_table_stored, PCS_kVA_string, BESS_Rating, n_clicks

    else:
        raise PreventUpdate


@app.callback(
Output('download-pdf', 'href'),
Output('generate-pdf-button', 'n_clicks'),
 [Input('generate-pdf-button', 'n_clicks'),
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

def update_pdf(n_clicks ,proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
                                    bol_design_summary, aug_energy_table, power_energy_rte_table, plot_title, y_axis_range, months_to_COD, block_type):
    
    def create_pdf_with_header_footer(proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
                                    bol_design_summary, aug_energy_table, power_energy_rte_table, plot_title, y_axis_range, months_to_COD, block_type):

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
        # print(fig['data'])

        fig = go.Figure(fig['data'])

        fig.update_layout(title={"text": plot_title, "x" : 0.5, "y" : 0.9},#,"y"：8.97，"x"：8.5，"anchor": "center","yanchor": "top"}, 
        
        xaxis=dict(showgrid=False, zeroline=True, showline=True, mirror= True, gridcolor='#bdbdbd', gridwidth=1, zerolinecolor='#969696', zerolinewidth=2, linecolor='#636363', linewidth=2, showticklabels=True, dtick = 1, range=["-0.5", str(project_life+0.5)]),
        yaxis=dict(showgrid=True, zeroline=True, showline=True, mirror=True, gridcolor='#bdbabd', gridwidth=1, zerolinecolor='#969696', zerolinewidth=2, linecolor='#636363', linewidth=2, showticklabels=True, range=y_axis_range),
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
    
        fig.write_image("plot.png", height = 650, width=1400)

        # Define header and footer function with image from URL
        def header(canvas, doc):
            
            canvas.saveState()
            img = PIL.Image.open('Prevalon Logo.jpg')
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
            canvas.drawString(25, 25+6, " %d" % page_num)

            canvas.restoreState()


        pdf_file = "Technical Proposal " + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"

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

        if len(aug_energy_table) == 0:
            aug_energy_data = []
        else:
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

        content.append(Paragraph("Note - BOL design accounts for " + months_to_COD + " of calendar degradation, an allowance for transportation, \
                                 installation, and commissioning. Should there be a need for additional time Prevalon reserves the right to make \
                                 changes to the BOL design and requisite commercial remedy.", style_normal))
        
        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("3. System Augmentation Plan", section_paragraph_style))

        content.append(Paragraph("<br/><br/>", style_normal))
        
        if len(aug_energy_data) == 0:
            content.append(Paragraph("Section NOT USED - Designed BESS has no Augmentations", style_normal))

            content.append(PageBreak())

        else:
            content.append(Paragraph("To maintain the discharge energy delivered at the POM throughout the " \
                                    + str('{:,.0f}'.format(project_life)) + "-year non-degrading energy period, \n" \
                                    "Prevalon recommends augmenting the BESS by periodically installing additional battery storage in parallel with the original system. \
                                    This results in a more attractive CAPEX. <br/><br/>" \
                                    "Planned augmentation also allows Buyer to take advantage of expected future battery performance improvements and price reductions. \
                                    It also provides the additional flexibility of being able to size the system based on actual usage in case it differs from the original \
                                    plan.", style_normal))

            
            content.append(Paragraph("<br/><br/>", style_normal))
            content.append(PageBreak())

            table = Table(aug_energy_data)
            table_style = table_styles(aug_energy_data)
            table.setStyle(TableStyle(table_style))
            content.append(table)

        content.append(Paragraph("<br/><br/>", style_normal))

        content.append(Paragraph("4. BESS Annual Energy Capacity", section_paragraph_style))

        content.append(Paragraph("<br/><br/> The curve below shows AC Usable Energy including auxiliary consumption at POM throughout \
                                the "  + str('{:,.0f}'.format(project_life)) + "-year Project Life.", style_normal))

        # Add image to PDF
        content.append(PlatypusImage('plot.png', width=600, height=320))

        content.append(Paragraph("<br/><br/>", style_normal))
        content.append(PageBreak())
        content.append(Paragraph("5. Estimated BESS Annual Performance", section_paragraph_style))
        content.append(Paragraph("<br/><br/>", style_normal))

        table = Table(power_energy_rte_data)
        table_style = table_styles(power_energy_rte_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(PageBreak())

        content.append(Paragraph("6. BESS AC Block Arrangement", section_paragraph_style))
        content.append(Paragraph("<br/><br/>", style_normal))

        # Add image to PDF
        content.append(PlatypusImage(str(block_type) + '.png', width=456, height=600))
        
        doc.build(content, header, header)
        # Return the URL for the download link
        return pdf_file

    if n_clicks:
        # Generate PDF
        pdf_file = '/download/{}'.format(create_pdf_with_header_footer(proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
                                  bol_design_summary, aug_energy_table, power_energy_rte_table, plot_title, y_axis_range, months_to_COD, block_type))
        n_clicks = 0
    else:
        # If button is not clicked, do nothing
        pdf_file = ''
    return pdf_file, n_clicks


@app.callback(
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
    
    def create_cost_memo(cost_memo_table, proj_location, proj_name, power_req, duration, aug_energy_table):

        # Define Colors 
        prevalon_lavendar = colors.Color(220/256,207/256,235/256)
        prevalon_purple = colors.Color(127/256,81/256,185/256)
        # Create a list to hold the contents of the PDF
        content = []

        # Define styles
        styles = getSampleStyleSheet()
        style_normal = styles["Normal"]

        # Define header and footer function with image from URL
        def header(canvas, doc):
            
            canvas.saveState()
            img = PIL.Image.open('Prevalon Logo.jpg')
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
            canvas.drawString(25, 25+6, " %d" % page_num)

            canvas.restoreState()


        cost_memo_pdf = "Cost Memo " + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"

        # Create a PDF document
        doc = SimpleDocTemplate(
            cost_memo_pdf,
            pagesize=letter,
        )


        cost_memo_table = pd.DataFrame.from_dict(cost_memo_table)

        cost_memo_table_data = []
        cost_memo_table_data.append(cost_memo_table.columns.tolist())
        for i in cost_memo_table.values.tolist():
            cost_memo_table_data.append(i)

        
        aug_energy_table = pd.DataFrame.from_dict(aug_energy_table)

        if len(aug_energy_table) == 0:
            aug_energy_data = []
        else:
            aug_energy_data = []
            aug_energy_data.append(aug_energy_table.columns.tolist())
            for i in aug_energy_table.values.tolist():
                aug_energy_data.append(i)

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
        
        table = Table(cost_memo_table_data)
        table_style = table_styles(cost_memo_table_data)
        table.setStyle(TableStyle(table_style))
        content.append(table)

        content.append(Paragraph("<br/><br/>", style_normal))


        content.append(Paragraph("System Augmentation Plan", section_paragraph_style))

        content.append(Paragraph("<br/><br/>", style_normal))
        
        if len(aug_energy_data) == 0:
            content.append(Paragraph("Section NOT USED - Designed BESS has no Augmentations", style_normal))

        else:
            table = Table(aug_energy_data)
            table_style = table_styles(aug_energy_data)
            table.setStyle(TableStyle(table_style))
            content.append(table)
    
        doc.build(content, header, header)
        # Return the URL for the download link
        return cost_memo_pdf

    if n_clicks:
        # Generate PDF
        cost_memo_pdf = '/download/{}'.format(create_cost_memo(cost_memo_table, proj_location, proj_name, power_req, \
                                                               duration, aug_energy_table))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        cost_memo_pdf = ''
    return cost_memo_pdf, n_clicks

@app.callback(
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
    
    def create_GA(proj_location, proj_name, power_req, duration, bol, PCS_kVA_string, BESS_Rating, aug):
        
        block_qty = int(bol['Value']['1'].replace(',', ''))
        block_type = int(bol['Value']['0'].replace(',', ''))/int(bol['Value']['1'].replace(',', ''))

        feeder_qty = math.ceil(block_qty/8)
        aux_xfrm_rating = int(math.ceil(float(bol['Value']['2'].replace(',', ''))*1.25/feeder_qty/100))*100

        total_BOL_energy = block_qty*block_type*BESS_Rating

        total_augmentation_energy = 0
        
        if aug:
            for i in aug['Augmentation Nameplate Energy (kWh)'].values():
                total_augmentation_energy = total_augmentation_energy + float(i.replace(',', ''))

        
        n_s_block_access_road = 10 # Access Road after "n" number of blocks
        
        container_length = 20*12
        container_width = 8*12

        pcs_length = 20*12
        pcs_width = 8*12

        container_clearance_minimum = 6
        container_clearance_long_end = 10*12

        pcs_clearance_short_end = 5*12
        pcs_clearance_long_end = 10*12

        access_road_width = 20*12

        

        def draw_arrow(c, x1, y1, x2, y2, arrow_size, orient):
            c.setDash()
            c.setLineWidth(0.4)

            if orient == 1:
                """
                Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
                arrow_size determines the size of the arrowhead.
                """

                # Draw the main line
                c.line(x1, y1, x2, y2)

                # Draw the first arrowhead
                angle1 = 45
                c.line(x1, y1, x1 + arrow_size, y1 + arrow_size/2)
                c.line(x1, y1, x1 + arrow_size, y1 - arrow_size/2)

                # Draw the second arrowhead
                c.line(x2, y2, x2 - arrow_size, y2 + arrow_size/2)
                c.line(x2, y2, x2 - arrow_size, y2 - arrow_size/2)

            if orient == 2:
                """
                Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
                arrow_size determines the size of the arrowhead.
                """

                # Draw the main line
                c.line(x1, y1, x2, y2)

                # Draw the first arrowhead
                c.line(x1, y1, x1 - arrow_size/2, y1 + arrow_size)
                c.line(x1, y1, x1 + arrow_size/2, y1 + arrow_size)

                # Draw the second arrowhead
                c.line(x2, y2, x2 - arrow_size/2, y2 - arrow_size)
                c.line(x2, y2, x2 + arrow_size/2, y2 - arrow_size)




            c.setDash(6, 3)
            c.setLineWidth(0.4)

        def draw_vertical_text(c, x, y, text):
            # Save the current state of the canvas
            c.saveState()
            
            # Move the origin to the position where the text will be centered
            c.translate(x, y)
            
            # Rotate the canvas by 90 degrees counterclockwise (270 degrees clockwise)
            c.rotate(90)
            
            # Draw the string centered at the new origin
            c.drawCentredString(0, 0, text)
            
            # Restore the canvas state to avoid affecting other drawings
            c.restoreState()


        def dim(value, scaling_factor, starter_string, end_string):
            return starter_string + '{:,.0f}'.format(value/scaling_factor//12) + "' " +  '{:,.0f}'.format(value/scaling_factor%12) + \
                '" (' +  '{:,.2f}'.format(value/scaling_factor/12/3.281) + " meters)" + end_string

        e_w_block_limit_array = []
        n_s_block_limit_array = []


        for i in range(block_qty,0,-1):
            e_w_block_limit_array.append(i)
            n_s_block_limit_array.append(math.ceil(block_qty/i))


        for i in range(block_qty):
            e_w_block_limit = e_w_block_limit_array[i]
            n_s_block_limit = n_s_block_limit_array[i]

            if block_type == 1:
                inner_block_length = (e_w_block_limit*2-math.floor(e_w_block_limit/2))*(container_length) + (e_w_block_limit*2-math.floor(e_w_block_limit/2)-1)*pcs_clearance_short_end + access_road_width/4
            
            if block_type == 2:
                inner_block_length = (e_w_block_limit*2)*(container_length) + (e_w_block_limit + (e_w_block_limit//2) + (e_w_block_limit%2 - 1))*pcs_clearance_short_end + (e_w_block_limit//2)*container_clearance_minimum + access_road_width/4
            
            if block_type == 3:
                inner_block_length = (e_w_block_limit*2 + math.ceil(e_w_block_limit/2))*(container_length) + (e_w_block_limit*2 - 1)*pcs_clearance_short_end + math.ceil(e_w_block_limit/2)*container_clearance_minimum + access_road_width/4
                
            if block_type == 4:
                inner_block_length = (e_w_block_limit + 2*e_w_block_limit)*(container_length) + (e_w_block_limit*2 - 1)*pcs_clearance_short_end + (e_w_block_limit)*container_clearance_minimum + access_road_width/4
            
            outer_block_length = inner_block_length + 2*access_road_width

            inner_block_width_partial = (n_s_block_limit % n_s_block_access_road)*(container_width*2 + container_clearance_minimum) + (n_s_block_limit % n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4
            inner_block_width_full = n_s_block_access_road*(container_width*2 + container_clearance_minimum) + (n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4

            if n_s_block_limit % n_s_block_access_road != 0:
                outer_block_width = n_s_block_limit//n_s_block_access_road*(inner_block_width_full  + access_road_width) + inner_block_width_partial + 2*access_road_width
                                    
            else:
                outer_block_width = n_s_block_limit//n_s_block_access_road*(inner_block_width_full) + 2*access_road_width

            scaling_factor_x = 1600/outer_block_length
            scaling_factor_y = 1200/outer_block_width

            scaling_factor = min(scaling_factor_x, scaling_factor_y)

            if i == 0:
                min_scaling_factor = scaling_factor
                min_e_w_block_limit = e_w_block_limit
                min_n_s_block_limit = n_s_block_limit

            elif scaling_factor >= min_scaling_factor:
                min_scaling_factor = scaling_factor
                min_e_w_block_limit = e_w_block_limit
                min_n_s_block_limit = n_s_block_limit
            
            
            i = i + 1
                
        scaling_factor = min_scaling_factor
        e_w_block_limit = min_e_w_block_limit
        n_s_block_limit = min_n_s_block_limit


        def scaled_parameter(parameter, scaling_factor):
            return parameter*scaling_factor


        container_length = scaled_parameter(container_length, scaling_factor)
        container_width = scaled_parameter(container_width, scaling_factor)

        container_clearance_minimum = scaled_parameter(container_clearance_minimum, scaling_factor)
        container_clearance_long_end = scaled_parameter(container_clearance_long_end, scaling_factor)

        pcs_length = scaled_parameter(pcs_length, scaling_factor)
        pcs_width = scaled_parameter(pcs_width, scaling_factor)

        pcs_clearance_short_end = scaled_parameter(pcs_clearance_short_end, scaling_factor)
        pcs_clearance_long_end = scaled_parameter(pcs_clearance_long_end, scaling_factor)

        access_road_width = scaled_parameter(access_road_width, scaling_factor)

        def add_block(c, block_type, x, y_block_mid, e_w_block_count, block_count, container_count):
            # Draw a rectangle
            c.setStrokeColorRGB(0, 0, 0)  # Set stroke color to black
            c.setFont("Helvetica", 20*scaling_factor)


            if e_w_block_count % 2 == 0:

                y = y_block_mid + container_clearance_minimum/2

                if block_type == 1:
                    # Container
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count)))

                    x = x + container_length + pcs_clearance_short_end
                    y = y_block_mid - pcs_width/2

                    # PCS
                    c.rect(x, y, pcs_length, pcs_width, fill=0)
                    c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                    x = x + pcs_length + pcs_clearance_short_end

                if block_type == 2:
                    x = x + container_length + container_clearance_minimum
                    # Container 1
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count)))

                    # Container 2
                    y = y - container_clearance_minimum - container_width  
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count+1)))

                    x = x + container_length + pcs_clearance_short_end
                    y = y_block_mid - pcs_width/2

                    # PCS
                    c.rect(x, y, pcs_length, pcs_width, fill=0)
                    c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                    x = x + pcs_length + pcs_clearance_short_end

                if block_type == 3:
            
                    # Container 1
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count)))

                    x = x + container_length + pcs_clearance_short_end
                    y = y_block_mid - pcs_width/2

                    # PCS
                    c.rect(x, y, pcs_length, pcs_width, fill=0)
                    c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                    x = x + pcs_length + pcs_clearance_short_end
                    y = y_block_mid + container_clearance_minimum/2

                    # Container 2
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 1)))
                    
                    y = y_block_mid - container_width - container_clearance_minimum/2
                    
                    # Container 3
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 2)))

                    x = x + container_length + pcs_clearance_short_end

                
                if block_type == 4:
                    
                    # PCS
                    y = y_block_mid - pcs_width/2
                    c.rect(x, y, pcs_length, pcs_width, fill=0)
                    c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                    x = x + pcs_length + pcs_clearance_short_end

                    y = y_block_mid - container_width - container_clearance_minimum/2

                    # Container 1 and 3
                    for i in range(2):
                        c.rect(x, y, container_length, container_width, fill=0)
                        c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + i)))
                        i = i + 1
                        y = y_block_mid + container_clearance_minimum/2

                    x = x + container_length + container_clearance_minimum

                    # Container 2 and 4
                    for i in range(2):
                        c.rect(x, y, container_length, container_width, fill=0)
                        c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 2 + i)))
                        i = i + 1
                        y = y_block_mid - container_width - container_clearance_minimum/2

                    x = x + container_length + pcs_clearance_short_end

            
                return x

            else:
                
                # PCS
                y = y_block_mid - pcs_width/2

                c.rect(x, y, pcs_length, pcs_width, fill=0)
                c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                x = x + pcs_length + pcs_clearance_short_end
                y = y_block_mid - container_width - container_clearance_minimum/2

                # Container
                c.rect(x, y, container_length, container_width, fill=0)
                c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count)))

                if block_type > 1:
                    # Container
                    y = y_block_mid + container_clearance_minimum/2
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 1)))

                    if block_type > 2:
                        # Container
                        y = y_block_mid - container_width - container_clearance_minimum/2
                        x = x + container_length + container_clearance_minimum
                        
                        c.rect(x, y, container_length, container_width, fill=0)
                        c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 2)))
                        
                        if block_type > 3:
                            # Container
                            y = y_block_mid + container_clearance_minimum/2

                            c.rect(x, y, container_length, container_width, fill=0)
                            c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 3)))
                            
                            x = x + container_length + pcs_clearance_short_end

                y = y_block_mid
                
                return x

        def add_inner_block (c, x, y, e_w_block_limit, n_s_block_count, block_type):

            x = x - access_road_width/8
            y = y - access_road_width/8

            if block_type == 1:
                inner_block_length = (e_w_block_limit*2-math.floor(e_w_block_limit/2))*(container_length) + (e_w_block_limit*2-math.floor(e_w_block_limit/2)-1)*pcs_clearance_short_end + access_road_width/4
            
            if block_type == 2:
                inner_block_length = (e_w_block_limit*2)*(container_length) + (e_w_block_limit + (e_w_block_limit//2) + (e_w_block_limit%2 - 1))*pcs_clearance_short_end + (e_w_block_limit//2)*container_clearance_minimum + access_road_width/4
            
            if block_type == 3:
                inner_block_length = (e_w_block_limit*2 + math.ceil(e_w_block_limit/2))*(container_length) + (e_w_block_limit*2 - 1)*pcs_clearance_short_end + math.ceil(e_w_block_limit/2)*container_clearance_minimum + access_road_width/4
                
            if block_type == 4:
                inner_block_length = (e_w_block_limit + 2*e_w_block_limit)*(container_length) + (e_w_block_limit*2 - 1)*pcs_clearance_short_end + (e_w_block_limit)*container_clearance_minimum + access_road_width/4
            
            if n_s_block_count % n_s_block_access_road != 0 :
                inner_block_width = (n_s_block_count % n_s_block_access_road)*(container_width*2 + container_clearance_minimum) + (n_s_block_count % n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4
            else:
                inner_block_width = n_s_block_access_road*(container_width*2 + container_clearance_minimum) + (n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4

            c.roundRect(x, y, inner_block_length, inner_block_width, access_road_width/8)  # (x, y, width, height)

            # c.rect(x, y- access_road_width, container_length, access_road_width, fill=0)    
            
            return inner_block_length, inner_block_width

        def border(c, area, block_qty, block_type):
            # Draw a rectangle
            c.setStrokeColorRGB(0, 0, 0)  # Set stroke color to black
            c.rect(20*mm, 20*mm, (841-40)*mm, (594-40)*mm, fill=0)  # (x, y, width, height)

            x_top_corner = (841-20)*mm
            y_top_corner = (594-20)*mm

            x_bot_corner = (841-20)*mm
            y_bot_corner = (20)*mm

            c.setFont("Helvetica", 14)

            c.rect(x_top_corner- 360, y_top_corner - 40, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_top_corner - 180, y_top_corner - 25, "NOTES")

            c.setFont("Helvetica", 8)
            x_notes = x_top_corner - 350
            y_notes = y_top_corner - 60

            c.drawString(x_notes, y_notes,      " 1. LAYOUT OF BESS YARD AND EQUIPMENT ARE ONLY REPRESENTATIVE. FINAL YARD")
            c.drawString(x_notes, y_notes - 10, "     LAYOUT SHALL BE DESIGNED BY A LICENSED ENGINEER TO ALL APPLICABLE")
            c.drawString(x_notes, y_notes - 20, "     CODES BASED ON ACTUAL SITE CONDITIONS.")

            c.drawString(x_notes, y_notes - 40, " 2. THIS DOCUMENT ONLY SHOWS EQUIPMENT IN PREVALON'S SCOPE AT BOL. BUYER")
            c.drawString(x_notes, y_notes - 50, "     TO ALLOCATE ADDITIONAL SPACE AS REQUIRED FOR EQUIPMENT INCLUDING BUT")
            c.drawString(x_notes, y_notes - 60, "     NOT LIMITED TO AUX TRANSFORMERS AND PANELS, AUGMENTATION EQUIPMENT")
            c.drawString(x_notes, y_notes - 70, "     REQUIRED OVER THE LIFE OF PROJECT, MV SWITCHGEAR, SUBSTATION YARD ETC.")
            
            c.drawString(x_notes, y_notes - 90, " 3. ALL DIMENSIONS ON THIS DRAWING ARE NOMINAL. CONTRACTOR SHALL VERIFY")
            c.drawString(x_notes, y_notes - 100, "     ALL DIMENSIONS AND CONDITIONS AT THE JOB SITE PRIOR TO COMMENCING WORK.")
            c.drawString(x_notes, y_notes - 110, "     DIMENSIONS NOT SHOWN ARE TO BE DETERMINED IN FIELD.")

            c.drawString(x_notes, y_notes - 130, " 4. EQUIPMENT RATING SHOWN ARE NAMEPLATE VALUES.")

            c.drawString(x_notes, y_notes - 150, " 5. APPROXIMATE AREA OF WORK REQUIRED FOR BOL EQUIPMENT: " + '{:,.2f}'.format(area) + " SQ FT")
            c.drawString(x_notes, y_notes - 160, "      ("+ '{:,.2f}'.format(area/43560) + " ACRES) OR " + '{:,.2f}'.format(area/10.764) + " SQ MTS ("+ '{:,.2f}'.format(area/107600) + " HECTARES)")

            augmentation_area = area/total_BOL_energy*total_augmentation_energy

            c.drawString(x_notes, y_notes - 180, " 6. APPROXIMATE AREA REQUIRED FOR AUGMENTATION EQUIPMENT (NOT SHOWN IN")
            c.drawString(x_notes, y_notes - 190, "      THIS DRAWING): " + '{:,.2f}'.format(augmentation_area) + " SQ FT ("+ '{:,.2f}'.format(augmentation_area/43560) + " ACRES) OR " + '{:,.2f}'.format(augmentation_area/10.764) + " SQ MTS ("+ '{:,.2f}'.format(augmentation_area/107600) + " HECTARES)")

            c.rect(x_top_corner- 360, y_notes - 200, 360, 260, fill=0)

            c.setFont("Helvetica", 9)

            c.rect(x_bot_corner - 360, y_bot_corner, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 270, y_bot_corner + 15, "REASON FOR CONTROL - NLR")
            c.drawCentredString(x_bot_corner - 90, y_bot_corner + 15, "DRAWING RELEASE DATE: " + str(date.today()))
            
            c.rect(x_bot_corner - 360, y_bot_corner + 40, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 270, y_bot_corner + 40 + 15, "SECURITY LEVEL - SL2")
            c.drawCentredString(x_bot_corner - 90, y_bot_corner + 40 + 15, "EXPORT CLASSIFICATION - EAR99")

            c.rect(x_bot_corner - 360, y_bot_corner, 180, 80, fill=0)  # (x, y, width, height)


            c.rect(x_bot_corner - 360, y_bot_corner+80, 360, 160, fill=0)  # (x, y, width, height)

            c.setFont("Helvetica", 10)
            c.drawCentredString(x_bot_corner - 170, y_bot_corner + 225, "EXPORT ADMINISTRATION REGULATIONS WARNING")
            
            c.setFont("Helvetica", 8)
            c.drawString(x_bot_corner - 350, y_bot_corner + 210, "THIS DOCUMENT CONTAINS TECHNICAL DATA WHICH IF EXPORTED FROM THE UNITED")
            c.drawString(x_bot_corner - 350, y_bot_corner + 200, "STATES MUST BE EXPORTED IN ACCORDANCE WITH THE EXPORT ADMINISTRATION ")
            c.drawString(x_bot_corner - 350, y_bot_corner + 190, "REGULATIONS. DIVERSION CONTRARY TO U.S. LAW IS PROHIBITED.")

            c.setFont("Helvetica", 10)
            c.drawCentredString(x_bot_corner - 170, y_bot_corner + 155, "CONFIDENTIAL & PROPRIETARY")

            c.setFont("Helvetica", 8)
            c.drawString(x_bot_corner - 350, y_bot_corner + 140, "THIS DOCUMENT CONTAINS COMPANY CONFIDENTIAL AND PROPRIETARY")
            c.drawString(x_bot_corner - 350, y_bot_corner + 130, "INFORMATION OF PREVALON.NEITHER THIS DOCUMENT, NOR ANY INFORMATION")
            c.drawString(x_bot_corner - 350, y_bot_corner + 120, "OBTAINED THEREFROM IS TO REPRODUCED,TRANSMITTED, OR DISCLOSED TO ANY")
            c.drawString(x_bot_corner - 350, y_bot_corner + 110, "THIRD-PARTY WITHOUT FIRST RECEIVING THE EXPRESS WRITTEN AUTHORIZATION OF")
            c.drawString(x_bot_corner - 350, y_bot_corner + 100, "PREVALON.")

            c.drawString(x_bot_corner - 350, y_bot_corner + 90, "© PREVALON, INC. ALL RIGHTS RESERVED")

            c.rect(x_bot_corner - 360, y_bot_corner+240, 360, 60, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 262, "GENERAL ARRANGEMENT DRAWING")

            c.rect(x_bot_corner - 360, y_bot_corner+300, 360, 120, fill=0)  # (x, y, width, height)
            c.drawImage("Prevalon Logo.jpg", x_bot_corner - 270, y_bot_corner+310, height = 100, width = 180)

            c.rect(x_bot_corner - 360, y_bot_corner+420, 360, 80, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica", 14)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 440, proj_name + ", "+ proj_location)
            c.setFont("Helvetica", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 470, '{:,.2f}'.format(power_req) + " MW / " + '{:,.2f}'.format(power_req*duration) +" MWh")

            c.rect(x_bot_corner - 360, y_bot_corner+500, 360, 60, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 522, "NOT FOR CONSTRUCTION")

            c.setFont("Helvetica", 10)
            c.rect(x_bot_corner - 360, y_bot_corner+640, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 320, y_bot_corner + 655, str(feeder_qty))
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 663, "AUX TRANFORMERS")
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 648, "(BY OTHERS)")
            c.drawCentredString(x_bot_corner - 60, y_bot_corner + 655,  '{:,.0f}'.format(aux_xfrm_rating) + " kVA")

            c.rect(x_bot_corner - 360, y_bot_corner+680, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 320, y_bot_corner + 695, str(feeder_qty))
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 703, "AUX AC PANEL")
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 688, "(BY OTHERS)")
            c.drawCentredString(x_bot_corner - 60, y_bot_corner + 695, "N/A")

            c.rect(x_bot_corner - 360, y_bot_corner+720, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 320, y_bot_corner + 735, str(block_qty))
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 743, "INVERTER WITH INTEGRATED")
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 728, "MV TRANSFORMER")
            c.drawCentredString(x_bot_corner - 60, y_bot_corner + 735, PCS_kVA_string)

            c.rect(x_bot_corner - 360, y_bot_corner+760, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 320, y_bot_corner + 775,  str(int(block_qty*block_type)))
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 775, "20' BESS CONTAINER")
            c.drawCentredString(x_bot_corner - 60, y_bot_corner + 775, str('{:,.2f}'.format(BESS_Rating)) + " kWh")

            c.rect(x_bot_corner - 360, y_bot_corner+800, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 320, y_bot_corner + 815, "QTY")
            c.drawCentredString(x_bot_corner - 200, y_bot_corner + 815, "DESCRIPTION")
            c.drawCentredString(x_bot_corner - 60, y_bot_corner + 815, "RATING")

            c.rect(x_bot_corner - 360, y_bot_corner+640, 80, 200, fill=0)  # (x, y, width, height)

            c.rect(x_bot_corner - 280, y_bot_corner+640, 160, 200, fill=0)  # (x, y, width, height)

            c.setFont("Helvetica", 14)
            c.rect(x_bot_corner - 360, y_bot_corner+840, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 855, "EQUIPMENT SCHEDULE")

            # Save the PDF

        def add_outer_block(c, x, y, inner_block_length, inner_block_width, n_s_block_limit, block_type):
            x = x - access_road_width - access_road_width/8
            y = y - access_road_width - access_road_width/8

            outer_block_length = inner_block_length + 2*access_road_width

            inner_block_width_partial = (n_s_block_limit % n_s_block_access_road)*(container_width*2 + container_clearance_minimum) + (n_s_block_limit % n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4
            inner_block_width_full = n_s_block_access_road*(container_width*2 + container_clearance_minimum) + (n_s_block_access_road - 1) * container_clearance_long_end + access_road_width/4

            if n_s_block_limit % n_s_block_access_road != 0:
            
                outer_block_width = n_s_block_limit//n_s_block_access_road*(inner_block_width_full  + access_road_width) + inner_block_width_partial + 2*access_road_width
                                    
            else:
                outer_block_width = n_s_block_limit//n_s_block_access_road*(inner_block_width_full) + 2*access_road_width

            c.roundRect(x, y, outer_block_length, outer_block_width, access_road_width/8, fill = 0)  # (x, y, width, height)
            
            # c.rect(x, y, access_road_width, container_length, fill=0)    

            return outer_block_length, outer_block_width

        def dimensions(c, x_start, y_start, access_road_width, block_type, inner_block_length, inner_block_width, outer_block_length, outer_block_width):
            c.setDash(6, 3)
            c.setLineWidth(0.4)
            
            # Vertical Lines
            x = x_start - access_road_width - access_road_width/8
            y = y_start
            c.line(x, y, x, 1580)

            x = x + outer_block_length
            c.line(x, y, x, 1580)
            
            c.setFont("Helvetica", 20)
            # Outer Length
            draw_arrow(c, x - outer_block_length, 1580, x, 1580, 10*scaling_factor, 1)
            c.drawCentredString(x - outer_block_length + outer_block_length/2, 1580 + 10, dim(outer_block_length, scaling_factor, "", ""))

            x = x_start - access_road_width/8
            c.line(x, y, x, 1540)

            c.setFont("Helvetica", min(20*scaling_factor, 20))


            # Access Road Length
            draw_arrow(c, x - access_road_width, 1500, x, 1500, 10*scaling_factor, 1)
            c.drawCentredString(x - access_road_width + access_road_width/2, 1500 + 30*scaling_factor, dim(access_road_width, \
                                                                                                        scaling_factor, "     ", ""))
            c.drawCentredString(x - access_road_width + access_road_width/2, 1500 + 10*scaling_factor, "          (ACCESS ROAD TYP.)")

            x = x_start
            c.line(x, y, x, 1500)


            x = x + pcs_length + pcs_clearance_short_end + container_length

            if block_type > 2:
                x = x + container_clearance_minimum + container_length

            c.line(x, y, x, 1500)

            block_length = pcs_length + pcs_clearance_short_end + container_length
            if block_type > 2:
                block_length = block_length + container_clearance_minimum + container_length

            # Block Length
            draw_arrow(c, x_start, 1500, x, 1500, 10*scaling_factor, 1)
            c.drawCentredString((x_start + x)/2, 1500 + 30*scaling_factor, dim(block_length, scaling_factor, "", ""))
            c.drawCentredString((x_start + x)/2, 1500 + 10*scaling_factor, "(BLOCK LENGTH TYP.)")
            
            # Block Clearance

            if block_type > 2:

                x = x + pcs_clearance_short_end
                c.line(x, y, x, 1500)
                
                draw_arrow(c, x - pcs_clearance_short_end, 1500, x, 1500, 10*scaling_factor, 1)
                c.drawString(x - pcs_clearance_short_end, 1500 + 20*scaling_factor, dim(pcs_clearance_short_end, scaling_factor, "", ""))
                
            x = x_start - access_road_width/8 + inner_block_length
            c.line(x, y, x, 1540)
            
            # Inner Block Length
            draw_arrow(c, x_start - access_road_width/8, 1540, x, 1540, 10*scaling_factor, 1)
            c.drawCentredString((x_start + x)/2, 1540 + 20*scaling_factor, dim(inner_block_length, scaling_factor, "", ""))


            # Horizontal Lines
            x = x_start
            y = y_start + pcs_width/2 + container_clearance_minimum/2 + container_width + access_road_width/8 + access_road_width
            y_upper_block = y - access_road_width
            y_outer = y - outer_block_width
            c.line(x, y, 110, y)

            # Outer Width
            c.setFont("Helvetica", 20)
            draw_arrow(c, 110, y_outer, 110, y, 10*scaling_factor, 2)
            draw_vertical_text(c, 100, (y + y_outer)/2, dim(outer_block_width, scaling_factor, "", ""))
            c.setFont("Helvetica", min(20*scaling_factor, 20))


            y = y - access_road_width
            c.line(x, y, 170, y)

            y = y - access_road_width/8
            c.line(x + container_length + pcs_clearance_short_end, y, 190, y)

            y = y - 2*container_width - container_clearance_minimum
            c.line(x + container_length + pcs_clearance_short_end, y, 190, y)

            # Block Width
            draw_arrow(c, 190, y, 190, y + 2*container_width + container_clearance_minimum, 10*scaling_factor, 2)
            draw_vertical_text(c, 190 - 10*scaling_factor, (y + (y + 2*container_width + container_clearance_minimum))/2, dim(2*container_width + container_clearance_minimum, \
                                                                                                    scaling_factor, "", ""))

            if dual_row == 1:
                y = y - container_clearance_long_end
                c.line(x + container_length + pcs_clearance_short_end, y, 220, y)

                # Block Clearance
                draw_arrow(c, 220, y, 220, y + container_clearance_long_end, 10*scaling_factor, 2)
                draw_vertical_text(c, 220 - 10*scaling_factor, (y + y + container_clearance_long_end)/2, dim(container_clearance_long_end, \
                                                                                                        scaling_factor, "", ""))
                
            y = y_upper_block - max_inner_block_width
            c.line(x_start, y, 170, y)

            #Inner Block Width
            draw_arrow(c, 170, y , 170, y + max_inner_block_width, 10*scaling_factor, 2)
            draw_vertical_text(c, 170 - 10*scaling_factor, (y + y + max_inner_block_width)/2, dim(max_inner_block_width, \
                                                                                                    scaling_factor, "", ""))
            
            y = y - access_road_width
            c.line(x_start, y, 170, y)

            #Access Road Width
            draw_arrow(c, 170, y , 170, y + access_road_width, 10*scaling_factor, 2)
            draw_vertical_text(c, 170 - 10*scaling_factor, (y + y + access_road_width)/2, dim(access_road_width, \
                                                                                                    scaling_factor, "", ""))

            y = y_outer
            c.line(x, y, 100, y)


        pdf_path = "General Arrangement Drawing " + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"
        c = canvas.Canvas(pdf_path, pagesize=landscape(A1))


        x_start = 250 + scaling_factor*200
        y_start = 1380 - scaling_factor*300

        dual_row = 0

        x_start_block = x_start
        y_start_block = y_start


        x = x_start_block
        y = y_start_block

        e_w_block_count = 1
        block_count = 1
        container_count = 1

        n_s_block_count = 1



        while n_s_block_count <= n_s_block_limit:
            y_block_mid = y_start_block + pcs_width/2

            while e_w_block_count <= e_w_block_limit and block_count <= block_qty:
                x = add_block(c, block_type, x, y_block_mid, e_w_block_count, block_count, container_count)
                e_w_block_count = e_w_block_count + 1
                block_count = block_count + 1
                container_count = container_count + block_type

            
            x = x_start_block

            if n_s_block_count % n_s_block_access_road == 0 or n_s_block_count == n_s_block_limit:
                y_start_block = y_block_mid - container_clearance_minimum/2 - container_width - access_road_width/4 - access_road_width - \
                    container_width - container_clearance_minimum/2 - pcs_width/2
                
                inner_block_length, inner_block_width = add_inner_block(c, x_start_block, y_block_mid - container_width - container_clearance_minimum/2,  e_w_block_limit, n_s_block_count, block_type)

                if n_s_block_count // n_s_block_access_road == 0:
                    max_inner_block_width = inner_block_width
                else:
                    max_inner_block_width = n_s_block_access_road*(container_width*2 + container_clearance_minimum) + (n_s_block_access_road - 1)*container_clearance_long_end + access_road_width/4

            else:
                y_start_block = y_block_mid - container_clearance_minimum/2 - container_width - container_clearance_long_end - \
                    container_width - container_clearance_minimum/2 - pcs_width/2
                
                dual_row = 1

            e_w_block_count = 1
            n_s_block_count = n_s_block_count + 1


        y = y_block_mid - container_width - container_clearance_minimum/2
        outer_block_length, outer_block_width = add_outer_block(c, x_start_block, y, inner_block_length, inner_block_width, n_s_block_limit, block_type)

        area = outer_block_length/12/scaling_factor*outer_block_width/12/scaling_factor

        border(c, area, block_qty, block_type)

        dimensions(c, x_start, y_start, access_road_width, block_type, inner_block_length, inner_block_width, outer_block_length, outer_block_width)

        c.save()

        return pdf_path

    if n_clicks:
        # Generate PDF
        GA_PDF = '/download/{}'.format(create_GA(proj_location, proj_name, power_req, duration, bol, PCS_kVA_string, BESS_Rating, aug))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        GA_PDF = ''
    return GA_PDF, n_clicks

@app.callback(
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

 ]
)

def update_SLD(n_clicks, proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String):
    
    def create_SLD(proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String):
               
        if complaince_code == "IEC":
            RMU_req = "Yes"
        else:
            RMU_req = "No"

        block_qty = int(bol['Value']['1'].replace(',', ''))
        block_type = int(int(bol['Value']['0'].replace(',', ''))/int(bol['Value']['1'].replace(',', '')))

        feeder_qty = math.ceil(block_qty/8)

        feeders = []

        for i in range(feeder_qty):
            feeders.append(block_qty//feeder_qty)

        i = 0

        while sum(feeders) < block_qty:
            feeders[i] = feeders[i] + 1
            i = i + 1

        def draw_arrow(c, x1, y1, x2, y2, arrow_size, orient):
            c.setDash()
            c.setLineWidth(0.4)

            if orient == 1:
                """
                Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
                arrow_size determines the size of the arrowhead.
                """

                # Draw the main line
                c.line(x1, y1, x2, y2)
                
                c.setFont("Helvetica", 14)
                c.drawCentredString(x1-2, y1-5, "//")


                # Draw the second arrowhead
                c.line(x2, y2, x2 - arrow_size, y2 + arrow_size/2)
                c.line(x2, y2, x2 - arrow_size, y2 - arrow_size/2)

                c.setFont("Helvetica", 14)


            if orient == 2:
                """
                Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
                arrow_size determines the size of the arrowhead.
                """

                # Draw the main line
                c.line(x1, y1, x2, y2)
                
                # Draw the second arrowhead
                c.line(x2, y2, x2 - arrow_size, y2 + arrow_size/2)
                c.line(x2, y2, x2 - arrow_size, y2 - arrow_size/2)

                c.setFont("Helvetica", 14)

            if orient == 3:
                """
                Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
                arrow_size determines the size of the arrowhead.
                """

                # Draw the main line
                c.line(x1, y1, x2, y2)
                
                # Draw the second arrowhead
                c.line(x1, y1, x1 + arrow_size, y1 + arrow_size/2)
                c.line(x1, y1, x1 + arrow_size, y1 - arrow_size/2)

                c.setFont("Helvetica", 14)
                c.drawCentredString(x2+2, y2-5, "//")



            c.setDash()
            c.setLineWidth(0.4)


        def border(c, block_qty, block_type):
            # Draw a rectangle
            c.setStrokeColorRGB(0, 0, 0)  # Set stroke color to black
            c.rect(20*mm, 20*mm, (841-40)*mm, (594-40)*mm, fill=0)  # (x, y, width, height)

            x_top_corner = (841-20)*mm
            y_top_corner = (594-20)*mm

            x_bot_corner = (841-20)*mm
            y_bot_corner = (20)*mm

            c.setFont("Helvetica", 14)

            c.rect(x_top_corner- 360, y_top_corner - 40, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_top_corner - 180, y_top_corner - 25, "NOTES")

            c.setFont("Helvetica", 8)
            x_notes = x_top_corner - 350
            y_notes = y_top_corner - 60

            c.drawString(x_notes, y_notes,      " 1. BUYER TO SIZE AND PROVIDE FOLLOWING CABLES:")
            c.drawString(x_notes, y_notes - 10, "     -  MV FEEDER CABLES")
            c.drawString(x_notes, y_notes - 20, "     -  AC CABLES FROM AUXILIARY AC PANEL TO THE ENCLOSURES")
            c.drawString(x_notes, y_notes - 30, "     -  DC CABLES FROM MAIN DC DISCONNECT OF THE ENCLOSURE TO THE")
            c.drawString(x_notes, y_notes - 40, "        DC INPUT OF THE INVERTER")
            
            c.drawString(x_notes, y_notes - 60, " 2. EQUIPMENT RATING SHOWN ARE NAMEPLATE VALUES.")
            
            c.drawString(x_notes, y_notes - 80, " 3. THIS DOCUMENT ONLY SHOWS EQUIPMENT IN PREVALON'S SCOPE AT BOL.")
            c.drawString(x_notes, y_notes - 100, " 4. FINAL SITE LEVEL SLD IN BUYER'S SCOPE. AS REQUIRED, SITE LEVEL SLD TO ALSO")
            c.drawString(x_notes, y_notes - 110, "     INCLUDE EQUIPMENT OUTSIDE OF PREVALON'S SCOPE INCLUDING BUT")
            c.drawString(x_notes, y_notes - 120, "     NOT LIMITED TO AUX TRANSFORMERS AND AC PANELS, AUGMENTATION EQUIPMENT")
            c.drawString(x_notes, y_notes - 130, "     REQUIRED OVER THE LIFE OF PROJECT, MV SWITCHGEAR, SUBSTATION YARD ETC.")

            c.rect(x_top_corner- 360, y_notes - 140, 360, 200, fill=0)

            c.setFont("Helvetica", 9)

            c.rect(x_bot_corner - 360, y_bot_corner, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 270, y_bot_corner + 15, "REASON FOR CONTROL - NLR")
            c.drawCentredString(x_bot_corner - 90, y_bot_corner + 15, "DRAWING RELEASE DATE: " + str(date.today()))
            
            c.rect(x_bot_corner - 360, y_bot_corner + 40, 360, 40, fill=0)  # (x, y, width, height)
            c.drawCentredString(x_bot_corner - 270, y_bot_corner + 40 + 15, "SECURITY LEVEL - SL2")
            c.drawCentredString(x_bot_corner - 90, y_bot_corner + 40 + 15, "EXPORT CLASSIFICATION - EAR99")

            c.rect(x_bot_corner - 360, y_bot_corner, 180, 80, fill=0)  # (x, y, width, height)


            c.rect(x_bot_corner - 360, y_bot_corner+80, 360, 160, fill=0)  # (x, y, width, height)

            c.setFont("Helvetica", 10)
            c.drawCentredString(x_bot_corner - 170, y_bot_corner + 225, "EXPORT ADMINISTRATION REGULATIONS WARNING")
            
            c.setFont("Helvetica", 8)
            c.drawString(x_bot_corner - 350, y_bot_corner + 210, "THIS DOCUMENT CONTAINS TECHNICAL DATA WHICH IF EXPORTED FROM THE UNITED")
            c.drawString(x_bot_corner - 350, y_bot_corner + 200, "STATES MUST BE EXPORTED IN ACCORDANCE WITH THE EXPORT ADMINISTRATION ")
            c.drawString(x_bot_corner - 350, y_bot_corner + 190, "REGULATIONS. DIVERSION CONTRARY TO U.S. LAW IS PROHIBITED.")

            c.setFont("Helvetica", 10)
            c.drawCentredString(x_bot_corner - 170, y_bot_corner + 155, "CONFIDENTIAL & PROPRIETARY")

            c.setFont("Helvetica", 8)
            c.drawString(x_bot_corner - 350, y_bot_corner + 140, "THIS DOCUMENT CONTAINS COMPANY CONFIDENTIAL AND PROPRIETARY")
            c.drawString(x_bot_corner - 350, y_bot_corner + 130, "INFORMATION OF PREVALON.NEITHER THIS DOCUMENT, NOR ANY INFORMATION")
            c.drawString(x_bot_corner - 350, y_bot_corner + 120, "OBTAINED THEREFROM IS TO REPRODUCED,TRANSMITTED, OR DISCLOSED TO ANY")
            c.drawString(x_bot_corner - 350, y_bot_corner + 110, "THIRD-PARTY WITHOUT FIRST RECEIVING THE EXPRESS WRITTEN AUTHORIZATION OF")
            c.drawString(x_bot_corner - 350, y_bot_corner + 100, "PREVALON.")

            c.drawString(x_bot_corner - 350, y_bot_corner + 90, "© PREVALON, INC. ALL RIGHTS RESERVED")

            c.rect(x_bot_corner - 360, y_bot_corner+240, 360, 60, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 262, "PROJECT SINGLE LINE DIAGRAM")

            c.rect(x_bot_corner - 360, y_bot_corner+300, 360, 120, fill=0)  # (x, y, width, height)
            c.drawImage("Prevalon Logo.jpg", x_bot_corner - 270, y_bot_corner+310, height = 100, width = 180)

            c.rect(x_bot_corner - 360, y_bot_corner+420, 360, 80, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica", 14)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 440, proj_name + ", "+ proj_location)
            c.setFont("Helvetica", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 470, '{:,.2f}'.format(power_req) + " MW / " + '{:,.2f}'.format(power_req*duration) +" MWh")

            c.rect(x_bot_corner - 360, y_bot_corner+500, 360, 60, fill=0)  # (x, y, width, height)
            c.setFont("Helvetica-Bold", 18)
            c.drawCentredString(x_bot_corner - 180, y_bot_corner + 522, "NOT FOR CONSTRUCTION")

            c.setDash(6, 4)
            c.setLineWidth(2)
            c.line(x_bot_corner - 800, y_top_corner - 40, x_bot_corner - 800, y_bot_corner + 40)
            c.drawString(x_bot_corner - 1020, y_top_corner - 50, "PREVALON ENERGY'S")
            c.drawString(x_bot_corner - 1020, y_top_corner - 68, "SCOPE")    
            c.drawString(x_bot_corner - 790, y_top_corner - 50, "BUYER'S SCOPE")

            c.setFont("Helvetica", 14)

            c.setDash()
            c.setLineWidth(0.4)




        def add_feeder(c, x, y, feeder_number, feeder_block_qty, block_type, unique_feeder):
            y_feeder = y

            if feeder_block_qty == 0:

                c.setFont("Helvetica-Bold", 14)
                
                c.drawString(x + 1520, y+50, "FEEDER #" + str(feeder_number+1) + " TO MEDIUM VOLTAGE BUS")
                
                c.setFont("Helvetica-Oblique", 12)

                c.drawString(x + 1520, y+30, "SAME AS FEEDER #" + str(unique_feeder))

                draw_arrow(c, x + 1300, y + 50, x + 1500, y+50, 10, 1)

            else:
                c.setFont("Helvetica-Bold", 14)

                c.drawString(x + 1520, y+272, "FEEDER #" + str(feeder_number+1) + " TO MEDIUM VOLTAGE BUS")

                for i in range(feeder_block_qty):
                    # Outer Rectangle
                    c.setDash(6, 4)
                    c.setLineWidth(0.4)

                    x = x + (1300 - 150*feeder_block_qty)/(feeder_block_qty+1)
                    c.rect(x, y_feeder, 150, 260)  # (x, y, width, height)

                    c.setDash()
                    c.setLineWidth(0.4)
                    c.setFont("Helvetica", 8)
                    c.drawString(x + 5, y_feeder - 10, "BATTERY BLOCK F" + str(feeder_number+1) + " #" + str(i + 1))
                    c.setFont("Helvetica-Bold", 14)

                    x_block = x

                    x = x_block + (150 - 20*4)/(4+1)
                    y = y_feeder + 20

                    x_mid = x_block + 150/2
                    if RMU_req == "Yes":
                        c.line(x_mid + 20, y + 260, x_mid + 20 + 150 - 20 + (1300 - 150*feeder_block_qty)/(feeder_block_qty+1), y + 260)
                    else:
                        c.line(x_mid + 20, y + 260, x_mid + 20 + 150 - 40 + (1300 - 150*feeder_block_qty)/(feeder_block_qty+1), y + 260)
                    
                    if i == feeder_block_qty - 1:
                        draw_arrow(c, x_mid + 20 + 150 - 40 + (1300 - 150*feeder_block_qty)/(feeder_block_qty+1), y + 260, 1600, y+260, 10, 2)
                    if i == 0:
                        
                        # Ground
                        c.line(x_mid - 40, y + 260 - 10, x_mid - 40, y + 260 + 10)
                        c.line(x_mid - 45, y + 260 - 7, x_mid - 45, y + 260 + 7)
                        c.line(x_mid - 50, y + 260 - 4, x_mid - 50, y + 260 + 4)
                        if RMU_req == "Yes":
                            c.line(x_mid, y + 260, x_mid - 40, y + 260)
                        else:
                            c.line(x_mid - 20, y + 260, x_mid - 40, y + 260)

                        # PCS SPECIFICATIONS
                        # DELTA - WYE
                        x1, y1 = x_mid - 35, y + 127
                        x2, y2 = x_mid - 30, y + 127
                        x3, y3 = x_mid - 32.5, y + 132
                        c.line(x1, y1, x2, y2)
                        c.line(x2, y2, x3, y3)
                        c.line(x3, y3, x1, y1)

                        x1, y1 = x_mid - 35, y + 115
                        x2, y2 = x_mid - 32.5, y + 113
                        x3, y3 = x_mid - 30, y + 115
                        x4, y4 = x_mid - 32.5, y + 110
                        c.line(x1, y1, x2, y2)
                        c.line(x2, y2, x3, y3)
                        c.line(x4, y4, x2, y2)

                        c.setFont("Helvetica", 6)
                        c.drawString(x_mid + 17, y + 130, PCS_String[:8])
                        c.drawString(x_mid + 17, y + 123, "34.5 kV - 690 V AC")
                        c.drawString(x_mid + 17, y + 116, "Z% = 6%")
                        c.drawString(x_mid + 17, y + 109, "Dy11")
                        c.setFont("Helvetica-Bold", 14)
                        
                    if RMU_req == "Yes":
                        
                        for i in range(3):
                            # Ground
                            c.line(x_mid - 34, y + 240 - 20 - 35*i, x_mid - 34, y + 240 - 10 - 35*i)
                            c.line(x_mid - 37, y + 240 - 17 - 35*i, x_mid - 37, y + 240 - 13 - 35*i)
                            c.line(x_mid - 40, y + 240 - 16 - 35*i, x_mid - 40, y + 240 - 14 - 35*i)

                            c.line(x_mid - 34, y + 240 - 15 - 35*i, x_mid - 25, y + 240 - 15 - 35*i)
                            c.line(x_mid - 25, y + 240 - 15 - 35*i, x_mid - 25, y + 240 - 18 - 35*i)
                            
                            # Breaker
                            c.line(x_mid - 25, y + 240 - 18 - 35*i, x_mid - 20, y + 240 - 23 - 35*i)
                            c.line(x_mid - 25, y + 240 - 23 - 35*i, x_mid - 25, y + 240 - 30 - 35*i)
                            
                            c.line(x_mid - 25, y + 240 - 30 - 35*i, x_mid - 30, y + 240 - 30 - 35*i)
                            
                            # Breaker
                            c.line(x_mid - 30, y + 240 - 30 - 35*i, x_mid - 35, y + 240 - 25 - 35*i)
                            c.line(x_mid - 35, y + 240 - 30 - 35*i, x_mid - 50, y + 240 - 30 - 35*i)
                        
                        c.line(x_mid - 50, y + 240 - 30, x_mid - 50, y + 240 - 30 - 35*2)
                        c.line(x_mid - 25, y + 240 - 30 - 35*2, x_mid, y + 240 - 30 - 35*2)
                        
                        c.line(x_mid + 20, y + 260, x_mid + 20, y + 240 - 30 - 35*1)
                        c.line(x_mid + 20, y + 240 - 30 - 35*1, x_mid - 25, y + 240 - 30 - 35*1)
                        
                        c.line(x_mid, y + 240 - 30, x_mid, y + 260)
                        c.line(x_mid, y + 240 - 30, x_mid - 25, y + 240 - 30)

                    else:
                        
                            c.line(x_mid - 20, y + 190, x_mid - 20, y + 260)
                            c.line(x_mid + 20, y + 190, x_mid + 20, y + 260)

                            c.line(x_mid - 20, y + 190, x_mid + 20, y + 190)

                            ## Breaker and Fuses
                            # Breaker
                            c.line(x_mid, y + 170, x_mid, y + 190)
                            c.line(x_mid, y + 165, x_mid - 2, y + 170)

                            c.line(x_mid, y + 158, x_mid, y + 165)

                            #Fuse
                            c.rect(x_mid - 2, y + 153, 4, 4)
                            c.rect(x_mid - 2, y + 152, 4, 6)

                            c.line(x_mid, y + 146, x_mid, y + 152)

                            #Fuse
                            c.rect(x_mid - 2, y + 141, 4, 4)
                            c.rect(x_mid - 2, y + 140, 4, 6)

                    c.line(x_mid, y + 132, x_mid, y + 140)

                    # Medium Voltage Transformer
                    c.line(x_mid - 10, y + 122, x_mid + 10, y + 122)
                    c.line(x_mid - 10, y + 120, x_mid + 10, y + 120)

                    for i in range(4):
                        c.arc(x_mid - (10 - 5*i), y + 132 + 5, x_mid - (10 - 5*(i+1)), y + 132 - 5, 180, 180)
                        c.arc(x_mid - (10 - 5*i), y + 110 + 5, x_mid - (10 - 5*(i+1)), y + 110 - 5, 0, 180)
                    


                    c.line(x_mid, y + 90, x_mid, y + 110)

                    # AC Bus - Low Side
                    c.line(x_block + (150 - 20*4)/(4+1), y + 90, x_block + 150 - (150 - 20*4)/(4+1), y + 90)
                    
                    # Inverter DC Buses
                    c.line(x, y + 40, x_mid - 10, y + 40)
                    c.line(x_mid + 10, y + 40, x_mid + 60, y + 40)
                    
                    # Inverter Blocks
                    
                    for j in range(4):
                        # Inverter Symbol
                        c.rect(x, y + 50, 20, 20)  # (x, y, width, height)
                        c.line(x, y + 50, x + 20, y + 70)

                        c.line(x + 12, y + 55.5, x + 16, y + 55.5)
                        c.line(x + 12, y + 56.5, x + 16, y + 56.5)
                        
                        c.arc(x + 2, y + 60, x + 5,  y + 64, 0, 180)
                        c.arc(x + 5, y + 60, x + 8,  y + 64, 180, 180)

                        c.line(x + 10, y + 70, x + 10, y + 90)

                        c.line(x + 10, y + 50, x + 10, y + 40)

                        x = x + 20 + (150 - 20*4)/(4+1)
                    
                    

                    # Battery Blocks
                    x = x_block + (150 - 30*block_type)/(block_type+1)
                    for j in range(block_type):
                        # Battery Symbol
                        c.rect(x, y, 30, 30)  # (x, y, width, height)
                        
                        c.line(x + 5, y + 15, x + 13, y + 15)
                        c.line(x + 13, y + 12, x + 13, y + 18)

                        c.line(x + 16, y + 9, x + 16, y + 21)
                        c.line(x + 16, y + 15, x + 25, y + 15)

                        c.setFont("Helvetica", 8)
                        c.drawString(x + 6, y + 18, "+")
                        c.drawString(x + 20, y + 19, "-")
                        c.setFont("Helvetica-Bold", 14)

                        if j == 1 and block_type % 2 != 0 or block_type == 1:
                            c.line(x + 15, y + 30, x + 15, y + 35)
                            c.line(x - 15, y + 35, x + 45, y + 35)
                            c.line(x - 15, y + 35, x - 15, y + 40)
                            c.line(x + 45, y + 35, x + 45, y + 40)

                        else:
                            c.line(x + 15, y + 30, x + 15, y + 40)
                        
                        x = x + 30 + (150 - 30*block_type)/(block_type+1)

        
        
        pdf_path = "Single Line Diagram " + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"
        c = canvas.Canvas(pdf_path, pagesize=landscape(A1))

        x_start = 100
        y_start = 1200



        x_start_block = x_start
        y_start_block = y_start


        x = x_start_block
        y = y_start_block

        e_w_block_count = 1
        block_count = 1
        n_s_block_count = 1

        border(c, block_qty, block_type)
        unique_feeder = 0

        for i in range(len(feeders)):
            if i > 0 and feeders[i] == feeders[i-1]:
                y = y + 220
                add_feeder(c, x, y, i, 0, block_type, unique_feeder)
            else:
                add_feeder(c, x, y, i, feeders[i], block_type, unique_feeder)
                unique_feeder = i+1
            y = y - 300

            if y < 100 and i < len(feeders) - 1:
                c.showPage()
                border(c, block_qty, block_type)
                y = y_start_block

        # Aux Feeder

        c.setFont("Helvetica-Bold", 14)

        c.drawString(x + 1520, y+50, "AUX FEEDER FROM MEDIUM VOLTAGE BUS")

        c.setFont("Helvetica-Oblique", 12)

        if RMU_req == "Yes":
            c.drawString(x + 1520, y+30, "400V AC AUX CONNECTION REQUIRED TO EACH OF")
        else:
            c.drawString(x + 1520, y+30, "480V AC AUX CONNECTION REQUIRED TO EACH OF")

        c.drawString(x + 1520, y+10, "THE ENCLOSURES IN THE ABOVE FEEDERS")
        draw_arrow(c, x + 1300, y + 50, x + 1500, y+50, 10, 3)

        c.setFont("Helvetica", 14)

        # c.showPage() ## ADDS A PAGE

        # if RMU_req == "Yes":
        #     batt_block_string = str(block_type) + "_RMU_SLD.png"
        # else:
            
        #     batt_block_string = str(block_type) + "_SLD.png"

        # c.drawImage(batt_block_string, 30*mm, 30*mm, width=(841-30)*mm, height=(594-30)*mm)


        c.save()

        return pdf_path

    if n_clicks:
        # Generate PDF
        SLD_PDF = '/download/{}'.format(create_SLD(proj_location, proj_name, power_req, duration, complaince_code, bol, PCS_String))
        n_clicks = 0

    else:
        # If button is not clicked, do nothing
        SLD_PDF = ''

    return SLD_PDF, n_clicks


@app.server.route('/download/<path:path>')
def serve_static(path):
    return send_file(path, as_attachment=True)

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True, port = 2400)