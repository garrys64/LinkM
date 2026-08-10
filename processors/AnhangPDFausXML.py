# =========================================================
#
# PROCESSOR AnhangPDFausXML
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import streamlit as st
from lxml import etree
import base64
import io

class AnhangPDFausXML(BaseProcessor):

    name = "Anhang PDF aus XML"

    def render_ui(self):

        Datendatei = st.file_uploader("Datendatei",type=["xml"])
        
        return {
            "Datendatei": Datendatei,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
  
        tree = etree.parse(Datendatei)
        root = tree.getroot()

        # BinaryObject с mimeCode="application/pdf"
        
  
        if root.nsmap.get("ram") is not None:
            ns = {"ram": root.nsmap.get("ram")}
            nodes = root.xpath("//ram:AttachmentBinaryObject[@mimeCode='application/pdf']", namespaces=ns)
                
        else:
            ns = {"cbc": root.nsmap.get("cbc")}   
            nodes = root.xpath("//cbc:EmbeddedDocumentBinaryObject[@mimeCode='application/pdf']", namespaces=ns)
        
        if not nodes:
            raise RuntimeError("Anhang nicht gefunden")
            
        node = nodes[0]
        buffer = io.BytesIO(base64.b64decode(node.text.strip()))   
        buffer.seek(0)
        st.pdf(buffer, height=800)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}.pdf", "mime": "application/pdf"}
        

        return data

