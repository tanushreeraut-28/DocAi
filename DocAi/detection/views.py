from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import tempfile
import os
from datetime import datetime
import re
import io
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors

from .models import DetectionHistory
from detection.forgery_detector import get_detector

# ==================== DOCUMENT DETECTION VIEWS ====================

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

# ==================== PDF GENERATION HELPERS ====================

def clean_and_format_document_fields(translated_text):
    """Clean and format document fields for PDF display"""
    if not translated_text or "Translation" in translated_text:
        return []
    
    # Remove extra characters commonly found in OCR
    cleaned_text = re.sub(r'[<>]+', '', translated_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    lines = cleaned_text.split('\n')
    formatted_fields = []
    
    # Field mappings for standardization
    field_mappings = {
        'surname': 'Surname',
        'apellido': 'Surname', 
        'primer apellido': 'First Surname',
        'segundo apellido': 'Second Surname',
        'name': 'Name',
        'nombre': 'Name',
        'nationality': 'Nationality',
        'nacionalidad': 'Nationality',
        'sex': 'Gender',
        'sexo': 'Gender',
        'date of birth': 'Date of Birth',
        'fecha de nacimiento': 'Date of Birth',
        'place of birth': 'Place of Birth',
        'lugar de nacimiento': 'Place of Birth',
        'date of issue': 'Issue Date',
        'fecha de expedicion': 'Issue Date',
        'date of expiry': 'Expiry Date',
        'valid until': 'Valid Until',
        'valido hasta': 'Valid Until',
        'passport no': 'Passport Number',
        'numero de pasaporte': 'Passport Number',
        'id number': 'ID Number',
        'dni': 'ID Number',
        'idesp': 'ID Number'
    }
    
    for line in lines:
        line = line.strip()
        if ':' in line and line:
            try:
                key, value = line.split(':', 1)
                key_clean = key.strip().lower()
                value_clean = value.strip()
                
                # Skip empty values
                if not value_clean:
                    continue
                
                # Map to standardized field names
                standard_name = None
                for pattern, standard in field_mappings.items():
                    if pattern in key_clean:
                        standard_name = standard
                        break
                
                if standard_name:
                    formatted_fields.append([f"{standard_name}:", value_clean])
                
            except ValueError:
                continue
    
    return formatted_fields

def generate_pdf_report(detection):
    """Generate formatted PDF report with only translated text"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=inch, bottomMargin=inch)
    
    # Get styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # Center alignment
        textColor=colors.darkblue
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        spaceAfter=15,
        textColor=colors.darkblue
    )
    
    story = []
    
    # Title
    story.append(Paragraph("Document Forgery Detection Report", title_style))
    story.append(Spacer(1, 20))
    
    # Detection Results Section
    story.append(Paragraph("Detection Results", heading_style))
    
    detection_data = [
        ['Analysis Date:', detection.timestamp.strftime('%Y-%m-%d %H:%M:%S')],
        ['Document Name:', detection.filename],
        ['Document Type:', detection.doc_type],
        ['Prediction:', detection.prediction],
        ['Confidence Level:', f"{detection.confidence:.2f}%"],
        ['Processing Time:', f"{detection.processing_time:.2f} seconds"]
    ]
    
    detection_table = Table(detection_data, colWidths=[2.2*inch, 3.8*inch])
    detection_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightsteelblue),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ('FONTNAME', (1,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
    ]))
    
    story.append(detection_table)
    story.append(Spacer(1, 25))
    
    # Document Information Section (Formatted Fields)
    story.append(Paragraph("Document Information", heading_style))
    
    formatted_fields = clean_and_format_document_fields(detection.translated_text)
    
    if formatted_fields:
        doc_table = Table(formatted_fields, colWidths=[2.2*inch, 3.8*inch])
        doc_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.lightyellow),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
            ('FONTNAME', (1,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 11),
            ('BOTTOMPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('GRID', (0,0), (-1,-1), 1, colors.black),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE')
        ]))
        story.append(doc_table)
    else:
        story.append(Paragraph("No structured document information available.", styles['Normal']))
    
    story.append(Spacer(1, 25))
    
    # Classification Probabilities
    story.append(Paragraph("Classification Probabilities", heading_style))
    
    prob_data = []
    for cls, prob in detection.probabilities.items():
        display_name = cls.replace('fraud5_inpaint_and_rewrite', 'Inpaint & Rewrite Forgery')
        display_name = display_name.replace('fraud6_crop_and_replace', 'Crop & Replace Forgery')
        display_name = display_name.replace('positive', 'Genuine Document')
        prob_data.append([display_name, f"{prob:.2f}%"])
    
    prob_table = Table(prob_data, colWidths=[3.5*inch, 2.5*inch])
    prob_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (0,-1), colors.lightcoral),
        ('BACKGROUND', (1,0), (1,-1), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,-1), colors.black),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 11),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    
    story.append(prob_table)
    story.append(Spacer(1, 30))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        alignment=1,
        textColor=colors.gray
    )
    
    story.append(Paragraph("Generated by DocVerify - Document Forgery Detection System", footer_style))
    story.append(Paragraph("This report contains only translated and formatted document information", footer_style))
    
    # Build PDF
    doc.build(story)
    pdf_content = buffer.getvalue()
    buffer.close()
    
    return pdf_content
