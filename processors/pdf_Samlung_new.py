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

    name = "pdf_Samlung_new Processor"

    def render_ui(self):

        ZugFerd = st.file_uploader("ZugFerd datei",type=["pdf"])
        Anhangs = st.file_uploader("Anhangs dateien",type=["pdf"], accept_multiple_files=True)
        
        return {
            "ZugFerd": ZugFerd,
            "Anhangs": Anhangs,
        }

    def process(self, data):

        ZugFerd = data["ZugFerd"]
        Anhangs = data["Anhangs"]
        
        combined_pdf = pikepdf.Pdf.new()
        with pikepdf.open(ZugFerd) as src_pdf:
            combined_pdf.pages.extend(src_pdf.pages)
        for file in Anhangs:
            # Открываем каждый файл в байтовом буфере
            with pikepdf.open(file) as src_pdf:
                # Добавляем все страницы из текущего файла в объединённый
                combined_pdf.pages.extend(src_pdf.pages)

        # Сохраняем результат в BytesIO, чтобы отдать через st.download_button
        buffer = BytesIO()
        combined_pdf.save(buffer)
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"mitAnhang_{ZugFerd.name}", "mime": "application/pdf"}
        

        return data

