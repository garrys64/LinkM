# =========================================================
#
# PROCESSOR WhatsappProcessorAT
# 
# =========================================================

REFERRAL_CONVERSION = False

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import io
import pandas as pd
import numpy as np


class WhatsappProcessorAT(BaseProcessor):

    name = "Whatsapp Processor AT"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei", type=["xlsx"])
        Preisliste = st.file_uploader("Preisliste", type=["xlsx","xlsm"])
        
        return {
            "Datendatei": Datendatei,
            "Preisliste": Preisliste,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        Preisliste = data["Preisliste"]
        output_files = []

#===========================================================
        df = pd.read_excel(Datendatei, usecols=['WABA', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'AMOUNT'], engine="calamine")
       
        conditions = [
            df['PRICING_CATEGORY'] == 'service',
            df['PRICING_CATEGORY'] == 'referral_conversion'
        ]

        choices = [
            'GEBUR_SERVICE',
            'GEBUR_referral_conversion'
        ]

        df['PRICING_CATEGORY'] = np.select(conditions, choices, default='GEBUR_TEMPLATE')
                
        result = df.groupby(['WABA', 'PRICING_CATEGORY','COUNTRY']).agg({
            'MESSAGES': 'sum',
            'AMOUNT': 'sum'   
        }).reset_index()

        #--------------------------------------------------------------------------------------------------------------
        df0 = pd.read_excel(Preisliste, usecols=['CUSTOMER_NAME', 'WABA', 'CHECK', 'GEBUR_SERVICE', 'GEBUR_TEMPLATE', 'COUNTRY', 'GRUNDPREIS'], engine="calamine")
        df1 = df0[(df0['COUNTRY'] == 'AT')  & (df0['CHECK'] == 'Y')]
        
        dfY = df1[['CUSTOMER_NAME', 'WABA', 'GEBUR_SERVICE', 'GEBUR_TEMPLATE']]
        dfY2 = df1[['CUSTOMER_NAME','WABA', 'GRUNDPREIS']]
        
        meta_long = dfY.melt(
            id_vars=['CUSTOMER_NAME','WABA'],
            var_name='PRICING_CATEGORY',
            value_name='meta_value'
        )

        #--------------------------------------------------------------------------------------------------------------
        result = result.merge(meta_long, on=['WABA', 'PRICING_CATEGORY'], how='right')
        result['AMOUNT'] = result['AMOUNT'] +result['MESSAGES'].fillna(0) * result['meta_value'].fillna(0)

        #--------------------------------------------------------------------------------------------------------------
       
        result2t = result.groupby(['WABA']).agg({
            'MESSAGES': 'sum',
            'AMOUNT': 'sum'   
        }).reset_index()
        
        result2t= result2t.merge(dfY2, on=['WABA'], how='right')
        result2t['TOTAL'] = result2t['AMOUNT'].fillna(0) +result2t['GRUNDPREIS'].fillna(0)
        
        #--------------------------------------------------------------------------------------------------------------       
        result3 = pd.concat([result, result2t], ignore_index=True)
        
        #--------------------------------------------------------------------------------------------------------------
        # Порядок столбцов для вывода
        result3 = result3[['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'AMOUNT', 'GRUNDPREIS', 'TOTAL']]
      
        #--------------------------------------------------------------------------------------------------------------
        # Сортировка по одному или нескольким столбцам
        result3 = result3.sort_values(['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY'], ascending=[True,True,True])

#===========================================================    
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            result3.to_excel(writer, index=False, sheet_name='Sheet1')
       
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        

        return data


    
 
