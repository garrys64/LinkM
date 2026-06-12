# =========================================================
#
# PROCESSOR BwiProcessor
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import uuid
import pandas as pd
from pathlib import Path
import html
import re

DEFAULT_PRICE = 0.063
DEFAULT_GR = "LG 3"
TEXT_GR = "Message Fees, BWI GmbH (SMS/bwi02/GwBw), SMS-Versand "

class BwiProcessor(BaseProcessor):

    name = "BwiProcessor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei",type=["xlsx","xls"])
        Preisliste = st.file_uploader("Preisliste",type=["xlsx"])
        
        return {
            "Datendatei": Datendatei,
            "Preisliste": Preisliste,
        }

    def process(self, data):

        datendatei = data["Datendatei"]
        preisliste = data["Preisliste"]
        output_files = []
               
        DEFAULT_PRICE = 0.063
        DEFAULT_GR = "LG 3"
        TEXT_GR = "Message Fees, BWI GmbH (SMS/bwi02/GwBw), SMS-Versand "

#---

        def normalize_country(value):
            return str(value or "").strip().casefold()

        def get_message_route(value):
            text = html.unescape(str(value or "")).strip()
            return re.sub(r"^\s*SMS-MT\s*/\s*", "", text, flags=re.IGNORECASE)

        def extract_country(value):
            route = get_message_route(value)
            return re.split(r"\s*-\s*", route, maxsplit=1)[0].strip()

        def extract_germany_price_key(value, germany_price_keys):
            route = get_message_route(value)
            parts = re.split(r"\s*-\s*", route, maxsplit=1)
            if not parts or normalize_country(parts[0]) != "germany":
                return None
            if len(parts) == 1:
                return "Germany"

            provider_text = normalize_country(parts[1])
            for price_key in germany_price_keys:
                provider_key = price_key.split("-", 1)[1].strip()
                if normalize_country(provider_key) in provider_text:
                    return price_key

            return "Germany"


        def get_price_key(value, germany_price_keys):
            country = extract_country(value)
            if normalize_country(country) == "germany":
                return extract_germany_price_key(value, germany_price_keys)
            return country    

#--------------------
     
        prices_df = pd.read_excel(preisliste)
        z1_df = pd.read_excel(datendatei,header=None,  nrows=4)   #заголовок первые 4 строки 
        
        data_df1 = pd.read_excel(datendatei, thousands='.', skiprows=4, header=0)   #пропускаем первые 4 строки               
        data_df = data_df1.iloc[:-7]   #удаляем последние 7 строк

        prices = {
            normalize_country(row["Country"]): row["Preis"]
            for _, row in prices_df.iterrows()
        }
        groups = {
            normalize_country(row["Country"]): row["Gruppe"]     
            for _, row in prices_df.iterrows()
        }
        germany_price_keys = [
            str(country).strip()
            for country in prices_df["Country"]
            if normalize_country(country).startswith("germany-")
        ]

        price_keys = data_df["Buchungstext"] .apply(lambda text: get_price_key(text, germany_price_keys))    
        data_df["Einzelpreis"] = price_keys.apply(lambda price_key: prices.get(normalize_country(price_key), DEFAULT_PRICE))
        data_df["Gesamtpreis"] =data_df["Anzahl"]* data_df["Einzelpreis"]
        data_df["Bezeichnung"] = price_keys.apply(lambda price_key: f"{TEXT_GR}{groups.get(normalize_country(price_key), DEFAULT_GR)}")    
        data_df["Pos."] = range(1, len(data_df) + 1)
        data_df["Buchungsart"] = 'Message Fee'
        data_df["Produktcode"] = '4422'
        
        sum_data_df = data_df.groupby(['Bezeichnung']).agg({
            'Bezeichnung': 'first',  # или 'last'                   
            'Anzahl': 'sum',
            'Gesamtpreis': 'sum'   
        })
        total_sum = sum_data_df['Gesamtpreis'].sum()
        total_Anzahl = sum_data_df['Anzahl'].sum()
        total_sum_data_df = pd.DataFrame({'-': ['Total:'],'--': [total_Anzahl],'---': [total_sum]})

        # Порядок столбцов для вывода
        data_df = data_df[['Pos.', 'Buchungsart', 'Buchungstext', 'Produktcode', 'Bezeichnung', 'Anzahl', 'Einzelpreis', 'Gesamtpreis']]

        os.makedirs("results", exist_ok=True)
        output_file = f"results/BWI_{uuid.uuid4()}.xlsx"
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            z1_df.to_excel(writer, sheet_name='Report', index=False, startrow=0, startcol=0, header=False)
            data_df.to_excel(writer, sheet_name='Report', index=False, startrow=5, startcol=0)
            
            # Добавляем отступ (например, 1 пустая строка)
            start_row = len(data_df) + 2+5
            sum_data_df.to_excel(writer, sheet_name='Report', index=False, startrow=start_row, startcol=4)
            start_row = start_row + 5
            total_sum_data_df.to_excel(writer, sheet_name='Report', index=False, startrow=start_row, startcol=4, header=False)
#--------------------               

#--           
        
        output_files.append(output_file)

        return output_files


#----------------------------------------------------------


