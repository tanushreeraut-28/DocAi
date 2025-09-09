from django.db import models

# Create your models here.
from django.db import models
import json

class DetectionHistory(models.Model):
    filename = models.CharField(max_length=255)
    doc_type = models.CharField(max_length=100, default="Unknown")
    prediction = models.CharField(max_length=20)
    confidence = models.FloatField()
    processing_time = models.FloatField()
    extracted_text = models.TextField(blank=True, null=True)
    translated_text = models.TextField(blank=True, null=True)
    probabilities = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.filename} - {self.prediction} ({self.confidence:.2f}%)"
    
    def get_probabilities_display(self):
        """Format probabilities for display"""
        return [(k, f"{v:.2f}%") for k, v in self.probabilities.items()]
