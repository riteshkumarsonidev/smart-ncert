import PyPDF2

def extract_text_from_pdf(filepath):
    try:
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            # Detect language: Count Devanagari characters
            # Devanagari range: \u0900 - \u097F
            devanagari_count = sum(1 for char in text[:5000] if '\u0900' <= char <= '\u097f')
            total_non_space = sum(1 for char in text[:5000] if not char.isspace())
            
            # If more than 10% of non-space characters are Devanagari, it's Hindi
            if total_non_space > 0 and (devanagari_count / total_non_space > 0.1):
                language = "Hindi"
            else:
                language = "English"
            
            return text.strip(), language
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return "", "English"
