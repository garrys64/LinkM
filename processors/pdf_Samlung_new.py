# =========================================================
#
# PROCESSOR pdf_Samlung_new
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
from io import BytesIO
import pikepdf



class pdf_Samlung_new(BaseProcessor):

    name = "PDFs Samlung (ZUGFeRD + Anhangs)"

    def render_ui(self):

        ZUGFeRD = st.file_uploader("ZUGFeRD Datei",type=["pdf"])
        Anhangs = st.file_uploader("Anhangs Dateien",type=["pdf"], accept_multiple_files=True)
        
        return {
            "ZUGFeRD": ZUGFeRD,
            "Anhangs": Anhangs,
        }

    def process(self, data):

        ZUGFeRD = data["ZUGFeRD"]
        Anhangs = data["Anhangs"]

        with pikepdf.open(ZUGFeRD) as combined_pdf:

            for file in Anhangs:
                with pikepdf.open(file) as src_pdf:
                    combined_pdf.pages.extend(src_pdf.pages)

        buffer = BytesIO()
        combined_pdf.save(buffer)
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"mitAnhang_{ZUGFeRD.name}", "mime": "application/pdf"}
        

        return data

