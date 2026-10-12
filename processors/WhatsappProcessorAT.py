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
        GEBUR_SERVICE = 0.009           #****************

        df = pd.read_excel(Datendatei, usecols=['WABA', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'UNIT_RATE', 'AMOUNT', 'BILLING_PERIOD'], engine="calamine")
                       
        result = df.groupby(['WABA', 'PRICING_CATEGORY','COUNTRY']).agg({
            'MESSAGES': 'sum',
            'UNIT_RATE': 'first',
            'BILLING_PERIOD': 'first',
            'AMOUNT': 'sum'   
        }).reset_index()

        #--------------------------------------------------------------------------------------------------------------
        df0 = pd.read_excel(Preisliste, engine="calamine")
        df1 = df0[(df0['COUNTRY'] == 'AT')  & (df0['CHECK'] == 'Y')]
        
        if 'WABA_ID' in df1.columns: 
            df1['WABA'] = df1['WABA_ID']                    #****************
            df1['GEBUR_SERVICE'] = GEBUR_SERVICE            #****************
            df1['GEBUR_TEMPLATE'] = df1['EINHEITPREIS']     #****************

        df_preis_sum = df1[['CUSTOMER_NAME','WABA', 'GRUNDPREIS', 'GEBUR_SERVICE', 'GEBUR_TEMPLATE']]


        #--------------rename------------------------------------------------------------------------------------------
        df_preis = df1[['CUSTOMER_NAME', 'WABA', 'GEBUR_SERVICE', 'GEBUR_TEMPLATE']].rename(
            columns={'GEBUR_SERVICE': 'service'}
        )
        df_preis = df_preis[['CUSTOMER_NAME', 'WABA', 'service']].assign(
            marketing=df1['GEBUR_TEMPLATE'],
            utility=df1['GEBUR_TEMPLATE'],
            autentification=df1['GEBUR_TEMPLATE']
        )
        
        df_preis_sum = df1[['CUSTOMER_NAME','WABA', 'GRUNDPREIS']]

        #--------------Pyvot------------------------------------------------------------------------------------------
        pyvot_PRICING_CATEGORY = df_preis.melt(
            id_vars=['CUSTOMER_NAME','WABA'],
            var_name='PRICING_CATEGORY',
            value_name='meta_value'
        )

        #--------------------------------------------------------------------------------------------------------------
        result = result.merge(pyvot_PRICING_CATEGORY, on=['WABA', 'PRICING_CATEGORY'])
        result['AMOUNT'] = result['AMOUNT'] +result['MESSAGES'].fillna(0) * result['meta_value'].fillna(0)
        result['UNIT_RATE'] = result['UNIT_RATE'] + result['meta_value'].fillna(0)

        #--------------------------------------------------------------------------------------------------------------
        # Суммы по WABA
        result_sum = result.groupby(['WABA']).agg({
            'MESSAGES': 'sum',
            'AMOUNT': 'sum'   
        }).reset_index()
        
        result_sum = result_sum.merge(df_preis_sum, on=['WABA'], how='right')
        result_sum['TOTAL'] = result_sum['AMOUNT'].fillna(0) +result_sum['GRUNDPREIS'].fillna(0)
        
        #--------------------------------------------------------------------------------------------------------------  
        # Данные + Суммы
        result_sheet = pd.concat([result, result_sum], ignore_index=True)
        
        #--------------------------------------------------------------------------------------------------------------
        # Порядок столбцов для вывода
        result_sheet = result_sheet[['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'UNIT_RATE', 'AMOUNT', 'GRUNDPREIS', 'TOTAL']]
      
        #--------------------------------------------------------------------------------------------------------------
        # Сортировка по одному или нескольким столбцам
        result_sheet = result_sheet.sort_values(['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY'], ascending=[True,True,True])

#===========================================================    
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            result_sheet.to_excel(writer, index=False, sheet_name='Sheet1')
                  
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        
        return data


    
 
