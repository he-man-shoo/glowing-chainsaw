import pandas as pd
from datetime import datetime

def schedule_excel_op(proj_schedule_stored, scope):

    df = pd.DataFrame(data=proj_schedule_stored)
    df.reset_index(drop=True, inplace=True)

    for i in range(len(df)):
            df.loc[i, "Start_Date"] = df.loc[i, "Start_Date"][:10] # first 10 characters of the string
            df.loc[i, "End_Date"] = df.loc[i, "End_Date"][:10] # first 10 characters of the string

    df = df.loc[(df['Event_Category'] == "Payment Milestone") | (df['Event_Category'] == "Project Milestone")]

    df.drop(columns=['Start_Date', 'Scope'], inplace=True)

    df.rename(columns={'End_Date': 'Date'}, inplace=True)

    df.reset_index(drop=True, inplace=True)
    
    if scope == "Full Project Schedule":
        # If COD is 60 days after PCS Delivery, final payment of PCS Supplier is "60 Days after Final Delivery"
        cod = datetime.strptime(df.loc[df['Event'] == 'Commercial Operation Date']['Date'].iloc[0], "%Y-%m-%d")
        final_deli = datetime.strptime(df.loc[df['Event'] == 'PCS Supplier | Final Delivery of all PCS Equipment']['Date'].iloc[0], "%Y-%m-%d")

        pcs_final_payment = final_deli + pd.to_timedelta(60, unit="d")
        

        if cod > pcs_final_payment:
                # New row to insert
                new_row = {'Event':'PCS Supplier | 60 Days after Final Delivery of all PCS Equipment', 'Date':str(pcs_final_payment)[:10], 'Event_Category':"Payment Milestone"}
                # Convert the new row to a DataFrame
                new_row_df = pd.DataFrame([new_row])
                # Specify the index where you want to insert the new row
                index = 7

                # Split the DataFrame into two parts and insert the new row
                df1 = df.iloc[:index]
                df2 = df.iloc[index:]
                df = pd.concat([df1, new_row_df, df2]).reset_index(drop=True)

        df['Event'] = df['Event'].replace(' | ', ' ', regex=True)
    
    return df