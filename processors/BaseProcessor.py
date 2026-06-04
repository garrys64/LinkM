# =========================================================
# BASE PROCESSOR
# =========================================================

class BaseProcessor:

    name = "Base Processor"

    def render_ui(self):
        """
        Должен вернуть словарь с данными/файлами
        """
        return {}

    def process(self, data):
        """
        Должен вернуть путь к результату
        """
        pass

