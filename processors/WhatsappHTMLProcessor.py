# =========================================================
#
# PROCESSOR WhatsappHTMLProcessor
# 
# =========================================================

#pip install python-calamine
from weasyprint import HTML
import time
from processors.BaseProcessor import BaseProcessor
import streamlit as st
from io import BytesIO
import pandas as pd
from html import escape
import zipfile


class WhatsappHTMLProcessor(BaseProcessor):

    name = "WhatsappHTML Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei", type=["xlsx"])
        Preisliste = st.file_uploader("Preisliste", type=["xlsx","xlsm"])
        
        xFormat = st.radio("Format:", ["HTML", "PDF", "ZIP"])
        
        return {
            "Datendatei": Datendatei,
            "Preisliste": Preisliste,
            "xFormat": xFormat,
        }

    def process(self, data):
        e_time = time.time()  # Засекаем время начала 


        Datendatei = data["Datendatei"]
        Preisliste = data["Preisliste"]
        xFormat = data["xFormat"]
        
        zip_buffer = BytesIO()

#---
        #df = pd.read_parquet(Datendatei)
        df = pd.read_excel(Datendatei, usecols=['WABA', 'WABA_NAME', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'AMOUNT'], engine="calamine")

        df2 = pd.read_excel(Preisliste, usecols=['WABA', 'GRUNDPREIS', 'PAKETDE', 'RABBAT(%)', 'GEBUR_TEMPLATE', 'GEBUR_SERVICE'], engine="calamine")

        df2["GRUNDPREIS"] = df2["GRUNDPREIS"].fillna(0)
        df2["PAKETDE"] = df2["PAKETDE"].fillna(0)
        df2["RABBAT(%)"] = df2["RABBAT(%)"].fillna(0)
        df2["GEBUR_TEMPLATE"] = df2["GEBUR_TEMPLATE"].fillna(0)
        df2["GEBUR_SERVICE"] = df2["GEBUR_SERVICE"].fillna(0)
            
        
        def money(value):
            return f"{value:.4f}"


        html0 = """
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">

        <title>Pricing Report</title>

        <style>

        body {
            font-family: Arial, sans-serif;
            font-size: 10px;
        } 
        
        details {
            margin: 5px 0 5px 5px;
        }        
        .category {
            font-style: italic;
            color: #003366;
        }
        .country {
            color: #333;
        }

        table {
            border-collapse: collapse;
            margin: 10px 0 10px 25px;
        }

        td, th {
            border: 1px solid #ccc;
            padding: 5px 15px;
        }

        th {
            background: #eee;
        }

        .messages {
          color: #5F718C;
          text-align: right;
        }
        .col_name {
          color: #5F718C;
          text-align: left;
        }
        .amount {
          color: #8B5A2B;    
          font-weight: bold;  
          text-align: right;
        }
        </style>

        </head>

        <body>

        <h2>WhatsApp Report</h2>
        
        <div style="display: grid; grid-template-columns: 215px 50px 75px 75px 50px 50px 30px 80px; font-weight: bold; background-color: #f0f0f0; border-bottom: 2px solid #333;">
            <span style="text-align: left;">Name</span>
            <span style="text-align: right;">Messages</span>
            <span style="text-align: right;">Amount</span>
            <span style="text-align: right;">Tr_gebur</span>
            <span style="text-align: right;">Gr.preis</span>
            <span style="text-align: right;">Paket</span>
            <span style="text-align: right;">(%)</span>
            <span style="text-align: right;">Total</span>
        </div>
        
        """
        html = html0
        sMessages = 0
        sAmount = 0.0
        sTr_gebur = 0.0
        sGrundpreis = 0.0
        sPaketDE = 0.0
        sTotal = 0.0
        
        # ---------- WABA_NAME ----------
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:

            for waba_name, waba_df in df.groupby("WABA_NAME"):
            #--
                mask = df2["WABA"] == waba_df["WABA"].iloc[0]
                matches = df2.index[mask]
                if len(matches) == 0:
                    continue                    
                ind = df2.index.get_loc(matches[0])
            #--        
        
                waba_messages = 0
                waba_amount = 0            
                tr_gebur0 = 0
                
                for category0, cat_df0 in waba_df.groupby("PRICING_CATEGORY"):

                    if category0 == "referral_conversion": 
                        continue
                        
                    cat_messages0 = cat_df0["MESSAGES"].sum()
                    waba_messages = waba_messages + cat_messages0 
                    
                    waba_amount0 = cat_df0["AMOUNT"].sum()
                    waba_amount = waba_amount + waba_amount0
                    
                    if category0 == "service": 
                        tr_gebur0 = tr_gebur0 + cat_messages0 * df2["GEBUR_SERVICE"].iloc[ind]
                    else:
                        tr_gebur0 = tr_gebur0 + cat_messages0 * df2["GEBUR_TEMPLATE"].iloc[ind]
                        
                        

                total = (waba_amount + tr_gebur0 + df2["GRUNDPREIS"].iloc[ind] + df2["PAKETDE"].iloc[ind]) * (1 - df2["RABBAT(%)"].iloc[ind] / 100)
                
                sMessages = sMessages + waba_messages
                sAmount = sAmount + waba_amount
                sTr_gebur = sTr_gebur + tr_gebur0
                sGrundpreis = sGrundpreis + df2["GRUNDPREIS"].iloc[ind]
                sPaketDE = sPaketDE + df2["PAKETDE"].iloc[ind]
                sTotal = sTotal + total
                
                html += f"""
                
                <details>
                <summary class="waba_name" style="list-style: none;">
                <div style="display: grid; grid-template-columns: 210px 50px 75px 75px 50px 50px 30px 80px; font-weight: bold; >
                <span class="col_name">{escape(waba_name)}</span>
                <span class="messages">{waba_messages}</span>
                <span class="amount">{money(waba_amount)}</span>
                <span class="amount">{money(tr_gebur0)}</span>
                <span class="amount">{df2["GRUNDPREIS"].iloc[ind]}</span>
                <span class="amount">{df2["PAKETDE"].iloc[ind]}</span>
                <span class="amount">{df2["RABBAT(%)"].iloc[ind]}</span>
                <span class="amount">{money(total)}</span>
                </div>
                </summary>

                """

                if xFormat == "HTML" or xFormat == "ZIP":
                # ---------- CATEGORY ----------

                    for category, cat_df in waba_df.groupby("PRICING_CATEGORY"):
                    
                        if category == "referral_conversion": 
                            continue

                        cat_messages = cat_df["MESSAGES"].sum()
                        cat_amount = cat_df["AMOUNT"].sum()
                            
                        if category == "service": 
                            tr_gebur = cat_messages * df2["GEBUR_SERVICE"].iloc[ind]
                        else:
                            tr_gebur = cat_messages * df2["GEBUR_TEMPLATE"].iloc[ind]

                        html += f"""
                        <details>
                        <summary class="category">
                        {escape(category)}
                        |
                        Messages: <span class="messages">{cat_messages}</span>
                        |
                        Amount: <span class="amount">{money(cat_amount)}</span>
                        |
                        Tr_gebur: <span class="amount">{money(tr_gebur)}</span>
                        </summary>
                        
                        <table>
                        <tr>
                            <th>Country</th>
                            <th>Messages</th>
                            <th>Amount</th>
                        </tr>
                        """
                        
                        # ---------- COUNTRY ----------

                        for country, country_df in cat_df.groupby("COUNTRY"):
                            country_messages = country_df["MESSAGES"].sum()
                            country_amount = country_df["AMOUNT"].sum()

                            html += f"""
                            <tr>
                                <td>{country}</td>
                                <td class="messages">{country_messages}</td>
                                <td class="amount">{money(country_amount)}</td>
                            </tr>
                            """
                        html += """
                        </table>

                        </details>
                        """
                html += """
                </details>
                </body>
                </html>
                """
                if xFormat == "ZIP":
                    buffer = BytesIO()
                    HTML(string=html.encode("utf-8")).write_pdf(buffer)
                    zip_file.writestr(f"{waba_name}.pdf", buffer.getvalue())
                    html = html0
                
            if xFormat == "HTML" or xFormat == "PDF":
                html += f"""
                <div style="display: grid; grid-template-columns: 215px 50px 75px 75px 50px 50px 30px 80px; font-weight: bold; background-color: #f0f0f0; border-top: 2px solid #333;">
                    <span style="text-align: left;">GESAMT</span>
                    <span style="text-align: right;">{sMessages}</span>  
                    <span style="text-align: right;">{money(sAmount)}</span>
                    <span style="text-align: right;">{money(sTr_gebur)}</span>
                    <span style="text-align: right;">{sGrundpreis}</span>
                    <span style="text-align: right;">{sPaketDE}</span>
                    <span style="text-align: right;">-</span>
                    <span style="text-align: right;">{money(sTotal)}</span>
                </div>
                </body>
                </html>
                """
        #---    
                if xFormat == "HTML":
                    buffer = BytesIO(html.encode("utf-8"))
                    buffer.seek(0)
                    data = {"df": buffer,"filename":  f"{Datendatei.name}.html", "mime": "text/html; charset=utf-8"}
                    
                if xFormat == "PDF":
                    buffer = BytesIO()
                    HTML(string=html.encode("utf-8")).write_pdf(buffer)
                    buffer.seek(0)
                    data = {"df": buffer,"filename":  f"{Datendatei.name}.pdf", "mime": "application/pdf"}
                           
                    
            if xFormat == "ZIP":
                buffer.seek(0)
                data = {"df": zip_buffer, "filename":  f"{Datendatei.name}.zip", "mime": "application/zip"}
            
            st.write(f"Time : {time.time() - e_time:.2f}" )

        return data


    
 
