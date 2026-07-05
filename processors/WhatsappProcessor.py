# =========================================================
#
# PROCESSOR WhatsappProcessor
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import io
import pandas as pd
import numpy as np
import time

class WhatsappProcessor(BaseProcessor):

    name = "Whatsapp Processor"

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

#---
        df = pd.read_excel(Datendatei, usecols=[5, 6, 7, 8, 14, 16])
               
#####---NUR BUSINESS_PHONE_NO  = 4917688800103 ---заменить на нужный-------------------------------------------
        #condition = (df['BUSINESS_PHONE_NO'] == 4917688800103) 

        #for idx in df[condition].index:
            #df.loc[idx, 'WABA'] = 0
            #df.loc[idx, 'WABA_NAME'] = df.loc[idx, 'WABA_NAME'] + '_BT'
#####--------------------------------------------------------------------------------------------------------------------------------------
#####---NUR DE500 WABA ?????? [9992066484947186470, 999281787285012305] ---заменить на нужные-------------
        #values_col1 = [9992066484947186470, 999281787285012305]

        #for item in values_col1:
            #condition = (df['WABA'] == item) & (df['PRICING_CATEGORY'] == 'marketing') 

            #remaining = 500
            #for idx in df[condition].index:
                #if remaining <= 0:
                    #break
                #decrease = min(df.loc[idx, 'MESSAGES'], remaining)
                #df.loc[idx, 'MESSAGES'] -= decrease
                #df.loc[idx, 'AMOUNT'] = 0
                #remaining -= decrease               
#####--------------------------------------------------------------------------------------------------------------------------------------
      
                
#####------------------------------------------------------------------------------------------------------
        #### OHNE REFERRAL_CONVERSION      
        
        conditions = [
            df['PRICING_CATEGORY'] == 'service',
            df['PRICING_CATEGORY'] == 'referral_conversion'
        ]

        choices = [
            'GEBUR_SERVICE',
            'GEBUR_referral_conversion'
        ]

        df['PRICING_CATEGORY'] = np.select(conditions, choices, default='GEBUR_TEMPLATE')
        
#####------------------------------------------------------------------------------------------------------
        #### MIT REFERRAL_CONVERSION  
        
        #df['PRICING_CATEGORY'] = np.where(df['PRICING_CATEGORY'] == 'service', 'GEBUR_SERVICE', 'GEBUR_TEMPLATE')

#####------------------------------------------------------------------------------------------------------              


        result = df.groupby(['WABA', 'PRICING_CATEGORY']).agg({
            #'WABA_NAME': 'first',  # или 'last'
            'MESSAGES': 'sum',
            'AMOUNT': 'sum'   
        }).reset_index()

        #--------------------------------------------------------------------------------------------------------------
        dfY = pd.read_excel(Preisliste, usecols=[0, 2, 7, 8])
        meta_long = dfY.melt(
            id_vars=['CUSTOMER_NAME','WABA'],
            var_name='PRICING_CATEGORY',
            value_name='meta_value'
        )

        #--------------------------------------------------------------------------------------------------------------
        result= result.merge(meta_long, on=['WABA', 'PRICING_CATEGORY'], how='right')
        result['AMOUNT'] = result['AMOUNT'] +result['MESSAGES'].fillna(0) * result['meta_value'].fillna(0)

        #--------------------------------------------------------------------------------------------------------------
        result2 = result.groupby(['WABA']).agg({
            'CUSTOMER_NAME': 'first', 
            'MESSAGES': 'sum',
            'AMOUNT': 'sum'   
        }).reset_index()

        #--------------------------------------------------------------------------------------------------------------
        dfY2 = pd.read_excel(Preisliste, usecols=[2, 1, 5, 6, 11])

        #--------------------------------------------------------------------------------------------------------------
        result2= result2.merge(dfY2, on=['WABA'], how='left')
        result2['TOTAL'] = (result2['AMOUNT'].fillna(0) + result2['GRUNDPREIS'].fillna(0) + result2['PAKETDE'].fillna(0)) * (100-result2['RABBAT(%)'].fillna(0)) / 100

        #--------------------------------------------------------------------------------------------------------------
        # Порядок столбцов для вывода
        result2 = result2[['COUNTRY', 'CUSTOMER_NAME', 'MESSAGES', 'AMOUNT', 'GRUNDPREIS', 'PAKETDE', 'RABBAT(%)', 'TOTAL']]

        #--------------------------------------------------------------------------------------------------------------
        # Сортировка по одному или нескольким столбцам
        result2 = result2.sort_values(['COUNTRY','CUSTOMER_NAME'], ascending=[True, True])

        #--------------------------------------------------------------------------------------------------------------
        #result2 = result2[result2['CHECK'] == 'Y']
#---    
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            result2.to_excel(writer, index=False, sheet_name='Sheet1')
       
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        

        return data


    
 
