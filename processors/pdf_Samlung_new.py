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
        
        combined_pdf = pikepdf.Pdf.new()
        with pikepdf.open(ZUGFeRD) as src_pdf:
            combined_pdf.pages.extend(src_pdf.pages)
            # Копируем структуру Names (включая EmbeddedFiles) целиком
            if src_pdf.root.Names:
                combined.root.Names = src_pdf.root.Names

            # Копируем XMP
            with src_pdf.open_metadata() as meta_src:
                with combined.open_metadata(readonly=False) as meta_dst:
                    meta_dst.packet = meta_src.packet

        with pikepdf.open(ZUGFeRD) as src:
        combined.pages.extend(src.pages)

        for file in Anhangs:
            # Открываем каждый файл в байтовом буфере
            with pikepdf.open(file) as add_src_pdf:
                # Добавляем все страницы из текущего файла в объединённый
                combined_pdf.pages.extend(add_src_pdf.pages)

        # Сохраняем результат в BytesIO, чтобы отдать через st.download_button
        buffer = BytesIO()
        combined_pdf.save(buffer)
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"mitAnhang_{ZUGFeRD.name}", "mime": "application/pdf"}
        

        return data

