import os
from fpdf import FPDF

class PDFMaker:
    def __init__(self, font_path=None):
        self.font_path = font_path

    def create_pdf(self, title, content, output_path):
        pdf = FPDF()
        pdf.add_page()
        
        font_loaded = False
        system_fonts = [
            self.font_path,
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        
        for fp in system_fonts:
            if fp and os.path.exists(fp):
                try:
                    pdf.add_font("CustomFont", "", fp, uni=True)
                    pdf.set_font("CustomFont", size=12)
                    font_loaded = True
                    break
                except:
                    try:
                        pdf.add_font("CustomFont", "", fp)
                        pdf.set_font("CustomFont", size=12)
                        font_loaded = True
                        break
                    except:
                        pass
        
        if not font_loaded:
            pdf.set_font("Helvetica", size=12)
            content = content.encode('latin-1', 'replace').decode('latin-1')
            title = title.encode('latin-1', 'replace').decode('latin-1')

        pdf.multi_cell(0, 10, txt=title, align='C')
        pdf.ln(10)
        pdf.multi_cell(0, 8, txt=content)
        pdf.output(output_path)

    def merge_texts_to_pdf(self, texts_list, output_path, title):
        full_content = "\n\n".join(texts_list)
        self.create_pdf(title, full_content, output_path)