from django.contrib import admin

from .models import Document, ReadingProgress, ReadingSession


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'file_type', 'word_count', 'uploaded_at')


@admin.register(ReadingSession)
class ReadingSessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'user', 'document', 'started_at', 'reading_speed_wpm')


@admin.register(ReadingProgress)
class ReadingProgressAdmin(admin.ModelAdmin):
    list_display = ('document', 'progress_percent', 'status', 'last_read_at')
