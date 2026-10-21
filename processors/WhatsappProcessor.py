# =========================================================
#
# PROCESSOR WhatsappProcessor
# 
# =========================================================

REFERRAL_CONVERSION = False

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
import io
import pandas as pd
import numpy as np


class WhatsappProcessor(BaseProcessor):

    name = "Whatsapp Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei", type=["xlsx"])
        Preisliste = st.file_uploader("Preisliste", type=["xlsx","xlsm"])
        
        col1, col2 = st.columns(2)

        with col1:
            ATDE = st.radio("AT/DE:", ["AT", "DE"], horizontal = True)
        with col2:
            FULLKURZ = st.radio("FULL/KURZ:" , ["FULL", "KURZ"], horizontal = True)
        
        return {
            "Datendatei": Datendatei,
            "Preisliste": Preisliste,
            
            "ATDE": ATDE,
            "FULLKURZ": FULLKURZ,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        Preisliste = data["Preisliste"]
        
        ATDE = data["ATDE"]
        FULLKURZ = data["FULLKURZ"]

        

#===========================================================
        GEBUR_SERVICE = 0.009           #****************

        df = pd.read_excel(Datendatei, usecols=['WABA', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'UNIT_RATE', 'AMOUNT', 'BILLING_PERIOD'], engine="calamine")

##---NUR DE500 WABA 
        values_col1 = [101308222986139, 117528971326434]
        for item in values_col1:
            condition = (df['WABA'] == item) & (df['PRICING_CATEGORY'] == 'marketing')  & (df['COUNTRY'] == 'Germany')

            remaining = 500
            for idx in df[condition].index:
                if remaining <= 0:
                    break
                decrease = min(df.loc[idx, 'MESSAGES'], remaining)
                df.loc[idx, 'MESSAGES'] -= decrease
                df.loc[idx, 'AMOUNT'] = 0
                remaining -= decrease  
##
##---NUR Maxda 
        values_col1 = [220144250066881]
        for item in values_col1:
            condition = (df['WABA'] == item) & (df['PRICING_CATEGORY'] == 'service')

            remaining = 2500
            for idx in df[condition].index:
                if remaining <= 0:
                    break
                decrease = min(df.loc[idx, 'MESSAGES'], remaining)
                df.loc[idx, 'MESSAGES'] -= decrease
                df.loc[idx, 'AMOUNT'] = 0
                remaining -= decrease  
##  

       
        result = df.groupby(['WABA', 'PRICING_CATEGORY','COUNTRY']).agg({
            'MESSAGES': 'sum',
            'UNIT_RATE': 'first',
            'BILLING_PERIOD': 'first',
            'AMOUNT': 'sum'   
        }).reset_index()

        #--------------------------------------------------------------------------------------------------------------
        df0 = pd.read_excel(Preisliste, engine="calamine")
        df1 = df0[(df0['COUNTRY'] == ATDE)  & (df0['CHECK'] == 'Y')]
        
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
        if FULLKURZ == 'FULL':
            result_sheet = pd.concat([result, result_sum], ignore_index=True)
            result_sheet = result_sheet[['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY', 'MESSAGES', 'UNIT_RATE', 'AMOUNT', 'GRUNDPREIS', 'TOTAL']]
            result_sheet = result_sheet.sort_values(['CUSTOMER_NAME', 'PRICING_CATEGORY', 'COUNTRY'], ascending=[True,True,True])
        else:
            result_sheet = result_sum
            result_sheet = result_sheet[['CUSTOMER_NAME', 'MESSAGES', 'AMOUNT', 'GRUNDPREIS', 'TOTAL']]
            result_sheet = result_sheet.sort_values(['CUSTOMER_NAME'], ascending=[True])

#===========================================================    
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            result_sheet.to_excel(writer, index=False, sheet_name='Sheet1')
                  
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
        
        return data


    
 
