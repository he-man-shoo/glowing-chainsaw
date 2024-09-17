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
import PyPDF2

from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import *
from datetime import date

def calculation(proj_location, proj_name, power_req, duration, number_cycles, point_of_measurement, RMU_Required, PF_required_at_POM, max_site_temp, oversize_required, project_life, number_of_augmentations, flat_guarantee):
    pd.set_option('display.max_colwidth', 200)
        
    energy_req = power_req*duration #MWh
    battery_model = 'HD 511' # Option to Choose Clou AC or Clou LC or HD 511 based on Batteries.xlsx
    r_SOC = 0.5 # % resting SOC
    
    PCS_model = 'Sungrow SC5000UD-MV-US' # Option to Choose based on PCS.xlsx

    if duration > 5:
        PCS_model = 'Sungrow SC4000UD-MV-US' # Option to Choose based on PCS.xlsx
        if duration > 7:
            PCS_model = 'Sungrow SC2750UD-MV-US' # Option to Choose based on PCS.xlsx

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
    stacks_config = [16, 20, 24, 32, 36, 40, 44, 48]

    container_config = [2, 2, 2, 4, 4, 4, 4, 4]

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
                                        "1) Integrated skid containing "+ '{:,.2f}'.format(PCS_kVA*0.001) + pcs_description + " \n" \
                                        "2) AC Output Power: " + '{:,.0f}'.format(PCS_kVA_at_max_site_temp) + "kVA @ "+ '{:,.0f}'.format(max_site_temp) +" deg C  \n" \
                                        "3) " + '{:,.0f}'.format(PCS_kVA) + "kVA " +'{:,.2f}'.format(PCS_AC_Voltage*0.001) + "kV/34.5kV mineral oil (PCB free) filled MV Transformer\n" \
                                        "4) Dimensions: 20’ (L) x 9.5’ (H) x 8’ (W) or 6,058mm (L) x 2,896mm (H) x 2,438mm (W)", \
                                        "Energy Management System with SCADA interface for BESS Dispatch and Control", \
                                        "Environmentally controlled NEMA 3R enclosure housing master fire panel with battery backup"
    
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

    container_config_8_strings =  [2, 0, 0, 4, 2, 2, 0, 0]
    container_config_10_strings = [0, 2, 0, 0, 2, 0, 2, 0]
    container_config_12_strings = [0, 0, 2, 0, 0, 2, 2, 4]

                                        

    cost_memo_table = pd.DataFrame({})
    cost_memo_table["Parameter"] = "Project Location", "Project Name", "Required Power (MW)", \
                                      "Required Energy (MWh)", "Nameplate Energy (kWh)", "AC Usable Energy at POM (kWh)",\
                                        "Qty Strings", "Qty Containers (12 Strings)", "Qty Containers (10 Strings)", \
                                            "Qty Containers (8 Strings)", "Total Qty Containers", "Qty PCS", "PCS Model"

    if RMU_Required == "IEC":
        cost_memo_PCS_string = PCS_model + " with RMU"
    else:
        cost_memo_PCS_string = PCS_model
    
    cost_memo_table["Value"] = proj_location, proj_name, '{:,.2f}'.format(power_req), '{:,.2f}'.format(energy_req), \
                               '{:,.2f}'.format(batt_nameplate*optimized_number_of_stacks), '{:,.2f}'.format((float(power_energy_rte_table["Usable AC Energy at POM (MWh)"][0].replace(',', ''))*1000)), \
                                optimized_number_of_stacks, container_config_12_strings[i]*optimized_number_of_pcs, container_config_10_strings[i]*optimized_number_of_pcs, \
                                container_config_8_strings[i]*optimized_number_of_pcs, optimized_number_of_containers, optimized_number_of_pcs, cost_memo_PCS_string
    

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
        bol_design_summary, plot_title, y_axis_range, months_to_COD, block_type, cost_memo_table, PCS_kVA_string, BESS_Rating, PCS_AC_Voltage, PCS_model

