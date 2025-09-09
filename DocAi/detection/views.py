from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponse
import tempfile
import os
from datetime import datetime

from .models import DetectionHistory
from detection.forgery_detector import get_detector


# ==================== DOCUMENT DETECTION VIEWS ====================

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
            # Save temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp_file:
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


def reports_history(request):
    """List of past reports"""
    reports = DetectionHistory.objects.all().order_by('-timestamp')[:50]
    stats = {
        'total_reports': DetectionHistory.objects.count(),
        'forged_count': DetectionHistory.objects.filter(prediction='FORGED').count(),
        'genuine_count': DetectionHistory.objects.filter(prediction='GENUINE').count(),
    }
    return render(request, 'reports.html', {'reports': reports, 'stats': stats})


def download_report(request, detection_id):
    """Download detection report as .txt"""
    try:
        detection = DetectionHistory.objects.get(id=detection_id)

        content = generate_downloadable_report(detection)
        response = HttpResponse(content, content_type="text/plain")
        filename = f"forgery_report_{detection.filename}_{detection.timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
    except DetectionHistory.DoesNotExist:
        return HttpResponse("Report not found", status=404)


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


# ==================== HELPERS ====================

def generate_downloadable_report(detection):
    """Format detection report for downloading"""
    lines = []
    lines.append("=" * 60)
    lines.append("      Document Forgery Detection Report")
    lines.append("=" * 60)
    lines.append(f"Date & Time: {detection.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Document Name: {detection.filename}")
    lines.append(f"Document Type: {detection.doc_type}")
    lines.append("")
    lines.append(f"Prediction: {detection.prediction}")
    lines.append(f"Confidence: {detection.confidence:.2f}%")
    lines.append(f"Processing Time: {detection.processing_time:.2f} seconds")
    lines.append("")
    lines.append("Class Probabilities:")
    for cls, prob in detection.probabilities.items():
        lines.append(f"  {cls}: {prob:.2f}%")
    lines.append("")
    lines.append("Extracted Text:")
    lines.append(detection.extracted_text or "N/A")
    lines.append("")
    lines.append("Translated Text:")
    lines.append(detection.translated_text or "N/A")
    lines.append("=" * 60)
    lines.append("Generated by Document Forgery Detection System")
    lines.append("=" * 60)
    return "\n".join(lines)
