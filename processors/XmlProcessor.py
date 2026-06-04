# =========================================================
#
# PROCESSOR XmlProcessor
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
import os
from lxml import etree
import re
from calendar import monthrange
import uuid

class XmlProcessor(BaseProcessor):

    name = "Xml Processor"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei", type=["xml"])
        #Preisliste = st.file_uploader("Preisliste", type=["xlsx","xlsm"])
        
        return {"Datendatei": Datendatei}

    def process(self, data):

        xml_file = data["Datendatei"]
        #Preisliste = data["Preisliste"]
        output_files = []

#---
      
        # Парсим XML (сохраняет nsmap как есть)
        parser = etree.XMLParser(remove_blank_text=False)
        tree = etree.parse(xml_file, parser)
        root = tree.getroot()

        ns = {
            'cac': 'urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2',
            'cbc': 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2',
            'ubl': 'urn:oasis:names:specification:ubl:schema:xsd:Invoice-2'
        }

        # -------------------------------------------------------------------------------------
        # AccountingCustomerParty > меняем email
        # -------------------------------------------------------------------------------------
        #for elem in root.xpath('.//cac:AccountingCustomerParty//cbc:EndpointID', namespaces=ns):
        #    elem.text = e_mail

        # -------------------------------------------------------------------------------------
        # InvoiceLine > добавляем InvoicePeriod
        # -------------------------------------------------------------------------------------
        for invoice_line in root.xpath('.//cac:InvoiceLine', namespaces=ns):
        
            if invoice_line.find('cac:InvoicePeriod', namespaces=ns)  is None :

                name_elem = invoice_line.find('.//cbc:Name', namespaces=ns)

                if name_elem is not None and name_elem.text:
                    match = re.search(r'(\d{2}/\d{2})', name_elem.text)

                    if match:
                        month, year = match.group(1).split('/')

                        if len(year) == 2:
                            year = f'20{year}'

                        month_num = int(month)
                        year_num = int(year)

                        startdate = f'{year}-{month.zfill(2)}-01'
                        last_day = monthrange(year_num, month_num)[1]
                        enddate = f"{year}-{month.zfill(2)}-{last_day:02d}"

                        # ищем или создаём InvoicePeriod
                        def insert_invoice_period(invoice_line, ns):
                            invoice_period = etree.Element(f'{{{ns["cac"]}}}InvoicePeriod')

                            # порядок из UBL (куда нельзя заходить)
                            after_tags = [
                                'OrderLineReference',
                                'DespatchLineReference',
                                'ReceiptLineReference',
                                'BillingReference',
                                'DocumentReference',
                                'PricingReference',
                                'Delivery',
                                'DeliveryTerms',
                                'Item',
                                'Price',
                                'ItemPriceExtension',
                                'SubInvoiceLine'
                            ]

                            insert_index = None

                            for i, child in enumerate(invoice_line):
                                localname = etree.QName(child).localname

                                if localname in after_tags:
                                    insert_index = i
                                    break

                            if insert_index is not None:
                                invoice_line.insert(insert_index, invoice_period)
                            else:
                                invoice_line.append(invoice_period)

                            return invoice_period

                        
                        invoice_period = insert_invoice_period(invoice_line, ns)
                        # StartDate
                        start_elem = invoice_period.find('cbc:StartDate', namespaces=ns)
                        if start_elem is None:
                            start_elem = etree.SubElement(
                                invoice_period,
                                f'{{{ns["cbc"]}}}StartDate'
                            )
                        start_elem.text = startdate

                        # EndDate
                        end_elem = invoice_period.find('cbc:EndDate', namespaces=ns)
                        if end_elem is None:
                            end_elem = etree.SubElement(
                                invoice_period,
                                f'{{{ns["cbc"]}}}EndDate'
                            )
                        end_elem.text = enddate
#---                
   
        os.makedirs("results", exist_ok=True)
        output_file = f"results/XML_{uuid.uuid4()}.xml"
        tree.write(output_file, encoding='utf-8', xml_declaration=True, pretty_print=False)

        output_files.append(output_file)

        return output_files


    
 
