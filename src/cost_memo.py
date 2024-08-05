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
