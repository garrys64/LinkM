# =========================================================
# REGISTRY
# =========================================================

import streamlit as st
import os
import io
import zipfile
import tempfile

from processors.BaseProcessor import BaseProcessor
from processors.TollCollectProcessor import TollCollectProcessor
from processors.XmlProcessor import XmlProcessor
from processors.WhatsappProcessor import WhatsappProcessor
from processors.OffenePostenProcessor import OffenePostenProcessor


processors = [
    TollCollectProcessor(),
    XmlProcessor(),
    OffenePostenProcessor(),
    WhatsappProcessor(),
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

st.title("📊 Mein Processors")

st.write("Select a processor and upload the files")


# =========================================================
# PROCESSOR SELECT
# =========================================================

selected_processor_name = st.selectbox(
    "Processor",
    list(processor_dict.keys())
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

                result_files = processor.process(data)

            # создаём zip в памяти
            zip_buffer = io.BytesIO()

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in result_files:
                    zipf.write(file_path, arcname=os.path.basename(file_path))
                    os.remove(file_path)

            st.success("Done!")
            st.balloons()
            
            st.download_button(
                label="📥 Download all results",
                data=zip_buffer,
                file_name="results.zip",
                mime="application/zip"
            )
            
    except Exception as e:

        st.error(f"Ошибка: {e}")
