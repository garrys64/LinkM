# =========================================================
#
# PROCESSOR Autobahn
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import io
import pandas as pd


class Autobahn(BaseProcessor):

    name = "Autobahn Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendateien",accept_multiple_files=True, type=["xlsx","xls"])
        
        return {
            "Datendatei": Datendatei,
        }

    def process(self, data):
    
        preis_de = 0.071
        preis_not_de = 0.10

        Datendatei = data["Datendatei"]
        col = "D"
        count_de = 0
        count_not_de = 0
        
        
        for f in Datendatei:
            df = pd.read_excel(f, header=None, usecols=col, engine="calamine" )
            df = df.iloc[2:-6]
            df.columns = ["col_D"]
            count_de = count_de + (df["col_D"] == "DE").sum()
            count_not_de = count_not_de + (df["col_D"] != "DE").sum()
            #print(f"{f}: прочитано строк {len(df)}")
       
#--     
        df2 = pd.DataFrame(
            {
                "SMS": ["DE national", "DE international"],
                "Count": [count_de, count_not_de],
                "Preis": [preis_de,preis_not_de],
                "Summe": [count_de * preis_de,count_not_de * preis_not_de],
            }
        )       
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df2.to_excel(writer, index=False, sheet_name='Sheet1')
       
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{f.name}", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        

        return data

