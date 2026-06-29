# =========================================================
#
# ValidatorXml
# 
# =========================================================

from processors.BaseProcessor import BaseProcessor
import subprocess
import os
import streamlit as st
from pathlib import Path



OUTPUT_DIR = Path("results")
PEPPOL3 = "Peppol BIS/POACC 3.0"
EN16931 = "STANDARD EN 16931/Peppol 1.0 (CII/UBL)"
VALIDATOR_JAR = Path("libs") / "validator-1.6.2-standalone.jar"
SCENARIOS1 = Path("libs") / "10" / "scenarios.xml"
SCENARIOS3 = Path("libs") / "30" / "scenarios.xml"


class ValidatorXml_UBL(BaseProcessor):

    name = "ValidatorXml"

    def render_ui(self):

                
        Datendatei = st.file_uploader("XML Datei", type=["xml"])
        profile_xml = st.selectbox("PROFILE",[EN16931, PEPPOL3])
        
        
        return {
            "Datendatei": Datendatei,
            "profile_xml": profile_xml,
        }

    def process(self, data):

        Datendatei = data["Datendatei"]
        profile_xml = data["profile_xml"]
        output_files = []
        
        if profile_xml ==  PEPPOL3:
            SCENARIOS = SCENARIOS3
        else:
            SCENARIOS = SCENARIOS1

        file_path = OUTPUT_DIR / Datendatei.name.replace(' ', '_').lower()
       
        try:                                                              
            with open(file_path, 'wb') as f:
                f.write(Datendatei.getvalue())

            java_cmd = "java"
            cmd = [java_cmd,"-jar",VALIDATOR_JAR,"-s", SCENARIOS, "-o", OUTPUT_DIR,  file_path]
            result = subprocess.run(cmd, capture_output=True,  text=True)
            
            os.remove(file_path)
            
            if result.returncode == 0:
                st.success("✅ Successfully! XML Datei is VALID")
                
            else:
                st.error(f"❌ Error")
                                
            name, ext = os.path.splitext(file_path) 
            report_filename = f"{name}-report{ext}"  
              
            if report_filename:
                with open(report_filename, 'r', encoding='utf-8') as f:
                    xml_content = f.read()
                
                os.remove(report_filename)
                st.html(xml_content) 
                data = {"df": xml_content, "filename": f"report_{Datendatei.name}", "mime": "application/xml"}
               
            else:
                st.warning("Ups...")
                if result.stdout:
                    st.code(result.stdout)

        except Exception as e: 
            st.write(e)     

                    
        return data            

