import os
import json
import torch
from torchvision import models, transforms
from PIL import Image
import torch.nn as nn
from datetime import datetime
import pytesseract
from deep_translator import GoogleTranslator
import re
import cv2
from django.conf import settings

# Set Tesseract path
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class DocumentForgeryDetector:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.class_idx_to_label = None
        self._load_model()
    
    def _build_model(self, num_classes=3):
        model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        num_ftrs = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(p=0.5),
            nn.Linear(num_ftrs, num_classes)
        )
        return model
    
    def _load_class_indices(self):
        class_indices_path = os.path.join(settings.BASE_DIR, 'ml_models', 'class_indices.json')
        if os.path.exists(class_indices_path):
            with open(class_indices_path, "r") as f:
                idx = json.load(f)
            return {int(k): v for k, v in idx.items()}
        return {0: "positive", 1: "fraud5_inpaint_and_rewrite", 2: "fraud6_crop_and_replace"}
    
    def _load_model(self):
        self.class_idx_to_label = self._load_class_indices()
        num_classes = len(self.class_idx_to_label)
        self.model = self._build_model(num_classes=num_classes).to(self.device)
        
        model_path = os.path.join(settings.BASE_DIR, 'ml_models', 'best_multiclass.pt')
        if os.path.exists(model_path):
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        else:
            raise FileNotFoundError(f"Model weights not found at {model_path}")
        
        self.model.eval()
    
    def clean_text(self, text):
        if not text:
            return "No text detected"
        
        # Remove non-printable/control characters
        text = re.sub(r'[^\x20-\x7E\n\r\tΑ-Ωα-ωΆ-Ώά-ώ]', '', text)
        lines = text.splitlines()
        
        # Keep only meaningful lines
        clean_lines = []
        for line in lines:
            line_clean = line.strip()
            if len(line_clean) < 3:
                continue
            if re.search(r'[A-Za-z0-9Α-Ωα-ω]', line_clean):
                clean_lines.append(line_clean)
        
        return "\n".join(clean_lines) if clean_lines else "No meaningful text detected"
    
    def extract_text_from_image(self, image_path, lang="eng+spa+ell"):
        try:
            img = cv2.imread(image_path)
            if img is None:
                return "OCR Error: Cannot load image."
            
            # Preprocessing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
            _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            thresh = cv2.medianBlur(thresh, 3)
            
            pil_img = Image.fromarray(thresh)
            text = pytesseract.image_to_string(pil_img, lang=lang, config="--psm 11")
            return self.clean_text(text)
        except Exception as e:
            return f"OCR Error: {str(e)}"
    
    def translate_text(self, text):
        try:
            if not text or "OCR Error" in text or "no text" in text.lower():
                return "Translation skipped (no valid text)."
            return GoogleTranslator(source='auto', target='en').translate(text)
        except Exception as e:
            return f"Translation failed: {e}"
    
    def predict_image(self, image_path):
        transform = transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize([0.485,0.456,0.406],[0.229,0.224,0.225])
        ])
        
        img = Image.open(image_path).convert("RGB")
        tensor = transform(img).unsqueeze(0).to(self.device)
        
        with torch.no_grad():
            logits = self.model(tensor)
            probs = torch.softmax(logits, dim=1)
            conf, pred_idx = probs.max(dim=1)
        
        pred_class = self.class_idx_to_label.get(int(pred_idx.item()), str(pred_idx.item()))
        simple_label = "GENUINE" if pred_class == "positive" else "FORGED"
        
        all_probs = {self.class_idx_to_label.get(i, str(i)): float(p)*100 for i, p in enumerate(probs[0])}
        return simple_label, float(conf.item())*100, all_probs
    
    def generate_report(self, image_path, doc_type="Unknown"):
        start_time = datetime.now()
        
        try:
            simple_label, conf, all_probs = self.predict_image(image_path)
            extracted_text = self.extract_text_from_image(image_path)
            translated_text = self.translate_text(extracted_text)
        except Exception as e:
            return f"Error processing document: {str(e)}"
        
        end_time = datetime.now()
        
        report = {
            'status': 'success',
            'prediction': simple_label,
            'confidence': f"{conf:.2f}%",
            'processing_time': f"{(end_time - start_time).total_seconds():.2f} seconds",
            'extracted_text': extracted_text,
            'translated_text': translated_text,
            'probabilities': all_probs,
            'timestamp': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'filename': os.path.basename(image_path),
            'doc_type': doc_type
        }
        
        return report

# Global detector instance
detector = None

def get_detector():
    global detector
    if detector is None:
        detector = DocumentForgeryDetector()
    return detector
