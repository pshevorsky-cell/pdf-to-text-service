from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import pdfplumber
import io
import logging

app = FastAPI(title="PDF to Text Extractor")

@app.post("/extract-text")
async def extract_text(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files allowed")
    
    try:
        # Читаем содержимое файла
        contents = await file.read()
        
        # Извлекаем текст
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        
        if not text.strip():
            return JSONResponse({"text": "[NO TEXT FOUND IN PDF]"})
        
        return JSONResponse({"text": text.strip()})
    
    except Exception as e:
        logging.error(f"Error processing PDF: {e}")
        return JSONResponse({"text": "[ERROR PROCESSING PDF]"})
