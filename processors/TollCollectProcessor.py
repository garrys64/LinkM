# =========================================================
#
# PROCESSOR TollCollectProcessor
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import uuid
import pandas as pd


class TollCollectProcessor(BaseProcessor):

    name = "TollCollect Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei",type=["xlsx","xls"])
        Preisliste = st.file_uploader("Preisliste",type=["xlsx"])
        
        return {
            "Datendatei": Datendatei,
            "Preisliste": Preisliste,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        Preisliste = data["Preisliste"]
        output_files = []

#---
        phones_df = pd.read_excel(Datendatei)
        result = pd.read_excel(Preisliste)
        
        result.columns = ['code', 'country', 'price'] + list(result.columns[3:])
        result['code'] = result['code'].astype(str)
        result['count'] = 0
        result['cost'] = 0.0

        def clean_phone_series(phones):
            phones_str = phones.astype(str).str.strip()
            phones_str = phones_str.str.replace(r'^00', '', regex=True)
            phones_str = phones_str.str.replace(r'\D', '', regex=True)
            return phones_str
            
        column_number = 2
        cleaned_phones = clean_phone_series(phones_df.iloc[:, column_number])  # колонка 3
        code_list = sorted(result['code'].values, key=len, reverse=True)   
               
        def find_code(phone):
            if phone == "":
                return '0000'           # пропускаем пустые строки
            for code in code_list:
                if phone.startswith(code):
                    return code
            return '9999'               # если кода нет в списке
             
        found_codes = cleaned_phones.apply(find_code)
        code_counts = found_codes.value_counts()
        
        for code, count in code_counts.items():
            mask = result['code'] == code
            if mask.any():
                result.loc[mask, 'count'] += count
                result.loc[mask, 'cost'] += count * result.loc[mask, 'price'].values[0]

        sum_count = result.iloc[:, 3].sum()
        sum_cost = result.iloc[:, 4].sum()
        sum_row = ['Total','','',sum_count,sum_cost]
        result2 = pd.concat([result, pd.DataFrame([sum_row], columns=result.columns)], ignore_index=True)

#--            
        os.makedirs("results", exist_ok=True)
        output_file = f"results/TollCollect_{uuid.uuid4()}.xlsx"
        result2.to_excel(output_file, index=False)
        
        output_files.append(output_file)

        return output_files

