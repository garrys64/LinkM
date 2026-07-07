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

        ns = {"ram": root.nsmap.get("ram")}

        # AttachmentBinaryObject с mimeCode="application/pdf"
        nodes = root.xpath("//ram:AttachmentBinaryObject[@mimeCode='application/pdf']", namespaces=ns)
        node = nodes[0]
        buffer = io.BytesIO(base64.b64decode(node.text.strip()))   
        buffer.seek(0)
        data = {"df": buffer,"filename":  f"result_{Datendatei.name}", "mime": "application/pdf"}
        

        return data

