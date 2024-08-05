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


def create_tech_proposal(proj_location, proj_name, power_req, duration, project_life, fig, bill_of_materials, design_summary, losses_table, \
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

        # content.append(PageBreak())

        # content.append(Paragraph("6. BESS AC Block Arrangement", section_paragraph_style))
        # content.append(Paragraph("<br/><br/>", style_normal))

        # # Add image to PDF
        # content.append(PlatypusImage(str(block_type) + '.png', width=456, height=600))
        
        doc.build(content, header, header)
        # Return the URL for the download link
        return pdf_file
