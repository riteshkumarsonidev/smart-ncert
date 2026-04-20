import google.generativeai as genai
import os
import json

def generate_questions(class_name, subject, level, number, content, api_key):
    if not api_key or api_key == "YOUR_GEMINI_API_KEY_HERE":
        return {"error": "Gemini API Key is missing. Please ensure GEMINI_API_KEY is set in the environment or .env file."}
    
    if not content or len(content.strip()) < 50:
        return {"error": "The PDF content is too short or empty. Please upload a PDF with more text."}
    
    try:
        print(f"--- AI Generation Started ---")
        print(f"Subject: {subject}, Level: {level}, Number: {number}")
        print(f"API Key present: {'Yes' if api_key else 'No'}")
        
        genai.configure(api_key=api_key)
        
        # Try to find a model that supports generateContent
        model = None
        model_name = ""
        
        print("Listing available models...")
        try:
            available_models = []
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    available_models.append(m.name)
            
            print(f"Found supported models: {available_models}")
            
            # Try models in order of preference
            preference = [
                'models/gemini-3-flash-preview', 
                'models/gemini-2.5-flash', 
                'models/gemini-2.0-flash', 
                'models/gemini-1.5-flash', 
                'models/gemini-pro'
            ]
            # Add models that were found but not in preference list
            for m_name in available_models:
                if m_name not in preference:
                    preference.append(m_name)
            
            for name in preference:
                try:
                    # Try with and without 'models/' prefix if needed
                    names_to_try = [name]
                    if not name.startswith('models/'):
                        names_to_try.append(f"models/{name}")
                    
                    for try_name in names_to_try:
                        print(f"Trying model: {try_name}")
                        m = genai.GenerativeModel(try_name)
                        # Test generation
                        m.generate_content("test", generation_config={"max_output_tokens": 1})
                        model = m
                        model_name = try_name
                        print(f"✅ Successfully initialized model: {try_name}")
                        break
                    if model: break
                except Exception as e:
                    print(f"❌ Model {name} failed: {e}")
                    continue
        except Exception as e:
            print(f"Error listing models: {e}")
            # Fallback to hardcoded names if list_models fails
            fallback_names = ['gemini-pro', 'models/gemini-pro', 'gemini-1.5-flash', 'models/gemini-1.5-flash']
            for name in fallback_names:
                try:
                    print(f"Trying fallback model: {name}")
                    m = genai.GenerativeModel(name)
                    m.generate_content("test", generation_config={"max_output_tokens": 1})
                    model = m
                    model_name = name
                    print(f"✅ Successfully initialized fallback model: {name}")
                    break
                except Exception as e:
                    print(f"❌ Fallback model {name} failed: {e}")
                    continue
        
        if not model:
            # Last ditch effort: try gemini-pro directly without testing
            try:
                print("Last ditch effort: Trying gemini-pro directly...")
                model = genai.GenerativeModel('gemini-pro')
                model_name = 'gemini-pro'
            except:
                return {"error": "Could not find a supported Gemini model for your API key. Please check your API key permissions at https://aistudio.google.com/"}
        
        print(f"Final model selected: {model_name}")
        
        # Language Detection: Count Devanagari characters
        # Devanagari range: \u0900 - \u097F
        devanagari_count = sum(1 for char in content[:5000] if '\u0900' <= char <= '\u097f')
        total_non_space = sum(1 for char in content[:5000] if not char.isspace())
        
        # If more than 10% of non-space characters are Devanagari, it's Hindi
        is_hindi = (devanagari_count / total_non_space > 0.1) if total_non_space > 0 else False
        
        # If subject is explicitly Hindi, force it
        if subject.lower() == "hindi":
            is_hindi = True
            
        language = "Hindi" if is_hindi else "English"
        
        # Content Coverage: Ensure we cover all parts of the PDF
        # We'll take up to 60,000 characters. If longer, we sample from start, middle, and end.
        if len(content) > 60000:
            part_size = 20000
            mid = len(content) // 2
            content_to_send = (
                content[:part_size] + 
                "\n\n[... Middle Section ...]\n\n" + 
                content[mid - part_size//2 : mid + part_size//2] + 
                "\n\n[... End Section ...]\n\n" + 
                content[-part_size:]
            )
        else:
            content_to_send = content
        
        prompt = f"""
        You are an expert teacher. Generate {number} Multiple Choice Questions (MCQs) for Class {class_name} {subject}.
        Difficulty Level: {level}
        Target Language: {language}
        
        Instructions:
        1. The output MUST be entirely in {language}. 
           - If Target Language is Hindi, use Devanagari script for everything.
           - If Target Language is English, use English for everything.
        2. Base the questions strictly on the provided content. Do not use external knowledge.
        3. Ensure questions are distributed across the entire provided content (start, middle, and end).
        4. Each question must have exactly 4 options.
        5. Provide exactly 1 correct answer index (0, 1, 2, or 3).
        6. IMPORTANT: Each question text must be concise (maximum 150 characters).
        7. Output ONLY a valid JSON object. No extra text, no markdown blocks.
        
        Content:
        {content_to_send}
        
        Expected JSON Format:
        {{
            "questions": [
                {{
                    "question": "Question text here",
                    "options": ["Option 0", "Option 1", "Option 2", "Option 3"],
                    "correctAnswer": 0
                }}
            ]
        }}
        """
        
        response = model.generate_content(prompt)
        text = response.text.strip()
        print(f"--- AI RAW RESPONSE ---\n{text}\n-----------------------")
        
        # Clean up Markdown JSON blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Final fallback: find first '{' and last '}' to handle extra text
        if "{" in text and "}" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            text = text[start:end]
            
        data = json.loads(text.strip())
        
        if "questions" not in data or not data["questions"]:
            return {"error": "AI failed to generate questions. Please try with different content."}
            
        return data
    except Exception as e:
        print(f"Error generating questions: {e}")
        return {"error": f"AI Generation Error: {str(e)}"}
