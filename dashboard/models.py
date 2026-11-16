"""
BionixReader - dashboard/models.py  (vertical slice: documents & reading)

ERD entity        -> Django model / table
---------------------------------------------------------------
DOCUMENTS         -> Document         (documents)
READING_SESSIONS  -> ReadingSession   (reading_sessions)
READING_PROGRESS  -> ReadingProgress  (reading_progress)

Relationships
---------------------------------------------------------------
USERS     1 - M DOCUMENTS          (ForeignKey)
USERS     1 - M READING_SESSIONS   (ForeignKey)
DOCUMENTS 1 - M READING_SESSIONS   (ForeignKey)
DOCUMENTS 1 - 1 READING_PROGRESS   (OneToOneField, unique FK)

(USER_PROFILES and USER_STATS live in accounts/models.py.)
"""

from django.conf import settings
from django.db import models

# USERS (auth_user) is Django's built-in User model.
User = settings.AUTH_USER_MODEL


class Document(models.Model):
    """DOCUMENTS - files uploaded by a user (USERS 1-M DOCUMENTS)."""

    document_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        db_column='user_id', related_name='documents',
    )
    title = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    file_type = models.CharField(max_length=20)
    word_count = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    last_opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'documents'

    def __str__(self):
        return self.title


class ReadingSession(models.Model):
    """READING_SESSIONS - one sitting of reading a document.

    USERS 1-M READING_SESSIONS and DOCUMENTS 1-M READING_SESSIONS.
    """

    session_id = models.AutoField(primary_key=True)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE,
        db_column='user_id', related_name='reading_sessions',
    )
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE,
        db_column='document_id', related_name='reading_sessions',
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    words_read = models.IntegerField(default=0)
    reading_speed_wpm = models.IntegerField(default=0)

    class Meta:
        db_table = 'reading_sessions'

    def __str__(self):
        return f'Session {self.session_id}: {self.user} - {self.document}'


class ReadingProgress(models.Model):
    """READING_PROGRESS - where the user is in a document (1-1 with DOCUMENTS)."""

    progress_id = models.AutoField(primary_key=True)
    document = models.OneToOneField(
        Document, on_delete=models.CASCADE,
        db_column='document_id', related_name='progress',
    )
    progress_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    current_position = models.IntegerField(default=0)
    status = models.CharField(max_length=20, default='not_started')
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'reading_progress'
        verbose_name_plural = 'reading progress'

    def __str__(self):
        return f'{self.document} - {self.progress_percent}%'
