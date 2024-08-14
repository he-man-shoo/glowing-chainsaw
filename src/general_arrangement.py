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
import PyPDF2

from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import *
from datetime import date

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

    container_clearance_minimum = 12
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
        
        if orient == 3:
            """
            Draw an arrow on the canvas from (start_x, start_y) to (end_x, end_y).
            arrow_size determines the size of the arrowhead.
            """

            # Draw the main line
            c.line(x1, y1, x2, y2)

            # Draw the first arrowhead
            c.line(x1, y1, x1 + arrow_size, y1 + arrow_size/2)
            c.line(x1, y1, x1 + arrow_size, y1 - arrow_size/2)



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
            inner_block_length = (e_w_block_limit + 2*e_w_block_limit)*(container_length) + (e_w_block_limit*2)*pcs_clearance_short_end + (e_w_block_limit-1)*container_clearance_minimum + access_road_width/4
        
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
                
                # Container 1 and 2
                y = y_block_mid - container_width - container_clearance_minimum/2
                for i in range(2):
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + i)))
                    i = i + 1
                    y = y_block_mid + container_clearance_minimum/2

                x = x + container_length + pcs_clearance_short_end

                
                # PCS
                y = y_block_mid - pcs_width/2
                c.rect(x, y, pcs_length, pcs_width, fill=0)
                c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                x = x + pcs_length + pcs_clearance_short_end

                y = y_block_mid - container_width - container_clearance_minimum/2


                # Container 3 and 4
                for i in range(2):
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 2 + i)))
                    i = i + 1
                    y = y_block_mid + container_clearance_minimum/2

                x = x + container_length + container_clearance_minimum
        
            return x

        else:
            if block_type == 4:
                # Container 1 and 2
                y = y_block_mid - container_width - container_clearance_minimum/2
                for i in range(2):
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + i)))
                    i = i + 1
                    y = y_block_mid + container_clearance_minimum/2

                x = x + container_length + pcs_clearance_short_end

                
                # PCS
                y = y_block_mid - pcs_width/2
                c.rect(x, y, pcs_length, pcs_width, fill=0)
                c.drawCentredString(x + pcs_length/2, y + pcs_width/2 - 6*scaling_factor, "PCS #" +str(int(block_count)))

                x = x + pcs_length + pcs_clearance_short_end

                y = y_block_mid - container_width - container_clearance_minimum/2


                # Container 3 and 4
                for i in range(2):
                    c.rect(x, y, container_length, container_width, fill=0)
                    c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 2 + i)))
                    i = i + 1
                    y = y_block_mid + container_clearance_minimum/2

                x = x + container_length + container_clearance_minimum
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
                        
                        # if block_type > 3:
                        #     # Container
                        #     y = y_block_mid + container_clearance_minimum/2

                        #     c.rect(x, y, container_length, container_width, fill=0)
                        #     c.drawCentredString(x + container_length/2, y + container_width/2 - 6*scaling_factor, "Container #" +str(int(container_count + 3)))
                            
                        #     x = x + container_length + pcs_clearance_short_end

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
            inner_block_length = (e_w_block_limit + 2*e_w_block_limit)*(container_length) + (e_w_block_limit*2)*pcs_clearance_short_end + (e_w_block_limit - 1)*container_clearance_minimum + access_road_width/4
        
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
        
        if block_type == 4:
            x = x + pcs_clearance_short_end - container_clearance_minimum
            
        c.line(x, y, x, 1500)

        block_length = pcs_length + pcs_clearance_short_end + container_length
        if block_type > 2:
            block_length = block_length + container_clearance_minimum + container_length
        
        if block_type == 4:
            block_length = block_length + pcs_clearance_short_end - container_clearance_minimum

        # Block Length
        draw_arrow(c, x_start, 1500, x, 1500, 10*scaling_factor, 1)
        c.drawCentredString((x_start + x)/2, 1500 + 30*scaling_factor, dim(block_length, scaling_factor, "", ""))
        c.drawCentredString((x_start + x)/2, 1500 + 10*scaling_factor, "(BLOCK LENGTH TYP.)")
        
        # Block Clearance
        if block_type == 4:

            x = x + container_clearance_minimum
            c.line(x, y, x, 1500)
            
            draw_arrow(c, x, 1500, x + 20*scaling_factor, 1500, 10*scaling_factor, 3)
            c.drawString(x - container_clearance_minimum, 1500 + 20*scaling_factor, dim(container_clearance_minimum, scaling_factor, "", ""))
        
        else:
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

        if block_type == 4:
            c.line(x + container_length, y, 190, y)
        else:
            c.line(x + container_length + pcs_clearance_short_end, y, 190, y)

        y = y - 2*container_width - container_clearance_minimum
        
        if block_type == 4:
            c.line(x + container_length, y, 190, y)
        else:
            c.line(x + container_length + pcs_clearance_short_end, y, 190, y)

        # Block Width
        draw_arrow(c, 190, y, 190, y + 2*container_width + container_clearance_minimum, 10*scaling_factor, 2)
        draw_vertical_text(c, 190 - 10*scaling_factor, (y + (y + 2*container_width + container_clearance_minimum))/2, dim(2*container_width + container_clearance_minimum, \
                                                                                                scaling_factor, "", ""))

        if dual_row == 1:
            y = y - container_clearance_long_end

            if block_type == 4:
                c.line(x + container_length, y, 210, y)
            else:
                c.line(x + container_length + pcs_clearance_short_end, y, 210, y)

            # Block Clearance
            draw_arrow(c, 210, y, 210, y + container_clearance_long_end, 10*scaling_factor, 2)
            draw_vertical_text(c, 210 - 10*scaling_factor, (y + y + container_clearance_long_end)/2, dim(container_clearance_long_end, \
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



    pdf_path = "GA.pdf"
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

    def combine_pdfs(pdf_list, output_path):
        pdf_writer = PyPDF2.PdfWriter()

        for pdf in pdf_list:
            pdf_reader = PyPDF2.PdfReader(pdf)
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                pdf_writer.add_page(page)

        with open(output_path, 'wb') as output_pdf:
            pdf_writer.write(output_pdf)

    batt_block_string = "Block Type " + str(int(block_type)) + ".pdf"


    # List of PDF files to combine
    pdf_list = [batt_block_string, 'GA.pdf']
    pdf_path = "General Arrangement Diagram" + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"

    combine_pdfs(pdf_list, pdf_path)

    return pdf_path