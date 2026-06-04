# =========================================================
#
# PROCESSOR OFFENE POSTEN  05.26
#
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import uuid
import pandas as pd
from datetime import date, datetime, timedelta
import win32com.client as win32com
import pythoncom
from pretty_html_table import build_table


class OffenePostenProcessor(BaseProcessor):

    name = "OffenePosten Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei",type=["xlsx"])
        Kundeliste = st.file_uploader("Kundeliste",type=["xlsx"])
        
        return {
            "Datendatei": Datendatei,
            "Kundeliste": Kundeliste,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        Kundeliste = data["Kundeliste"]
        output_files = []
#---
        #--------------------------
        min_date_str = "2025-12-31"
        days_to_add = -3
        y_sheet1 = 'Sheet1'
        y_sheet2 = 'Sheet2'

        current_date = date.today() + timedelta(days=days_to_add)
        min_date = datetime.strptime(min_date_str, "%Y-%m-%d").date()

        #---Datendatei---------------------------------------------------------------------------------------------------
        df = pd.read_excel(Datendatei, header=1)
        result = df[(df['Fälligkeit'].dt.date  < current_date) & (df['Fälligkeit'].dt.date  > min_date) & (df['Restbetrag'] > 0)]

        #---Kundeliste-----------------------------------------------------------------------------------------------------
        dfY1 = pd.read_excel(Kundeliste, sheet_name=y_sheet1, header=0)
        dfY2 = pd.read_excel(Kundeliste, sheet_name=y_sheet2, header=0)

        #---Bearbeitung-----------------------------------------------------------------------------------------------------
        result = result.merge(dfY1, on=['Kto.'], how='left')
        result = result[(result['Check'] != 'N')]
        result = result.merge(dfY2, on=['Mahn_Number'], how='left')

        result = result[['Belegdat.','Fälligkeit','Belegnr.','OP-Betrag','Restbetrag','Kto.','Kto.-Name','Kunde_mail','Mahn_Schreibung']]
        result['Belegdat.'] = result['Belegdat.'].dt.date
        result['Fälligkeit'] = result['Fälligkeit'].dt.date
        result = result.sort_values(['Kto.'], ascending=[True])
        
        #---result_SPoint---------------------------------------------------------------------------------------------
        result_SPoint = df.merge(dfY1, on=['Kto.'], how='left')
        result_SPoint = result_SPoint[['Belegdat.','Fälligkeit','Belegnr.','OP-Betrag','Restbetrag','Kto.','Kto.-Name', 'Owner']]
        result_SPoint['Belegdat.'] = result_SPoint['Belegdat.'].dt.date
        result_SPoint['Fälligkeit'] = result_SPoint['Fälligkeit'].dt.date
        result_SPoint['DatumAnpassen_' + current_date.strftime('%Y-%m-%d')] = result_SPoint['Fälligkeit'] - current_date
        result_SPoint = result_SPoint.sort_values(['DatumAnpassen_' + current_date.strftime('%Y-%m-%d')], ascending=[True])                       

        #---to_excel---------------------------------------------------------------------------------------------------------    
        os.makedirs("results", exist_ok=True)
        
        output_file1 = f"results/OffenePosten_{uuid.uuid4()}.xlsx"
        result.to_excel(output_file1, index=False)
        
        output_file2 = f"results/OffenePosten_SPoint_{uuid.uuid4()}.xlsx"
        result_SPoint.to_excel(output_file2, index=False)
        
        output_files.append(output_file1)
        output_files.append(output_file2)
        

        #---Outlook----------------------------------------------------------
        pythoncom.CoInitialize()
        outlook = win32com.DispatchEx('Outlook.Application')
        
        #---Signature--------------------------------------------------------
        with open(r'C:\Users\garry\AppData\Roaming\Microsoft\Signatures\is.htm', 'r', encoding='MacCyrillic') as f:
            signature_htm = f.read()
                      
        #---Grouped_by_kto  &  Columns_to_include--------------------
        grouped_by_kto = result.groupby('Kto.')
        columns_to_include = ['Kto.-Name','Belegdat.','Fälligkeit','Belegnr.','OP-Betrag','Restbetrag']

        #---Per alle Kto-------------------------------------------------------
        protocol = []
        for kto, item in grouped_by_kto:  
            if len(item) > 0:
                
        #---Daten--------------------------------------------------------------
                table_html = build_table(item[columns_to_include], 'blue_dark', width='800px', font_size='small', font_family='Calibri')       
                ms_html =  item['Mahn_Schreibung'].iloc[0].replace('\n', '<br>') if pd.notna(item['Mahn_Schreibung'].iloc[0]) else ''
                kunde_mail = item['Kunde_mail'].iloc[0]       
                html_body = f"""<html><head></head><body>{ms_html}<br><br><p>{table_html}<br><br></p>{signature_htm}</body></html>"""
                
        #---Mail-----------------------------------------------------------------
                mail = outlook.CreateItem(0)
                mail.To = kunde_mail
                mail.Subject = 'Mahnung'
                mail.HTMLBody  = html_body
                
                if pd.isna(ms_html) or not str(ms_html).strip() or pd.isna(kunde_mail) or not str(kunde_mail).strip():                    
                    protocol.append([f'❌ {kto}', f'{item['Kto.-Name'].iloc[0]}', f'displayet: kunde_mail fehlt!'])
                    mail.Display(False)
                else:
                    protocol.append([f'✔️ {kto}', f'{item['Kto.-Name'].iloc[0]}', f'gesendet'])
                    mail.Send() 
#---
        st.dataframe(pd.DataFrame(protocol, columns=['Kto.', 'Kto.-Name', 'Ergebnis']))
        
        return output_files


    
 
