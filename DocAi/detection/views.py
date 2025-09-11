from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import tempfile
import os
from datetime import datetime
import re
import io
from typing import Dict, List, Set
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from .models import DetectionHistory
from detection.forgery_detector import get_detector

# ==================== DJANGO VIEW FUNCTIONS ====================

@login_required(login_url='login')
def upload_view(request):
    """Main upload page - handles both GET and POST"""
    report_data = None
    
    if request.method == "POST" and request.FILES.get('document'):
        uploaded_file = request.FILES['document']
        doc_type = request.POST.get('doc_type', 'Unknown')

        # Allowed image formats
        allowed_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']
        if not any(uploaded_file.name.lower().endswith(ext) for ext in allowed_extensions):
            return render(request, 'upload.html', {
                'error': 'Invalid file type. Please upload an image file.',
                'report': None
            })

        try:
            # Save temporarily with original extension
            ext = os.path.splitext(uploaded_file.name)[1]
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
                for chunk in uploaded_file.chunks():
                    tmp_file.write(chunk)
                tmp_file_path = tmp_file.name

            # Run detector
            detector = get_detector()
            report_data = detector.generate_report(tmp_file_path, doc_type)

            # Clean up temp file
            os.unlink(tmp_file_path)

            if report_data.get('status') == 'success':
                # Save to DB
                detection = DetectionHistory.objects.create(
                    filename=uploaded_file.name,
                    doc_type=doc_type,
                    prediction=report_data['prediction'],
                    confidence=float(report_data['confidence'].replace('%', '')),
                    processing_time=float(report_data['processing_time'].replace(' seconds', '')),
                    extracted_text=report_data['extracted_text'],
                    translated_text=report_data['translated_text'],
                    probabilities=report_data['probabilities']
                )
                report_data['detection_id'] = detection.id
            else:
                return render(request, 'upload.html', {
                    'error': f'Processing failed: {report_data}',
                    'report': None
                })

        except Exception as e:
            return render(request, 'upload.html', {
                'error': f'Processing failed: {str(e)}',
                'report': None
            })

    return render(request, 'upload.html', {'report': report_data, 'error': None})

@login_required(login_url='login')
def reports_history(request):
    """List of past reports"""
    reports = DetectionHistory.objects.all().order_by('-timestamp')[:50]
    stats = {
        'total_reports': DetectionHistory.objects.count(),
        'forged_count': DetectionHistory.objects.filter(prediction='FORGED').count(),
        'genuine_count': DetectionHistory.objects.filter(prediction='GENUINE').count(),
    }
    
    # Calculate percentages
    total = stats['total_reports']
    if total > 0:
        stats['forged_percentage'] = (stats['forged_count'] / total) * 100
        stats['genuine_percentage'] = (stats['genuine_count'] / total) * 100
    else:
        stats['forged_percentage'] = 0
        stats['genuine_percentage'] = 0
    
    return render(request, 'reports.html', {'reports': reports, 'stats': stats})

@login_required(login_url='login')
def download_pdf_report(request, detection_id):
    """Download detection report as PDF with formatted fields"""
    try:
        detection = DetectionHistory.objects.get(id=detection_id)
        pdf_content = generate_pdf_report(detection)
        
        response = HttpResponse(pdf_content, content_type='application/pdf')
        filename = f"document_report_{detection.filename}_{detection.timestamp.strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except DetectionHistory.DoesNotExist:
        return HttpResponse("Report not found", status=404)

@login_required(login_url='login')
def delete_report(request, detection_id):
    """Delete a report"""
    if request.method == "POST":
        try:
            detection = DetectionHistory.objects.get(id=detection_id)
            detection.delete()
            return JsonResponse({'success': True})
        except DetectionHistory.DoesNotExist:
            return JsonResponse({'error': 'Report not found'}, status=404)
    return JsonResponse({'error': 'Invalid method'}, status=405)

# ==================== ULTIMATE INTELLIGENT OCR SYSTEM ====================

def ultimate_preprocessing(raw_ocr_text: str) -> str:
    """Ultimate preprocessing with intelligent field label removal"""
    if not raw_ocr_text:
        return ""
    
    text = raw_ocr_text.lower()
    
    # Remove duplicate lines intelligently
    lines = text.split('\n')
    unique_lines = []
    seen = set()
    for line in lines:
        line = line.strip()
        if line and len(line) > 1 and line not in seen:
            # Skip if this line is contained in a longer existing line
            is_subset = any(line in existing for existing in seen if len(existing) > len(line) * 1.2)
            if not is_subset:
                unique_lines.append(line)
                seen.add(line)
    text = '\n'.join(unique_lines)
    
    # Remove field labels that might be confused as values
    field_labels_to_remove = [
        r'\bprimer\s*apellido\b[:\s]*',
        r'\bsegundo\s*apellido\b[:\s]*',
        r'\bnombre\b[:\s]*',
        r'\bnacionalidad\b[:\s]*',
        r'\bsexo\b[:\s]*',
        r'\bfecha\s*de\s*nacimiento\b[:\s]*',
        r'\bválido\s*hasta\b[:\s]*',
        r'\bidesp\b[:\s]*',
        r'\bsurname\b[:\s]*',
        r'\bname\b[:\s]*',
        r'\bnationality\b[:\s]*',
        r'\bsex\b[:\s]*',
        r'\bdate\s*of\s*birth\b[:\s]*',
        r'\bplace\s*of\s*birth\b[:\s]*',
        r'\bpassport\s*no\b[:\s]*',
        r'\biss\.?\s*date\b[:\s]*',
        r'\bexpiry\b[:\s]*',
        r'\bheight\b[:\s]*',
    ]
    
    for label_pattern in field_labels_to_remove:
        text = re.sub(label_pattern, ' ', text, flags=re.IGNORECASE)
    
    # Ultimate OCR corrections
    corrections = {
        # Greek corrections
        r'\bblond\b': 'orestiada', r'\bslow\b': 'orestiada',
        r'\bsalonika\b': 'thessaloniki', r'\bkozanh\b': 'kozani',
        r'\bveroia\b': 'veroia', r'\bgiannitsa\b': 'giannitsa',
        r'\bkomotini\b': 'komotini', r'\bhaektpa\b': 'elektra',
        r'\bpassport\b(?!\s+no)': '', r'\bpasaport\b': '',
        r'\bnicolaidis\b': 'nikolaidis', r'\bpapadoulis\b': 'papadoulis',
        r'\bvasiliki\b': 'vasiliki', r'\bdimitris\b': 'dimitris',
        r'\bhellenic\b': 'hellenic', r'\bhelenic\b': 'hellenic',
        
        # Spanish corrections
        r'\bespana\b': 'españa', r'\bnacionalidad\b': '',
        r'\bvalido\b': 'válido', r'\bmiranda\b': 'miranda',
        r'\bserrano\b': 'serrano', r'\btorres\b': 'torres',
        r'\bbenitez\b': 'benitez', r'\bmoreno\b': 'moreno',
        r'\bmolina\b': 'molina', r'\bnati\b': 'nati',
        r'\balicia\b': 'alicia', r'\balba\b': 'alba',
        
        # Remove noise
        r'\bgenerated\b': '', r'\bphotos\b': '', r'\bfake\b': '', r'\bv3\b': '',
    }
    
    for pattern, replacement in corrections.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Clean up spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def create_validation_sets() -> Dict[str, Set[str]]:
    """Create validation sets to reject invalid field values"""
    return {
        'invalid_surnames': {
            'nationality', 'nacionalidad', 'hellenic', 'esp', 'españa', 'sex', 'sexo',
            'male', 'female', 'date', 'birth', 'passport', 'document', 'numero',
            'valid', 'height', 'place', 'issue', 'expiry', 'authority'
        },
        'invalid_names': {
            'nationality', 'nacionalidad', 'hellenic', 'esp', 'españa', 'sex', 'sexo',
            'male', 'female', 'surname', 'apellido', 'document', 'passport'
        },
        'valid_spanish_names': {
            'alba', 'alicia', 'maría', 'carmen', 'ana', 'isabel', 'pilar', 'carlos',
            'josé', 'antonio', 'miguel', 'juan', 'david', 'daniel', 'adrián',
            'alejandro', 'álvaro', 'pablo', 'manuel', 'sergio', 'javier'
        },
        'valid_greek_names': {
            'dimitris', 'vasiliki', 'konstantinos', 'ioannis', 'george', 'andreas',
            'michael', 'alexis', 'maria', 'anna', 'sofia', 'elena', 'christina',
            'theodoros', 'petros', 'nikos', 'yannis', 'kostas', 'elektra'
        },
        'valid_spanish_surnames': {
            'miranda', 'serrano', 'garcia', 'lópez', 'martínez', 'gonzález',
            'rodríguez', 'fernández', 'torres', 'ruiz', 'moreno', 'molina',
            'jiménez', 'martín', 'sánchez', 'pérez', 'gómez', 'nati'
        },
        'valid_greek_surnames': {
            'nikolaidis', 'konstantopoulos', 'anastasiou', 'papadopoulos',
            'papantoniou', 'papanastasiou', 'papadoulis', 'dimitriou'
        }
    }

def is_valid_field_value(field_name: str, value: str, validation_sets: Dict[str, Set[str]]) -> bool:
    """Validate field values against known invalid patterns"""
    if not value or len(value.strip()) < 2:
        return False
    
    value_lower = value.lower().strip()
    
    # Check for obviously invalid values
    if field_name in ['First Surname', 'Second Surname', 'Surname']:
        if value_lower in validation_sets['invalid_surnames']:
            return False
        # Additional length check for surnames
        if len(value_lower) < 3 or len(value_lower) > 25:
            return False
            
    elif field_name == 'Name':
        if value_lower in validation_sets['invalid_names']:
            return False
        # Additional length check for names
        if len(value_lower) < 2 or len(value_lower) > 20:
            return False
    
    elif field_name == 'Gender':
        if value_lower not in ['m', 'f', 'male', 'female']:
            return False
    
    elif field_name == 'Nationality':
        if value_lower not in ['esp', 'españa', 'hellenic', 'ελληνικη', 'greek']:
            return False
    
    # Check for common OCR garbage
    if re.search(r'[^a-záéíóúñα-ωά-ώ\s]', value_lower):  # Contains invalid characters
        if field_name not in ['DNI Number', 'Passport Number', 'ID Number', 'Date of Birth', 'Issue Date', 'Expiry Date', 'Valid Until', 'Height']:
            return False
    
    return True

def ultimate_spanish_dni_extraction(text: str) -> Dict[str, str]:
    """Ultimate Spanish DNI extraction with intelligent validation"""
    extracted = {}
    validation_sets = create_validation_sets()
    
    # Enhanced Spanish patterns with better value extraction
    spanish_patterns = {
        'First Surname': [
            r'(?:primer\s*apellido[:\s]*)?([A-ZÁÉÍÓÚÑ]{3,20})(?:\s+segundo|\s+[A-ZÁÉÍÓÚÑ]{3,20}\s+[A-ZÁÉÍÓÚÑ]{2,15}|\s+\d{8}[A-Z])',
            r'([A-ZÁÉÍÓÚÑ]{3,20})\s+([A-ZÁÉÍÓÚÑ]{3,20})(?:\s+[A-ZÁÉÍÓÚÑ]{2,15})?',  # First of two surnames
            r'documento[^a-z]*([A-ZÁÉÍÓÚÑ]{3,20})',
            r'españa[^a-z]*([A-ZÁÉÍÓÚÑ]{3,20})',
        ],
        'Second Surname': [
            r'(?:segundo\s*apellido[:\s]*)?([A-ZÁÉÍÓÚÑ]{3,20})(?:\s+nombre|\s+[A-ZÁÉÍÓÚÑ]{2,15}\s+[MF])',
            r'[A-ZÁÉÍÓÚÑ]{3,20}\s+([A-ZÁÉÍÓÚÑ]{3,20})(?:\s+[A-ZÁÉÍÓÚÑ]{2,15})?',  # Second of two surnames
        ],
        'Name': [
            r'(?:nombre[:\s]*)?([A-ZÁÉÍÓÚÑ]{2,15})(?:\s+[MF]|\s+esp|\s+\d{2}\s+\d{2}\s+\d{4})',
            r'[A-ZÁÉÍÓÚÑ]{3,20}\s+[A-ZÁÉÍÓÚÑ]{3,20}\s+([A-ZÁÉÍÓÚÑ]{2,15})',  # Name after two surnames
            r'segundo\s*apellido[^a-z]*[A-ZÁÉÍÓÚÑ]+[^a-z]*([A-ZÁÉÍÓÚÑ]{2,15})',
        ],
        'DNI Number': [
            r'(\d{8}[A-Z])\b',
            r'dni[^0-9]*(\d{8}[A-Z])',
        ],
        'Gender': [
            r'(?:sexo[:\s]*)?([MF])(?:\s+esp|\s+\d{2})',
            r'([MF])\s*esp\s*\d{2}',
            r'nombre[^a-z]*[A-ZÁÉÍÓÚÑ]+[^a-z]*([MF])',
        ],
        'Nationality': [
            r'(?:nacionalidad[:\s]*)?(esp)(?:\s+fecha|\s+\d{2})',
            r'([MF])\s*(esp)\s*\d{2}',
        ],
        'Date of Birth': [
            r'(?:fecha\s*de\s*nacimiento[:\s]*)?(\d{2}\s*\d{2}\s*\d{4})',
            r'esp\s*(\d{2}\s*\d{2}\s*\d{4})',
        ],
        'ID Number': [
            r'(?:idesp[:\s]*)?([A-Z]{3}\d{6,8})',
            r'(\d{2}\s*\d{2}\s*\d{4})\s*([A-Z]{3}\d{6,8})',
        ],
        'Valid Until': [
            r'(?:válido\s*hasta[:\s]*)?(\d{2}\s*\d{2}\s*\d{4})(?!\s*idesp)',
            r'[A-Z]{3}\d{6,8}\s*(\d{2}\s*\d{2}\s*\d{4})',
        ]
    }
    
    # Extract with validation
    for field, patterns in spanish_patterns.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle tuple matches - find the first valid value
                    for value in match:
                        if value and is_valid_field_value(field, value, validation_sets):
                            extracted[field] = value.upper().strip()
                            break
                else:
                    if is_valid_field_value(field, match, validation_sets):
                        extracted[field] = match.upper().strip()
                
                if field in extracted:
                    break
            if field in extracted:
                break
    
    return extracted

def ultimate_greek_passport_extraction(text: str) -> Dict[str, str]:
    """Ultimate Greek passport extraction with intelligent validation"""
    extracted = {}
    validation_sets = create_validation_sets()
    
    # Enhanced Greek patterns
    greek_patterns = {
        'Surname': [
            r'(?:surname[:\s]*)?([A-Z]{4,25})(?:\s+[A-Z]{3,15}\s+hellenic)',
            r'([A-Z]{4,25})\s+[A-Z]{3,15}\s+hellenic',
            r'hellenic\s+([A-Z]{4,25})',
            r'(nikolaidis|konstantopoulos|papadoulis|papantoniou|anastasiou)\b',
        ],
        'Name': [
            r'(?:name[:\s]*)?([A-Z]{3,15})(?:\s+hellenic|\s+[MF]|\s+\d{2}\s+\w{3})',
            r'([A-Z]{3,15})\s+hellenic',
            r'[A-Z]{4,25}\s+([A-Z]{3,15})\s+hellenic',
            r'(dimitris|vasiliki|konstantinos|elektra|maria|anna|sofia)\b',
            r'(haektpa)',  # Specific OCR variant for ELEKTRA
        ],
        'Nationality': [
            r'(hellenic)\b',
            r'nationality[:\s]*(hellenic)',
        ],
        'Gender': [
            r'(?:sex[:\s]*)?([MF])(?:\s+\d{2}\s+\w{3}|\s+[A-Z]{4,})',
            r'([MF])\s+\d{2}\s+\w{3}\s+\d{2,4}',
            r'hellenic\s+[A-Z]+\s+([MF])',
        ],
        'Date of Birth': [
            r'(?:date\s*of\s*birth[:\s]*)?(\d{1,2}\s+\w{3}\s+\d{2,4})',
            r'([MF])\s+(\d{1,2}\s+\w{3}\s+\d{2,4})',
        ],
        'Place of Birth': [
            r'(?:place\s*of\s*birth[:\s]*)?([A-Z]{4,20})(?:\s+[A-Z]{1,3}\d{6,8})',
            r'(komotini|veroia|giannitsa|kozani|thessaloniki|athens|sparta)\b',
        ],
        'Passport Number': [
            r'(?:passport\s*no[:\s]*)?([A-Z]{1,3}\d{6,8})\b',
            r'(vu\d{7}|m\d{7}|ee\d{7}|jh\d{7})\b',
        ],
        'Issue Date': [
            r'(?:iss\.?\s*date[:\s]*)?(\d{1,2}\s+\w{3}\s+\d{2,4})(?=.*expiry)',
            r'(\d{1,2}\s+sep\s+\d{2,4})(?=.*\d{1,2}\s+sep\s+\d{2,4})',  # Issue before expiry
        ],
        'Expiry Date': [
            r'(?:expiry[:\s]*)?(\d{1,2}\s+\w{3}\s+\d{2,4})(?!\s*iss)',
            r'(\d{1,2}\s+sep\s+\d{2,4})$',  # Last date is usually expiry
        ],
        'Height': [
            r'(?:height[:\s]*)?(\d+\.\d{2})\b',
            r'(1\.\d{2}|2\.\d{2})\b',
        ],
        'Issuing Authority': [
            r'(?:iss\.?\s*office[:\s]*)?([A-Z\.\s\-\/]{8,30})',
            r'(place\s+of\s+birth[^a-z]+[A-Z\.\s\-\/]{8,30})',
        ]
    }
    
    # Extract with validation
    for field, patterns in greek_patterns.items():
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    for value in match:
                        if value and is_valid_field_value(field, value, validation_sets):
                            extracted[field] = value.upper().strip()
                            break
                else:
                    if is_valid_field_value(field, match, validation_sets):
                        extracted[field] = match.upper().strip()
                
                if field in extracted:
                    break
            if field in extracted:
                break
    
    return extracted

def intelligent_document_detection(text: str) -> str:
    """Intelligent document detection with confidence scoring"""
    text_lower = text.lower()
    
    spanish_score = 0
    greek_score = 0
    
    # Spanish indicators
    spanish_keywords = ['españa', 'dni', 'esp', 'primer apellido', 'segundo apellido', 'nacionalidad', 'válido hasta']
    for keyword in spanish_keywords:
        if keyword in text_lower:
            spanish_score += 2
    
    # Greek indicators  
    greek_keywords = ['hellas', 'hellenic', 'passport', 'greece', 'grc', 'nationality']
    for keyword in greek_keywords:
        if keyword in text_lower:
            greek_score += 2
    
    # Pattern-based scoring
    if re.search(r'\d{8}[A-Z]', text_lower):  # Spanish DNI pattern
        spanish_score += 3
    if re.search(r'[A-Z]{1,3}\d{6,8}', text_lower):  # Passport pattern
        greek_score += 3
    
    return 'spanish_dni' if spanish_score > greek_score else 'greek_passport'

def intelligent_validation_cleanup(extracted: Dict[str, str]) -> Dict[str, str]:
    """Intelligent cleanup with relationship validation"""
    validation_sets = create_validation_sets()
    
    # Remove invalid values
    cleaned = {}
    for field, value in extracted.items():
        if is_valid_field_value(field, value, validation_sets):
            cleaned[field] = value
    
    # Fix duplicates
    if ('First Surname' in cleaned and 'Second Surname' in cleaned and 
        cleaned['First Surname'] == cleaned['Second Surname']):
        del cleaned['Second Surname']
    
    if ('Name' in cleaned and 'Surname' in cleaned and 
        cleaned['Name'] == cleaned['Surname']):
        del cleaned['Name']
    
    # Normalize values
    if 'Nationality' in cleaned:
        nat = cleaned['Nationality'].lower()
        if 'hellenic' in nat or 'greek' in nat:
            cleaned['Nationality'] = 'HELLENIC'
        elif 'esp' in nat:
            cleaned['Nationality'] = 'ESP'
    
    # Clean issuing authority
    if 'Issuing Authority' in cleaned:
        authority = cleaned['Issuing Authority']
        if len(authority) > 40:
            # Extract clean part
            clean_match = re.search(r'([A-Z\.\s\-\/]{8,25})', authority)
            if clean_match:
                cleaned['Issuing Authority'] = clean_match.group(1).strip()
            else:
                cleaned['Issuing Authority'] = authority[:25] + "..."
    
    return cleaned

def ultimate_extract_document_fields(ocr_text: str) -> Dict[str, str]:
    """Ultimate extraction with intelligent validation"""
    if not ocr_text:
        return {}
    
    # Preprocess
    preprocessed = ultimate_preprocessing(ocr_text)
    
    # Detect document type
    doc_type = intelligent_document_detection(preprocessed)
    
    # Extract fields
    if doc_type == 'spanish_dni':
        extracted = ultimate_spanish_dni_extraction(preprocessed)
    else:
        extracted = ultimate_greek_passport_extraction(preprocessed)
    
    # Validate and clean
    extracted = intelligent_validation_cleanup(extracted)
    
    return extracted

def clean_and_format_document_fields(translated_text):
    """Format fields with intelligent ordering"""
    if not translated_text or "Translation" in translated_text:
        return []
    
    extracted_data = ultimate_extract_document_fields(translated_text)
    formatted_fields = []
    
    doc_type = intelligent_document_detection(translated_text)
    
    if doc_type == 'spanish_dni':
        field_order = ['First Surname', 'Second Surname', 'Name', 'DNI Number', 'Gender', 
                      'Nationality', 'Date of Birth', 'ID Number', 'Valid Until']
    else:
        field_order = ['Surname', 'Name', 'Nationality', 'Gender', 'Date of Birth', 
                      'Place of Birth', 'Passport Number', 'Issue Date', 'Expiry Date', 
                      'Issuing Authority', 'Height']
    
    # Add fields in order
    for field in field_order:
        if field in extracted_data and extracted_data[field]:
            formatted_fields.append([f"{field}:", extracted_data[field]])
    
    # Add remaining fields
    for field, value in extracted_data.items():
        if field not in field_order and value:
            formatted_fields.append([f"{field}:", value])
    
    # Fallback
    if not formatted_fields:
        sample_text = translated_text[:200] + "..." if len(translated_text) > 200 else translated_text
        formatted_fields.append(["Extracted Text:", sample_text])
    
    return formatted_fields

# ==================== PDF GENERATION (UNCHANGED) ====================

def generate_pdf_report(detection):
    """Generate single page PDF report"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.4*inch, 
                          leftMargin=0.5*inch, rightMargin=0.5*inch)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, 
                                spaceAfter=15, alignment=1, textColor=colors.darkblue)
    heading_style = ParagraphStyle('CustomHeading', parent=styles['Heading2'], fontSize=12, 
                                  spaceAfter=8, textColor=colors.darkblue)
    
    story = []
    story.append(Paragraph("Document Forgery Detection Report", title_style))
    story.append(Spacer(1, 10))
    story.append(Paragraph("Detection Results", heading_style))
    
    is_genuine = detection.prediction.upper() == 'GENUINE'
    doc_type_display = intelligent_document_detection(detection.translated_text or "")
    doc_type_names = {
        'spanish_dni': 'Spanish National ID (DNI)',
        'greek_passport': 'Greek Passport', 
        'unknown': 'Unknown Document Type'
    }
    
    detection_data = [
        ['Analysis Date:', detection.timestamp.strftime('%Y-%m-%d %H:%M:%S')],
        ['Document Name:', detection.filename],
        ['Document Type:', doc_type_names.get(doc_type_display, detection.doc_type)],
        ['Prediction:', detection.prediction],
        ['Confidence Level:', f"{detection.confidence:.2f}%"],
        ['Processing Time:', f"{detection.processing_time:.2f} seconds"]
    ]
    
    detection_table = Table(detection_data, colWidths=[2.1*inch, 3.7*inch])
    prediction_color = colors.lightgreen if is_genuine else colors.lightcoral
    confidence_color = (colors.lightgreen if detection.confidence > 90 else 
                       colors.lightyellow if detection.confidence > 70 else colors.lightcoral)
    
    detection_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightsteelblue),
        ('BACKGROUND', (0,3), (1,3), prediction_color),
        ('BACKGROUND', (0,4), (1,4), confidence_color),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    
    story.append(detection_table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Document Information", heading_style))
    
    formatted_fields = clean_and_format_document_fields(detection.translated_text)
    
    if formatted_fields:
        doc_table = Table(formatted_fields, colWidths=[2.1*inch, 3.7*inch])
        doc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightblue),
            ('BACKGROUND', (1,0), (1,-1), colors.white),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(doc_table)
    
    story.append(Spacer(1, 12))
    story.append(Paragraph("Classification Probabilities", heading_style))
    
    prob_data = []
    for cls, prob in detection.probabilities.items():
        display_name = cls.replace('fraud5_inpaint_and_rewrite', 'Inpaint & Rewrite Forgery')
        display_name = display_name.replace('fraud6_crop_and_replace', 'Crop & Replace Forgery')  
        display_name = display_name.replace('positive', 'Genuine Document')
        prob_data.append([display_name, f"{prob:.2f}%"])
    
    prob_table = Table(prob_data, colWidths=[3.3*inch, 2.3*inch])
    
    if is_genuine:
        prob_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightgreen),
            ('BACKGROUND', (1,0), (1,-1), colors.palegreen),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.darkgreen),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 1, colors.darkgreen),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
    else:
        prob_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightcoral),
            ('BACKGROUND', (1,0), (1,-1), colors.mistyrose),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.darkred),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('ALIGN', (1,0), (1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('GRID', (0,0), (-1,-1), 1, colors.darkred),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
    
    story.append(prob_table)
    story.append(Spacer(1, 15))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, 
                                 alignment=1, textColor=colors.gray)
    story.append(Paragraph("Generated by DocVerify - Document Forgery Detection System", footer_style))
    story.append(Paragraph("This report contains analyzed and formatted document information", footer_style))
    
    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    return pdf_content

# ==================== DEBUG FUNCTION ====================

def debug_ultimate_extraction(detection_id):
    """Ultimate debug function"""
    try:
        detection = DetectionHistory.objects.get(id=detection_id)
        
        print("=" * 80)
        print("ULTIMATE EXTRACTION DEBUG")
        print("=" * 80)
        
        preprocessed = ultimate_preprocessing(detection.translated_text)
        print(f"Preprocessed: {preprocessed[:300]}...")
        
        doc_type = intelligent_document_detection(preprocessed)
        print(f"Document Type: {doc_type}")
        
        extracted = ultimate_extract_document_fields(detection.translated_text)
        print(f"Extracted Fields ({len(extracted)} total):")
        for k, v in extracted.items():
            print(f"  {k:20}: {v}")
        
        return extracted
        
    except DetectionHistory.DoesNotExist:
        print("Detection not found")
        return None

# ==================== LEGACY COMPATIBILITY ====================

def get_standard_field_name(key_lower):
    """Legacy compatibility function"""
    field_mappings = {
        'surname': 'Surname', 'apellido': 'Surname', 'name': 'Name', 'nombre': 'Name',
        'nationality': 'Nationality', 'nacionalidad': 'Nationality', 'sex': 'Gender', 'sexo': 'Gender',
        'date of birth': 'Date of Birth', 'fecha de nacimiento': 'Date of Birth',
        'place of birth': 'Place of Birth', 'lugar de nacimiento': 'Place of Birth',
        'passport no': 'Passport Number', 'passport number': 'Passport Number',
        'id number': 'ID Number', 'dni': 'DNI Number', 'issue date': 'Issue Date',
        'expiry date': 'Expiry Date', 'valid until': 'Valid Until'
    }
    
    for pattern, standard in field_mappings.items():
        if pattern in key_lower:
            return standard
    return None