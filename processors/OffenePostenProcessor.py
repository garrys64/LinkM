# =========================================================
#
# PROCESSOR OFFENE POSTEN  05.26
#
# =========================================================

from processors.BaseProcessor import BaseProcessor
from datetime import date, datetime, timedelta
from pretty_html_table import build_table
from email.message import EmailMessage

import streamlit as st
import os
import re
import uuid
import pandas as pd
import smtplib


class OffenePostenProcessor(BaseProcessor):

    name = "OffenePosten Processor"
    
    EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    MIN_DATE_STR = "2025-12-31"
    DAYS_TO_ADD = -3
    Y_SHEET1 = 'Sheet1'
    Y_SHEET2 = 'Sheet2'
    EMAIL_FROM_NAME = 'garrys64001@web.de'    
    EMAIL_FROM_PASSWORD = st.secrets.WEB_PASS  #В интерфейсе Streamlit Cloud: > Settings > Secrets > WEB_PASS=....     
    SMTP_NAME = 'smtp.web.de'
    SMTP_PORT = 465

   
#--------------------------
    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei",type=["xlsx"])
        Kundeliste = st.file_uploader("Kundeliste",type=["xlsx"])
        
        email_editor = None
        if Datendatei is not None and Kundeliste is not None:
            try:
                result, _, _ = self._prepare_data(Datendatei, Kundeliste)
                email_editor = self._render_email_editor(result)
            except Exception as e:
                st.warning(f"Email editor konnte nicht geladen werden: {e}")

        return {
            "Datendatei": Datendatei,
            "Kundeliste": Kundeliste,
            "email_editor": email_editor,
        }

#--------------------------
    def process(self, data):

        Datendatei = data["Datendatei"]
        Kundeliste = data["Kundeliste"]
        email_editor = data["email_editor"]
        output_files = []

        result, result_SPoint, kundeliste_sheets = self._prepare_data(Datendatei, Kundeliste)
        result = self._apply_email_editor(result, email_editor)
        kundeliste_sheets[self.Y_SHEET1] = self._apply_email_editor(kundeliste_sheets[self.Y_SHEET1], email_editor)

        #--- save output_files ----------------------------------------------------
        os.makedirs("results", exist_ok=True)

        output_file1 = f"results/OffenePosten_{uuid.uuid4()}.xlsx"
        result.to_excel(output_file1, index=False)
        output_file2 = f"results/OffenePosten_SPoint_{uuid.uuid4()}.xlsx"
        result_SPoint.to_excel(output_file2, index=False)
        output_file3 = f"results/OP_Einstellungen_updated_{uuid.uuid4()}.xlsx"
                
        with pd.ExcelWriter(output_file3, engine="openpyxl") as writer:
            for sheet_name, sheet_df in kundeliste_sheets.items():
                sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)

        output_files.append(output_file1)
        output_files.append(output_file2)
        output_files.append(output_file3)

        protocol = self._send_grouped_emails(result, data)
        st.dataframe(pd.DataFrame(protocol, columns=['Kto.', 'Kto.-Name', 'Ergebnis']))

        return output_files
        
#--------------------------        
    def _send_grouped_emails(self, result, data):                  
        
        #---Grouped_by_kto ---
        
        grouped_by_kto = result.groupby('Kto.')
        columns_to_include = ['Kto.-Name','Belegdat.','Fälligkeit','Belegnr.','OP-Betrag','Restbetrag']

        #---Per alle Kto ---
        
        signature_htm = ''
        protocol = []
        
        for kto, item in grouped_by_kto:  
            if len(item) > 0:
                
        #---Mail---
                table_html = build_table(item[columns_to_include], 'blue_dark', width='800px', font_size='small', font_family='Calibri')       
                ms_html =  item['Mahn_Schreibung'].iloc[0].replace('\n', '<br>') if pd.notna(item['Mahn_Schreibung'].iloc[0]) else ''
                kunde_mail = item['Kunde_mail'].iloc[0]       
                html_body = f"""<html><head></head><body>{ms_html}<br><br><p>{table_html}<br><br></p>{signature_htm}</body></html>"""
                
                if pd.isna(ms_html) or not str(ms_html).strip() or pd.isna(kunde_mail) or not str(kunde_mail).strip():                    
                    protocol.append([f'❌ {kto}', f'{item['Kto.-Name'].iloc[0]}', f'warn: kunde_mail fehlt!'])
                else:
                    protocol.append([f'✔️ {kto}', f'{item['Kto.-Name'].iloc[0]}', f'gesendet'])                    
                
                    msg = EmailMessage()
                    msg['From'] = self.EMAIL_FROM_NAME
                    msg['To'] = kunde_mail
                    msg['Subject'] = 'subject'
                    msg.set_content(html_body, subtype='html')
                    
                    with smtplib.SMTP_SSL(self.SMTP_NAME, 465) as server:
                        server.login(self.EMAIL_FROM_NAME, st.secrets.WEB_PASS)              
                        server.send_message(msg)
                           
        return protocol
        
#--------------------------
    def _prepare_data(self, Datendatei, Kundeliste):
        
        current_date = date.today() + timedelta(days=self.DAYS_TO_ADD)
        min_date = datetime.strptime(self.MIN_DATE_STR, "%Y-%m-%d").date()

        #---Datendatei---------------------------------------------------------------------------------------------------
        df = pd.read_excel(Datendatei, header=1)
        df = self._normalize_columns(df)
        result = df[(df['Fälligkeit'].dt.date < current_date) & (df['Fälligkeit'].dt.date > min_date) & (df['Restbetrag'] > 0)]

        #---Kundeliste-----------------------------------------------------------------------------------------------------
        dfY1 = pd.read_excel(Kundeliste, sheet_name=self.Y_SHEET1, header=0)
        dfY2 = pd.read_excel(Kundeliste, sheet_name=self.Y_SHEET2, header=0)
        kundeliste_sheets = {
            self.Y_SHEET1: dfY1.copy(),
            self.Y_SHEET2: dfY2.copy(),
        }

        #---Bearbeitung-----------------------------------------------------------------------------------------------------
        result = result.merge(dfY1, on=['Kto.'], how='left')
        result = result[(result['Check'] != 'N')]
        result = result.merge(dfY2, on=['Mahn_Number'], how='left')

        result = result[['Belegdat.', 'Fälligkeit', 'Belegnr.', 'OP-Betrag', 'Restbetrag', 'Kto.', 'Kto.-Name', 'Kunde_mail', 'Mahn_Schreibung']]
        result['Belegdat.'] = result['Belegdat.'].dt.date
        result['Fälligkeit'] = result['Fälligkeit'].dt.date
        result = result.sort_values(['Kto.'], ascending=[True])

        #---result_SPoint---------------------------------------------------------------------------------------------
        result_SPoint = df.merge(dfY1, on=['Kto.'], how='left')
        result_SPoint = result_SPoint[['Belegdat.', 'Fälligkeit', 'Belegnr.', 'OP-Betrag', 'Restbetrag', 'Kto.', 'Kto.-Name', 'Owner']]
        result_SPoint['Belegdat.'] = result_SPoint['Belegdat.'].dt.date
        result_SPoint['Fälligkeit'] = result_SPoint['Fälligkeit'].dt.date
        result_SPoint['DatumAnpassen_' + current_date.strftime('%Y-%m-%d')] = result_SPoint['Fälligkeit'] - current_date
        result_SPoint = result_SPoint.sort_values(['DatumAnpassen_' + current_date.strftime('%Y-%m-%d')], ascending=[True])

        return result, result_SPoint, kundeliste_sheets

#--------------------------
    def _render_email_editor(self, result):

        recipients = (
            result[['Kto.', 'Kto.-Name', 'Kunde_mail']]
            .drop_duplicates(subset=['Kto.'])
            .sort_values(['Kto.'])
            .reset_index(drop=True)
        )
        recipients['Kunde_mail'] = recipients['Kunde_mail'].fillna('').astype(str)
        recipients['Email_ok'] = recipients['Kunde_mail'].apply(self._is_valid_email)

        st.subheader("Email editor")
        st.caption("Are all email valid ?")

        edited = st.data_editor(
            recipients,
            hide_index=True,
            width="stretch",
            column_config={
                "Kto.": st.column_config.TextColumn("Kto.", disabled=True),
                "Kto.-Name": st.column_config.TextColumn("Kto.-Name", disabled=True),
                "Kunde_mail": st.column_config.TextColumn("Kunde_mail"),
                "Email_ok": st.column_config.CheckboxColumn("Email ok", disabled=True),
            },
        )
        edited['Email_ok'] = edited['Kunde_mail'].fillna('').astype(str).apply(self._is_valid_email)
        invalid_count = len(edited[~edited['Email_ok']])
        if invalid_count:
            st.warning(f"{invalid_count} invalid email")
        else:
            st.success("All email are valid !")

        return edited
        
#--------------------------                
    def _is_valid_email(self, value):

        if pd.isna(value):
            return False
        return bool(self.EMAIL_RE.match(str(value).strip()))

#--------------------------
    def _normalize_columns(self, df):

        return df.rename(columns={
            "FГ¤lligkeit": "Fälligkeit",
        })
    
#-------------------------- 
    def _apply_email_editor(self, df, email_editor):

        if email_editor is None or 'Kto.' not in df.columns or 'Kunde_mail' not in df.columns:
            return df

        edited = pd.DataFrame(email_editor)
        if edited.empty:
            return df

        email_map = edited.set_index('Kto.')["Kunde_mail"].to_dict()
        df = df.copy()
        df["Kunde_mail"] = df["Kto."].map(email_map).combine_first(df["Kunde_mail"])
        return df
        
#--------------------------