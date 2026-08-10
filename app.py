# =========================================================
# REGISTRY
# =========================================================

import streamlit as st

from processors.BaseProcessor import BaseProcessor
from processors.TollCollectProcessor import TollCollectProcessor
from processors.XmlProcessor import XmlProcessor
from processors.WhatsappProcessor import WhatsappProcessor
from processors.WhatsappHTMLProcessor import WhatsappHTMLProcessor

from processors.BwiProcessor import BwiProcessor
from processors.ValidatorXml import ValidatorXml
from processors.XmlConverter_CIItoUBL import XmlConverter_CIItoUBL
from processors.pdf_Samlung_new import pdf_Samlung_new
from processors.AnhangPDFausXML import AnhangPDFausXML


processors = [
    TollCollectProcessor(),
    BwiProcessor(),
    XmlProcessor(),    
    pdf_Samlung_new(),    
    AnhangPDFausXML(),
    ValidatorXml(),
    XmlConverter_CIItoUBL(),
    WhatsappProcessor(),
    WhatsappHTMLProcessor(),    
]

processor_dict = {
    p.name: p
    for p in processors
}


# =========================================================
# STREAMLIT PAGE
# =========================================================

st.set_page_config(
    page_title="MeinProcessors",
    page_icon="📊",
    layout="centered"
)

#----------- 
if True:
#-----------

    st.sidebar.header("📊 Mein Processors")

    st.write("**Select a processor and upload the files**   :sunglasses:")


    # =========================================================
    # PROCESSOR SELECT
    # =========================================================

    selected_processor_name = st.sidebar.pills(
        "Processor",
        list(processor_dict.keys()),default = list(processor_dict.keys())[0]
    )

    processor = processor_dict[selected_processor_name]


    # =========================================================
    # DYNAMIC UI
    # =========================================================

    data = processor.render_ui()


    # =========================================================
    # PROCESS BUTTON
    # =========================================================

    if st.button("🚀 Execute"):

        try:

            # проверяем что все файлы загружены
            missing = False

            for key, value in data.items():

                # selectbox/date/etc пропускаем
                if isinstance(value, str):
                    continue

                if value is None:
                    missing = True

            if missing:

                st.error("Please fill in all the fields")

            else:

                with st.spinner("Processing..."):

                    result = processor.process(data)
                

                st.success("Done!")
                st.balloons()
                
                df = result["df"]
                filename = result["filename"]
                mime = result["mime"]

                st.download_button(
                    label="📥 Download all results",
                    data=df,
                    file_name=filename,
                    mime=mime
                )
                            
        except Exception as e:

            st.error(f"Ошибка: {e}")
