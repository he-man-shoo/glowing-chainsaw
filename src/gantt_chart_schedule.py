import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import math
from datetime import datetime
import dash


def scheduler(ntp, intended_cod, number_of_PCS, number_of_containers, scope):
    
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
                                                        'font-size': '12px',
                                                        'border': '1px solid black',
                                                        'textAlign': 'center',
                                                    })





    def create_schedule_table(pcs_delay_fntp_po_date, batt_delay_fntp_po_date, batt_delay_shipment_installation, comm_duration):
        
        batt_shipment_duration = 8 #weeks

        pcs_delay_po_date_manu = 0
        pcs_delay_manu_shipment = 0
        pcs_manu_duration = 24 #weeks
        pcs_shipment_duration = batt_shipment_duration
        pcs_delay_shipment_installation = 0
        pcs_installation_duration = 4 #weeks (should change with number of PCSs)

        batt_delay_po_date_dw_conf = 0
        batt_delay_dw_conf_manu = 0
        batt_dw_conf_duration = 13 #weeks
        batt_delay_manu_shipment = 0
        batt_manu_duration = 2 # weeks
        batt_installation_duration = 4 


        delay_comm_installation = 0
        delay_pa_cod = 0
        delay_cod_fa = 9



        containers_per_feeder = math.ceil(number_of_containers/number_feeders)


        ###### PCS Supplier Dataframe
        df = pd.DataFrame([])

        # Creating a column "Event"

        df['Event'] = ['PO Date']

        df.loc[len(df) + 1, 'Event'] = "Manufacturing"

        df.loc[len(df) + 1, 'Event'] = 'First FAT'

        df.loc[len(df) + 1, 'Event'] = 'Shipment Commencement'


        for i in range(number_manu_slots_pcs):
            df.loc[len(df) + 1, 'Event'] = "Shipment Batch #" + str(i + 1)
            if i == 0 :
                df.loc[len(df) + 1, 'Event'] = 'Site Ready to Accept Delivery'
                df.loc[len(df) + 1, 'Event'] = 'Delivery Commencement'
            if i == number_manu_slots_pcs -1 :
                df.loc[len(df) + 1, 'Event'] = 'Guaranteed Delivery Date'
            
            df.loc[len(df) + 1, 'Event'] = "Installation Commencement"
            df.loc[len(df) + 1, 'Event'] = "Installation PCS Batch #" + str(i + 1)


        df['Scope'] = ['PCS Supplier']*len(df['Event'])

        # Adding timelines to the events

        po_date = ntp + pd.to_timedelta(pcs_delay_fntp_po_date, unit="w")
        df.loc[df["Event"] == "PO Date", 'Start_Date'] = po_date
        df.loc[df["Event"] == "PO Date", 'End_Date'] = po_date

        manufacturing_start = po_date + pd.to_timedelta(pcs_delay_po_date_manu, unit="w")
        manufacturing_end = manufacturing_start + pd.to_timedelta(pcs_manu_duration, unit="w")

        df.loc[df["Event"] == "Manufacturing", 'Start_Date'] = manufacturing_start
        df.loc[df["Event"] == "Manufacturing", 'End_Date'] = manufacturing_end
    
        df.loc[df["Event"] == 'First FAT', 'Start_Date'] = manufacturing_end
        df.loc[df["Event"] == 'First FAT', 'End_Date'] = manufacturing_end

        for i in range(number_manu_slots_pcs):

            shipment_start = manufacturing_end + pd.to_timedelta(pcs_delay_manu_shipment, unit="w") + pd.to_timedelta(i, unit="w")
            shipment_end = shipment_start + pd.to_timedelta(pcs_shipment_duration, unit="w")

            if i == 0:
                df.loc[df["Event"] == 'Shipment Commencement', 'Start_Date'] = shipment_start 
                df.loc[df["Event"] == 'Shipment Commencement', 'End_Date'] = shipment_start


            df.loc[df["Event"] == "Shipment Batch #" + str(i+1), 'Start_Date'] = shipment_start
            df.loc[df["Event"] == "Shipment Batch #" + str(i+1), 'End_Date'] = shipment_end

            if i == 0 :
                df.loc[df["Event"] == 'Site Ready to Accept Delivery', 'Start_Date'] = shipment_end - pd.to_timedelta(1, unit="w")
                df.loc[df["Event"] == 'Site Ready to Accept Delivery', 'End_Date'] = shipment_end - pd.to_timedelta(1, unit="w")

                df.loc[df["Event"] == 'Delivery Commencement', 'Start_Date'] = shipment_end
                df.loc[df["Event"] == 'Delivery Commencement', 'End_Date'] = shipment_end

            if i == number_manu_slots_pcs - 1 :
                df.loc[df["Event"] == 'Guaranteed Delivery Date', 'Start_Date'] = shipment_end
                df.loc[df["Event"] == 'Guaranteed Delivery Date', 'End_Date'] = shipment_end

            if i == 0:
                pcs_delivery_to_site = shipment_end

            installation_start= shipment_end + pd.to_timedelta(pcs_delay_shipment_installation, unit="w")
            if i == 0:
                df.loc[df["Event"] == "Installation Commencement", 'Start_Date'] = installation_start
                df.loc[df["Event"] == "Installation Commencement", 'End_Date'] = installation_start


            installation_end = installation_start + pd.to_timedelta(pcs_installation_duration, unit="w")
            df.loc[df["Event"] == "Installation PCS Batch #" + str(i+1), 'Start_Date'] = installation_start
            df.loc[df["Event"] == "Installation PCS Batch #" + str(i+1), 'End_Date'] = installation_end

        proj_milestones = ['Shipment Commencement', 'Site Ready to Accept Delivery', 'Installation Commencement']
        paym_milestones = ['PO Date', 'First FAT', 'Delivery Commencement', 'Guaranteed Delivery Date']

        proj_milestones_combined = []
        paym_milestones_combined = []


        # add Scope to the milestones if they do not have the word in the list; Bascially just to not have "PCS Supplier" in front of 'Site Ready to Accept Delivery'
        list = ['Ready', 'Commencement']
        for i in range(len(proj_milestones)):
            if any(item in proj_milestones[i] for item in list):
                proj_milestones_combined.append(proj_milestones[i])
            else:
                proj_milestones_combined.append(df['Scope'][0] + " | " + proj_milestones[i])

        for i in range(len(paym_milestones)):
            if any(item in paym_milestones[i] for item in list):
                paym_milestones_combined.append(paym_milestones[i])
            else:
                paym_milestones_combined.append(df['Scope'][0] + " | " + paym_milestones[i])


        ### Generating a Dataframe for Battery Supplier
        total_installed_capacity = 0
        remaining_installed_capacity = 0
        j = 0

        df_2 = pd.DataFrame([])
        # 'SLOC Received by Prevalon', 'SLOC Received by the Buyer'
        df_2['Event'] = 'PO Date', 'SLOC Received by Prevalon', 'SLOC Received by the Buyer','Drawing Confirmation', 'Drawing Confirmation Date'

        for i in range(number_manu_slots_batt):
            df_2.loc[len(df_2) + 1, 'Event'] = "Manufacturing Batch #" + str(i + 1)
            if i == 0:
                df_2.loc[len(df_2) + 1, 'Event'] = "First FAT"
                df_2.loc[len(df_2) + 1, 'Event'] = "First BESS loaded at Port of Export"
            if i == number_manu_slots_batt - 1:
                df_2.loc[len(df_2) + 1, 'Event'] = "Final FAT"
            df_2.loc[len(df_2) + 1, 'Event'] = "Shipment Batch #" + str(i + 1)
            if i == number_manu_slots_batt - 1 :
                df_2.loc[len(df_2) + 1, 'Event'] = 'Final Delivery of all DC Block Equipment'                
                df_2.loc[len(df_2) + 1, 'Event'] = 'Guaranteed Delivery Completion Date'
            df_2.loc[len(df_2) + 1, 'Event'] = "Installation BESS Batch #" + str(i + 1)

            if i == number_manu_slots_batt - 1 :
                 df_2.loc[len(df_2) + 1, 'Event'] = "Installation Completion"

            # Commissioning 

            total_installed_capacity = total_installed_capacity + manufacturing_slot_size_batt

            if total_installed_capacity > number_of_containers:
                remaining_installed_capacity = total_installed_capacity - number_of_containers
                total_installed_capacity = number_of_containers

            else:
                remaining_installed_capacity = remaining_installed_capacity + manufacturing_slot_size_batt
            
            
            while remaining_installed_capacity >= containers_per_feeder and j <= number_feeders - 1:
                if j == 0:
                    df_2.loc[len(df_2) + 1, 'Event'] = "Backfeed Available"
                df_2.loc[len(df_2) + 1, 'Event'] = "Comissioning Feeder #" + str(j + 1)
                remaining_installed_capacity = remaining_installed_capacity - containers_per_feeder
                j = j + 1


            if j == number_feeders - 1 and i == number_manu_slots_batt -1 and remaining_installed_capacity > 0:
                if j == 0:
                    df_2.loc[len(df_2) + 1, 'Event'] = "Backfeed Available"
                df_2.loc[len(df_2) + 1, 'Event'] = "Comissioning Feeder #" + str(j + 1)
                remaining_installed_capacity = remaining_installed_capacity - remaining_installed_capacity
                j = j + 1

        df_2.loc[len(df_2) + 1, 'Event'] = "Guaranteed Provisional Acceptance"

        df_2.loc[len(df_2) + 1, 'Event'] = "Commercial Operation Date"

        df_2.loc[len(df_2) + 1, 'Event'] = "Final Acceptance"

            
        df_2['Scope'] = ['Battery Supplier']*len(df_2['Event'])

        # Gantt Chart Inputs

        total_installed_capacity = 0
        remaining_installed_capacity = 0
        j = 0


        po_date = ntp + pd.to_timedelta(batt_delay_fntp_po_date, unit="w")
        df_2.loc[df_2["Event"] == "PO Date", 'Start_Date'] = po_date
        df_2.loc[df_2["Event"] == "PO Date", 'End_Date'] = po_date


        sloc_prevalon = po_date + pd.to_timedelta(45, unit="d")
        df_2.loc[df_2["Event"] == "SLOC Received by Prevalon", 'Start_Date'] = sloc_prevalon
        df_2.loc[df_2["Event"] == "SLOC Received by Prevalon", 'End_Date'] = sloc_prevalon

        sloc_buyer = po_date + pd.to_timedelta(60, unit="d")
        df_2.loc[df_2["Event"] == "SLOC Received by the Buyer", 'Start_Date'] = sloc_buyer
        df_2.loc[df_2["Event"] == "SLOC Received by the Buyer", 'End_Date'] = sloc_buyer

        dw_conf_start = po_date + pd.to_timedelta(batt_delay_po_date_dw_conf, unit="w")
        dw_conf_end = dw_conf_start + pd.to_timedelta(batt_dw_conf_duration, unit="w")
        df_2.loc[df_2["Event"] == "Drawing Confirmation", 'Start_Date'] = dw_conf_start
        df_2.loc[df_2["Event"] == "Drawing Confirmation", 'End_Date'] = dw_conf_end

        df_2.loc[df_2["Event"] == "Drawing Confirmation Date", 'Start_Date'] = dw_conf_end
        df_2.loc[df_2["Event"] == "Drawing Confirmation Date", 'End_Date'] = dw_conf_end


        manufacturing_start = dw_conf_end + pd.to_timedelta(batt_delay_dw_conf_manu, unit="w")

        for i in range(number_manu_slots_batt):

            manufacturing_end = manufacturing_start + pd.to_timedelta(batt_manu_duration, unit="w")
            df_2.loc[df_2["Event"] == "Manufacturing Batch #" + str(i+1), 'Start_Date'] = manufacturing_start
            df_2.loc[df_2["Event"] == "Manufacturing Batch #" + str(i+1), 'End_Date'] = manufacturing_end

            if i == 0:
                df_2.loc[df_2["Event"] == "First FAT", 'Start_Date'] = manufacturing_end
                df_2.loc[df_2["Event"] == "First FAT", 'End_Date'] = manufacturing_end

                first_fat = manufacturing_end

            if i == number_manu_slots_batt -1:
                df_2.loc[df_2["Event"] == "Final FAT", 'Start_Date'] = manufacturing_end
                df_2.loc[df_2["Event"] == "Final FAT", 'End_Date'] = manufacturing_end

            shipment_start = manufacturing_end + pd.to_timedelta(batt_delay_manu_shipment, unit="w")

            shipment_end = shipment_start + pd.to_timedelta(batt_shipment_duration, unit="w")
            df_2.loc[df_2["Event"] == "Shipment Batch #" + str(i+1), 'Start_Date'] = shipment_start
            df_2.loc[df_2["Event"] == "Shipment Batch #" + str(i+1), 'End_Date'] = shipment_end
            
            if i == number_manu_slots_batt - 1 :
                df_2.loc[df_2["Event"] == 'Final Delivery of all DC Block Equipment', 'Start_Date'] = shipment_end
                df_2.loc[df_2["Event"] == 'Final Delivery of all DC Block Equipment', 'End_Date'] = shipment_end
            
                df_2.loc[df_2["Event"] == 'Guaranteed Delivery Completion Date', 'Start_Date'] = shipment_end + pd.to_timedelta(batt_delay_shipment_installation, unit="w") 
                df_2.loc[df_2["Event"] == 'Guaranteed Delivery Completion Date', 'End_Date'] = shipment_end + pd.to_timedelta(batt_delay_shipment_installation, unit="w")
            
            if i == 0:
                df_2.loc[df_2["Event"] == "First BESS loaded at Port of Export", 'Start_Date'] = shipment_start + pd.to_timedelta(1, unit="w")
                df_2.loc[df_2["Event"] == "First BESS loaded at Port of Export", 'End_Date'] = shipment_start + pd.to_timedelta(1, unit="w")
                
                batt_delivery_to_site = shipment_end

            installation_start= shipment_end + pd.to_timedelta(batt_delay_shipment_installation, unit="w")

            installation_end = installation_start + pd.to_timedelta(batt_installation_duration, unit="w")
            df_2.loc[df_2["Event"] == "Installation BESS Batch #" + str(i+1), 'Start_Date'] = installation_start
            df_2.loc[df_2["Event"] == "Installation BESS Batch #" + str(i+1), 'End_Date'] = installation_end

            if i == number_manu_slots_batt - 1:
                df_2.loc[df_2["Event"] == "Installation Completion", 'Start_Date'] = installation_end
                df_2.loc[df_2["Event"] == "Installation Completion", 'End_Date'] = installation_end

            # Commissioning 

            total_installed_capacity = total_installed_capacity + manufacturing_slot_size_batt

            if total_installed_capacity > number_of_containers:
                remaining_installed_capacity = total_installed_capacity - number_of_containers
                total_installed_capacity = number_of_containers

            else:
                remaining_installed_capacity = remaining_installed_capacity + manufacturing_slot_size_batt

            while remaining_installed_capacity >= containers_per_feeder and j <= number_feeders - 1:
                comissioning_start = installation_end + pd.to_timedelta(delay_comm_installation, unit="w")
                comissioning_end = comissioning_start + pd.to_timedelta(comm_duration, unit="d")

                if j == 0:
                    df_2.loc[df_2["Event"] == "Backfeed Available", 'Start_Date'] = comissioning_start - pd.to_timedelta(1, unit="w")
                    df_2.loc[df_2["Event"] == "Backfeed Available", 'End_Date'] = comissioning_start - pd.to_timedelta(1, unit="w")

                df_2.loc[df_2["Event"] == "Comissioning Feeder #" + str(j+1), 'Start_Date'] = comissioning_start
                df_2.loc[df_2["Event"] == "Comissioning Feeder #" + str(j+1), 'End_Date'] = comissioning_end

                remaining_installed_capacity = remaining_installed_capacity - containers_per_feeder
                j = j + 1
            
            if j == number_feeders - 1 and i == number_manu_slots_batt -1 and remaining_installed_capacity > 0:
                comissioning_start = installation_end + pd.to_timedelta(delay_comm_installation, unit="w")
                comissioning_end = comissioning_start + pd.to_timedelta(comm_duration, unit="d")
          
                df_2.loc[df_2["Event"] == "Comissioning Feeder #" + str(j+1), 'Start_Date'] = comissioning_start
                df_2.loc[df_2["Event"] == "Comissioning Feeder #" + str(j+1), 'End_Date'] = comissioning_end

                remaining_installed_capacity = remaining_installed_capacity - remaining_installed_capacity
                j = j + 1

            manufacturing_start = manufacturing_start + pd.to_timedelta(batt_manu_duration, unit="w")


        pa = comissioning_end + pd.to_timedelta(delay_comm_pa, unit="w")

        df_2.loc[df_2["Event"] == "Guaranteed Provisional Acceptance", 'Start_Date'] = pa
        df_2.loc[df_2["Event"] == "Guaranteed Provisional Acceptance", 'End_Date'] = pa

        cod = pa + pd.to_timedelta(delay_pa_cod, unit="w")

        df_2.loc[df_2["Event"] == "Commercial Operation Date", 'Start_Date'] = cod
        df_2.loc[df_2["Event"] == "Commercial Operation Date", 'End_Date'] = cod

        fa = cod + pd.to_timedelta(delay_cod_fa, unit="w")

        df_2.loc[df_2["Event"] == "Final Acceptance", 'Start_Date'] = fa
        df_2.loc[df_2["Event"] == "Final Acceptance", 'End_Date'] = fa

        proj_milestones = ['Backfeed Available', 'Commercial Operation Date', 'Installation Completion']
        paym_milestones = ['PO Date', 'Drawing Confirmation Date', 'First FAT', 'First BESS loaded at Port of Export', 'Final FAT', 'SLOC Received by Prevalon', 'SLOC Received by the Buyer', 'Final Delivery of all DC Block Equipment', 'Guaranteed Delivery Completion Date', 'Guaranteed Provisional Acceptance', 'Final Acceptance']

        list = ['Acceptance', 'Commercial', 'Backfeed', 'Ready', 'Completion']

        for i in range(len(proj_milestones)):
            if any(item in proj_milestones[i] for item in list):
                proj_milestones_combined.append(proj_milestones[i])
            else:
                proj_milestones_combined.append(df_2['Scope'][0] + " | " + proj_milestones[i])

        for i in range(len(paym_milestones)):
            if any(item in paym_milestones[i] for item in list):
                paym_milestones_combined.append(paym_milestones[i])
            else:
                paym_milestones_combined.append(df_2['Scope'][0] + " | " + paym_milestones[i])
        
        # print(paym_milestones_combined)

        df_3 = pd.concat([df, df_2], ignore_index=True)

        list = ['Comissioning', 'Acceptance', 'Commercial', 'Backfeed', 'Ready', 'Installation', 'Commencement', 'Completion']

        for i in range(len(df_3)):
            if any(item in df_3.loc[i, 'Event'] for item in list):
                df_3.loc[i, 'Event'] = df_3.loc[i, 'Event']
            else:
                df_3.loc[i, 'Event'] = df_3.loc[i, 'Scope'] + " | " + df_3.loc[i, 'Event']

        
        new_row = pd.DataFrame({'Event': ['NTP'], 'Scope': ['Battery Supplier'], 'Start_Date': ntp, 'End_Date': ntp})


        df_3 = pd.concat([new_row, df_3], ignore_index=True)

        paym_milestones_combined.append('NTP')

        list = ['Drawing Confirmation', 'Manufacturing', 'Shipment', 'Installation', 'Comissioning']

        df_3['Event_Category'] = df_3['Event'].apply(lambda x: [event for event in list if event in x])
        

        for i in range(len(df_3)):
            if len(df_3.loc[i, 'Event_Category']) == 0:
                if any(item in df_3.loc[i, 'Event'] for item in proj_milestones_combined):
                    df_3.loc[i, 'Event_Category'] = "Project Milestone"
                if any(item in df_3.loc[i, 'Event'] for item in paym_milestones_combined):
                    df_3.loc[i, 'Event_Category'] = "Payment Milestone"
            else:
                df_3.loc[i, 'Event_Category'] = df_3.loc[i, 'Event_Category'][0]

        # print(df_3)

        return df_3, cod, first_fat, pcs_delivery_to_site, batt_delivery_to_site, paym_milestones_combined, proj_milestones_combined

    ntp = pd.Timestamp(ntp)
    intended_cod = pd.Timestamp(intended_cod)

    delay_comm_pa = 0
    batt_delay_shipment_installation = 0

    total_schedule_float = 0

    pcs_delay_fntp_po_date = 1
    batt_delay_fntp_po_date = 1
    batt_delay_shipment_installation = 1 # weeks
    initial_batt_delay_shipment_installation = batt_delay_shipment_installation
    comm_duration = 120 # 120 days per Feeder

    float_comm_duration = 0
    float_ship_duration = 0

    number_feeders = math.ceil(number_of_PCS/8)


    # PCS Supplier
    manufacturing_slot_size_pcs = 20
    number_manu_slots_pcs = math.ceil(number_of_PCS/manufacturing_slot_size_pcs)


    # Battery Supplier
    manufacturing_slot_size_batt = 20 #20 Enclosures per 2 weeks
    number_manu_slots_batt = math.ceil(number_of_containers/manufacturing_slot_size_batt)



    df_3, cod, first_fat, pcs_delivery_to_site, batt_delivery_to_site, paym_milestones_combined, proj_milestones_combined = create_schedule_table(pcs_delay_fntp_po_date, batt_delay_fntp_po_date, batt_delay_shipment_installation, comm_duration)

    
    # PCS are delivered atleast 4 weeks before batteries

    if batt_delivery_to_site - pd.to_timedelta(4, unit="w") < pcs_delivery_to_site:

        batt_delay_fntp_po_date = math.ceil((pcs_delivery_to_site - batt_delivery_to_site + pd.to_timedelta(5, unit="w")).days/7)

        df_3, cod, first_fat, pcs_delivery_to_site, batt_delivery_to_site, paym_milestones_combined, proj_milestones_combined = create_schedule_table(pcs_delay_fntp_po_date, batt_delay_fntp_po_date, batt_delay_shipment_installation, comm_duration)

    # If Intended COD is LATER than Calculated COD

    if intended_cod >= cod + pd.to_timedelta(7, unit="d"):
        total_schedule_float = math.floor((intended_cod - cod).days/7)
        remaining_schedule_float = total_schedule_float

        # Delay the PA by max 4 weeks
        
        if remaining_schedule_float > 0:
            float_comm_duration = min(4, remaining_schedule_float)
            comm_duration = comm_duration + float_comm_duration*7
        remaining_schedule_float = remaining_schedule_float - min(4, remaining_schedule_float)

        # Delay the Delay Shipment and Installation by max 4 weeks
        if remaining_schedule_float > 0:
            float_ship_duration = min(4, remaining_schedule_float)
            batt_delay_shipment_installation =  initial_batt_delay_shipment_installation + float_ship_duration
        remaining_schedule_float = remaining_schedule_float - min(4, remaining_schedule_float)

        # Delay the Delay PCS PO by rest of the weeks
        if remaining_schedule_float > 0:
            pcs_delay_fntp_po_date = remaining_schedule_float
            batt_delay_fntp_po_date = batt_delay_fntp_po_date + pcs_delay_fntp_po_date

        df_3, cod, first_fat, pcs_delivery_to_site, batt_delivery_to_site, paym_milestones_combined, proj_milestones_combined = create_schedule_table(pcs_delay_fntp_po_date, batt_delay_fntp_po_date, batt_delay_shipment_installation, comm_duration)

    # Label Installation Commencement and Completion as Project Milestones
    i = df_3.loc[df_3['Event'] == 'Installation Commencement'].iloc[0].name
    df_3.loc[i, "Event_Category"] = "Project Milestone"

    i = df_3.loc[df_3['Event'] == 'Installation Completion'].iloc[0].name
    df_3.loc[i, "Event_Category"] = "Project Milestone"

    # Filter based on Scope Chosen

    cust_mile_list = ['NTP', 'Battery Supplier | Drawing Confirmation Date', 'Battery Supplier | First FAT', \
                     'Site Ready to Accept Delivery', 'Delivery Commencement', 'Installation Commencement', 'Guaranteed Delivery Completion Date', 'Installation Completion', \
                        'Guaranteed Provisional Acceptance', 'Commercial Operation Date', 'Final Acceptance', 'Backfeed Available', 'Installation', 'Comissioning Feeder #' + str(number_feeders)]
    
    batt_mile_list = ['Battery Supplier | PO Date', 'Battery Supplier | Manufacturing', 'Battery Supplier | SLOC Received by Prevalon', 'Battery Supplier | SLOC Received by the Buyer', 'Battery Supplier | Drawing Confirmation Date', 'Battery Supplier | First FAT', \
                     'Battery Supplier | First BESS loaded at Port of Export', 'Battery Supplier | Shipment', 'Battery Supplier | Final Delivery of all DC Block Equipment', \
                        'Comissioning Feeder #' + str(number_feeders), 'Guaranteed Provisional Acceptance', 'Final Acceptance']
    
    pcs_mile_list = ['PCS Supplier | PO Date', 'PCS Supplier | Manufacturing', 'PCS Supplier | Shipment', 'PCS Supplier | First FAT', 'PCS Supplier | Guaranteed Delivery Date', \
                     'Guaranteed Provisional Acceptance']
    
    # print(paym_milestones_combined, proj_milestones_combined)
    if scope == "Customer Schedule":
        list = cust_mile_list

        for i in range(len(df_3)):
            # print(df_3.loc[i, 'Event'])
            if any(item in df_3.loc[i, 'Event'] for item in list):
                df_3.loc[i, 'Event'] = df_3.loc[i, 'Event']
            else:
                df_3 = df_3.drop(i)

        i = df_3.loc[df_3['Event'] == 'Comissioning Feeder #' + str(number_feeders)].iloc[0].name

        df_3.loc[i, "Event"] = "Comissioning"
        
        df_3 = df_3.sort_values(by=['Start_Date'], ascending=True)
    
    if scope == "Battery Supplier Schedule":
        list = batt_mile_list
        for i in range(len(df_3)):
            # print(df_3.loc[i, 'Event'])
            if any(item in df_3.loc[i, 'Event'] for item in list):
                df_3.loc[i, 'Event'] = df_3.loc[i, 'Event']
            else:
                df_3 = df_3.drop(i)

        i = df_3.loc[df_3['Event'] == 'Comissioning Feeder #' + str(number_feeders)].iloc[0].name

        df_3.loc[i, "Event"] = "Comissioning"
        # df_3 = df_3.sort_values(by=['End_Date'], ascending=True)
    
    if scope == "PCS Supplier Schedule":
        list = pcs_mile_list
        for i in range(len(df_3)):
            # print(df_3.loc[i, 'Event'])
            if any(item in df_3.loc[i, 'Event'] for item in list):
                df_3.loc[i, 'Event'] = df_3.loc[i, 'Event']
            else:
                df_3 = df_3.drop(i)
        df_3.reset_index(drop=True, inplace=True)
        i = len(df_3) - 1
        final_deli = df_3.loc[df_3['Event'] == 'PCS Supplier | Guaranteed Delivery Date']['Start_Date'].iloc[0]
        if cod > final_deli + pd.to_timedelta(60, unit="d"):
            df_3.loc[i, 'Event'] = '60 Days after Guaranteed Delivery Date'
            df_3.loc[i, 'Start_Date'] = final_deli + pd.to_timedelta(60, unit="d")
            df_3.loc[i, 'End_Date'] = final_deli + pd.to_timedelta(60, unit="d")
            paym_milestones_combined.append('60 Days after Guaranteed Delivery Date')

        # df_3 = df_3.sort_values(by=['End_Date'], ascending=True)
        
    df_3.reset_index(drop=True, inplace=True)


    custom_colors = {
        'Drawing Confirmation': 'rgb(245,225,164)',
        'Manufacturing': 'rgb(252,215,87)',
        'Shipment': 'rgb(99,102,106)',
        'Installation': 'rgb(208,211,240)',
        'Comissioning': 'rgb(72,49,120)',
        'Payment Milestone': 'rgb(252,215,87)',
        'Project Milestone': 'rgb(252,215,87)',
    }

    fig = px.timeline(df_3, x_start="Start_Date", x_end="End_Date", y="Event", color='Event_Category', color_discrete_map=custom_colors)

    fig.update_yaxes(categoryorder='array', categoryarray=df_3['Event'])
    fig.update_yaxes(autorange="reversed") # otherwise tasks are listed from the bottom up
    # Adjust bar height
    fig.update_traces(marker=dict(line=dict(width=0.5)), selector=dict(type='bar'))


    fig.add_trace(go.Scatter(
        x=df_3[df_3['Event'].isin(proj_milestones_combined)]["Start_Date"],
        y=df_3[df_3['Event'].isin(proj_milestones_combined)]["Event"],
        mode='markers',
        name='Project Milestones',
        marker=dict(size=10, color='orange', symbol='diamond'), showlegend=True))

    fig.add_trace(go.Scatter(
        x=df_3[df_3['Event'].isin(paym_milestones_combined)]["Start_Date"],
        y=df_3[df_3['Event'].isin(paym_milestones_combined)]["Event"],
        mode='markers',
        name='Payment Milestones',
        marker=dict(size=10, color='green', symbol='star'), showlegend=True))
    
    fig.update_layout(
        legend=dict(
            x=1,
            y=1,
            traceorder="reversed",
            title_font_family="Helvetica",
            font=dict(
                family="Helvetica",
                size=12,
                color="black"
            ),
            bordercolor="Black",
            borderwidth=2
        )
    )
    for trace in fig.data:
        if trace.name in proj_milestones_combined or trace.name in paym_milestones_combined or trace.name in ["Project Milestone", "Payment Milestone"]:  # Replace with the trace you want to remove
            trace.showlegend = False
        
    # fig.write_image("schedule_plot.png", height = 650, width=1400)

    # fig.write_image("plot-schedule.png", width=600, height=320)

    def months_diff(start_date, end_date):
        # Ensure start_date is before end_date
        if start_date > end_date:
            start_date, end_date = end_date, start_date

        # Calculate the difference in years and months
        year_diff = end_date.year - start_date.year
        month_diff = end_date.month - start_date.month

        # Total months difference
        total_months = year_diff * 12 + month_diff

        return total_months
    

    # Months from NTP to COD
    months_ntp_cod = str(months_diff(cod, ntp)) + " months"

    # Months from FAT to COD
    months_fat_cod = str(months_diff(cod, first_fat)) + " months"

    proj_schedule_stored = df_3.to_dict()

    if pcs_delay_fntp_po_date == 1:
        float_po_date = 0
    else:
        float_po_date = pcs_delay_fntp_po_date

    # Milestones Table
    df_milestones = pd.DataFrame([])
    for i in range(len(df_3)):
        if (df_3.loc[i, 'Event_Category'] == 'Payment Milestone') or (df_3.loc[i, 'Event_Category'] == 'Project Milestone'):
            df_milestones.loc[i, 'Event'] =  df_3.loc[i, 'Event']
            df_milestones.loc[i, 'Date'] = df_3.loc[i, 'Start_Date'].date()
    
    df_milestones.reset_index(drop=True, inplace=True)

    # Critical Durations Table
    df_critical_durations = pd.DataFrame([])
    # Suppliers - PO - Last Payment, PO to FAT, Delivery Window
    # Customer - NTP to FA, Installation Window, Commissioning and Testing Window

    durations_list = ['Total Project Duration', 'PCS Supplier Drawing Confirmation, Manufacturing and FAT', 'Battery Supplier Drawing Confirmation, Manufacturing and FAT', 'Total Transportation', 'Installation', 'Commissioning and Testing']
    durations_desc = ["From " + str(df_3.loc[0, "Event"]) + " to " + str(df_3.loc[len(df_3)-1, "Event"]), 'From PCS Supplier PO Date to FAT', 'From Battery Supplier PO Date to FAT','From First Shipment Leaving the Factory to Last Delivery to site', \
                      'From Installation Commencement to Installation Completion', 'From Installation Completion to PA']
    duration_weeks = []
    if "Supplier" in scope:
        durations_list.remove("Installation")
        durations_list.remove("Commissioning and Testing")

        durations_desc.remove('From Installation Commencement to Installation Completion')
        durations_desc.remove('From Installation Completion to PA')

        durations_desc[0] = "From PO Date" + " to " + str(df_3.loc[len(df_3)-1, "Event"])

        duration_weeks.append(math.ceil((df_milestones.loc[len(df_milestones)-1, "Date"] - df_milestones.loc[0, "Date"]).days/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"].str.contains("First FAT")]['Date'] - df_milestones.loc[0, "Date"]).iloc[0].days)/7))

        if "Battery" in scope:
            durations_list.remove("PCS Supplier Drawing Confirmation, Manufacturing and FAT")
            durations_desc.remove('From PCS Supplier PO Date to FAT')

            duration_weeks.append(math.ceil(((df_3.loc[df_3["Event"].str.contains("Final Delivery of all DC Block Equipment")]['End_Date'].iloc[0] - df_3.loc[df_3["Event"].str.contains("Shipment Batch #1")]['Start_Date'].iloc[0]).days)/7))
        if "PCS" in scope:
            durations_list.remove("Battery Supplier Drawing Confirmation, Manufacturing and FAT")
            durations_desc.remove('From Battery Supplier PO Date to FAT')

            duration_weeks.append(math.ceil(((df_3.loc[df_3["Event"].str.contains("Guaranteed Delivery")]['End_Date'].iloc[0] - df_3.loc[df_3["Event"].str.contains("Shipment Batch #1")]['Start_Date'].iloc[0]).days)/7))

    elif "Customer" in scope:
        durations_list.remove('PCS Supplier Drawing Confirmation, Manufacturing and FAT')
        durations_list.remove('Battery Supplier Drawing Confirmation, Manufacturing and FAT')

        durations_desc.remove('From PCS Supplier PO Date to FAT')
        durations_desc.remove('From Battery Supplier PO Date to FAT')
        
        durations_list[1] = "Delivery"
        durations_desc[1] = "From Delivery Commencement to Guaranteed Delivery Date"
        



        # duration_weeks = [0]*len(durations_list)

        duration_weeks.append(math.ceil((df_milestones.loc[len(df_milestones)-1, "Date"] - df_milestones.loc[0, "Date"]).days/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"].str.contains("Guaranteed Delivery Completion Date")]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"].str.contains("Delivery Commencement")]['Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"].str.contains("Installation Completion")]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"].str.contains("Installation Commencement")]['Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"].str.contains("Provisional Acceptance")]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"].str.contains("Installation Completion")]['Date'].iloc[0]).days)/7))
    
    else:
        duration_weeks.append(math.ceil((df_milestones.loc[len(df_milestones)-1, "Date"] - df_milestones.loc[0, "Date"]).days/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"] == "PCS Supplier | First FAT"]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"] == "PCS Supplier | PO Date"]['Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"] == "Battery Supplier | First FAT"]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"] == "Battery Supplier | PO Date"]['Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_3.loc[df_3["Event"] == "Guaranteed Delivery Completion Date"]['Start_Date'].iloc[0] - df_3.loc[df_3["Event"] == "PCS Supplier | Shipment Batch #1"]['Start_Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"] == "Installation Completion"]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"] == "Installation Commencement"]['Date'].iloc[0]).days)/7))
        duration_weeks.append(math.ceil(((df_milestones.loc[df_milestones["Event"] == "Guaranteed Provisional Acceptance"]['Date'].iloc[0] - df_milestones.loc[df_milestones["Event"] == "Installation Completion"]['Date'].iloc[0]).days)/7))


    df_critical_durations['Critical Durations'] = durations_list
    df_critical_durations['Weeks'] = duration_weeks
    df_critical_durations['Description'] = durations_desc

    # Float Table 
    df_floats = pd.DataFrame([])

    df_floats['Float Description'] = ['Float for Commissioning and Testing', 'Float for Guaranteed Delivery Date', 'Float for PCS Supplier PO', 'Total Project Schedule Float']
    df_floats['Float Duration (weeks)'] = [float_comm_duration, float_ship_duration, float_po_date, total_schedule_float]

    # Project Overview Table 
    df_proj_overview = pd.DataFrame([])

    df_proj_overview['Event Time Window'] = ['Months from NTP to PA', 'Months from Battery First FAT to PA']
    df_proj_overview['Duration'] = [months_ntp_cod, months_fat_cod]
    
    stored_fig_data = fig
    df_milestones_stored = df_milestones.to_dict()
    df_critical_durations_stored = df_critical_durations.to_dict()
    
    # Convert Dataframes to Tables
    df_milestones = table_format(df_milestones)
    df_critical_durations = table_format(df_critical_durations)
    df_floats = table_format(df_floats)
    df_proj_overview = table_format(df_proj_overview)



    return fig, stored_fig_data, cod.date(), proj_schedule_stored, df_milestones, df_milestones_stored, df_critical_durations, df_critical_durations_stored, df_floats, df_proj_overview
# scheduler(ntp, number_of_PCS, number_of_containers, manufacturing_slot_size_pcs, manufacturing_slot_size_batt, pcs_delay_ntp_fntp, pcs_delay_fntp_po_date, \
#               pcs_delay_po_date_dw_conf, pcs_dw_conf_duration, pcs_delay_dw_conf_manu, pcs_manu_duration, pcs_delay_manu_shipment, pcs_shipment_duration, \
#                 pcs_delay_shipment_installation, pcs_installation_duration, batt_delay_ntp_fntp, batt_delay_fntp_po_date, batt_delay_po_date_dw_conf, batt_dw_conf_duration, \
#                     batt_delay_dw_conf_manu, batt_manu_duration, batt_delay_manu_shipment, batt_shipment_duration, batt_delay_shipment_installation, \
#                         batt_installation_duration, delay_comm_installation, comm_duration, delay_comm_pa, delay_pa_cod, delay_cod_fa)