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

    
    
    pdf_path = "SLD.pdf" 
    c = canvas.Canvas(pdf_path, pagesize=landscape(A1))

    x_start = 100
    y_start = 1200



    x_start_block = x_start
    y_start_block = y_start


    x = x_start_block
    y = y_start_block


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

    if RMU_req == "Yes":
        batt_block_string = str(block_type) + "_RMU_SLD.pdf"
    else:
        batt_block_string = str(block_type) + "_SLD.pdf"


    # List of PDF files to combine
    pdf_list = ['SLD.pdf', batt_block_string]
    pdf_path = "Single Line Diagram" + str(proj_name) + ", " + str(proj_location) + ", "+ str('{:,.2f}'.format(power_req)) + "MW_"+ str('{:,.2f}'.format(power_req*duration)) + "MWh.pdf"

    combine_pdfs(pdf_list, pdf_path)

    return pdf_path