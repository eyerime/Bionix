import json
import os
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_POST

from accounts.models import UserProfile, UserStats

from .forms import UploadForm
from .models import Document, ReadingProgress, ReadingSession
from .reading import bionize, clamp_intensity
from .stats import recalculate_stats

THEMES = ('dark', 'light')
FONT_SIZE_CHOICES = (('sm', 'Small'), ('md', 'Medium'), ('lg', 'Large'), ('xl', 'Extra large'))
FONT_SIZES = tuple(k for k, _ in FONT_SIZE_CHOICES)
COMPLETE_AT = 98.0     # % scrolled at which a document counts as finished
MAX_WPM = 1200         # ignore absurd speeds caused by fast scrolling
MIN_WPM_SECONDS = 10   # sessions shorter than this don't produce a speed


@login_required
def home(request):
    """Dashboard: reading stats cards + the user's document library."""
    stats, _ = UserStats.objects.get_or_create(user=request.user)
    documents = (Document.objects.filter(user=request.user)
                 .select_related('progress').order_by('-uploaded_at'))
    completed = ReadingProgress.objects.filter(
        document__user=request.user, status='completed').count()

    return render(request, 'dashboard/dashboard.html', {
        'stats': stats,
        'documents': documents,
        'total_documents': documents.count(),
        'completed_documents': completed,
    })


@login_required
def upload(request):
    form = UploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        f = form.cleaned_data['file']
        raw = f.read()
        text = raw.decode('utf-8', errors='replace')
        ext = os.path.splitext(f.name)[1].lower()

        safe_name = get_valid_filename(os.path.basename(f.name))
        saved_path = default_storage.save(
            f'documents/{request.user.id}/{safe_name}', ContentFile(raw))

        title = form.cleaned_data['title'].strip() or os.path.splitext(f.name)[0]
        doc = Document.objects.create(
            user=request.user,
            title=title,
            file_path=saved_path,
            file_type=ext.lstrip('.'),
            word_count=len(text.split()),
        )
        ReadingProgress.objects.create(document=doc)

        messages.success(request, f'"{doc.title}" uploaded ({doc.word_count:,} words).')
        return redirect('dashboard:home')

    return render(request, 'dashboard/upload.html', {'form': form})


@login_required
@require_POST
def delete_document(request, pk):
    doc = get_object_or_404(Document, pk=pk, user=request.user)
    title = doc.title
    try:
        default_storage.delete(doc.file_path)
    except OSError:
        pass
    doc.delete()
    messages.info(request, f'"{title}" was removed.')
    return redirect('dashboard:home')


# ---------------------------------------------------------------- reader --

def _apply_progress(doc, percent):
    """Save reading position/status for a document. Returns the progress row."""
    percent = max(0.0, min(100.0, float(percent)))
    progress, _ = ReadingProgress.objects.get_or_create(document=doc)

    progress.current_position = int(round(percent * 100))   # resume point (basis points)
    progress.progress_percent = Decimal(str(round(
        max(float(progress.progress_percent), percent), 2)))  # furthest point reached
    if progress.status != 'completed':
        if float(progress.progress_percent) >= COMPLETE_AT:
            progress.status = 'completed'
        elif float(progress.progress_percent) > 0:
            progress.status = 'in_progress'
    progress.last_read_at = timezone.now()
    progress.save()
    return progress


@login_required
def reader(request, pk):
    doc = get_object_or_404(Document, pk=pk, user=request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    progress, _ = ReadingProgress.objects.get_or_create(document=doc)

    try:
        with default_storage.open(doc.file_path) as fh:
            text = fh.read().decode('utf-8', errors='replace')
    except (OSError, ValueError):
        messages.error(request, 'The file for this document could not be found.')
        return redirect('dashboard:home')

    doc.last_opened_at = timezone.now()
    doc.save(update_fields=['last_opened_at'])

    resume_percent = progress.current_position / 100
    if progress.status == 'completed' and resume_percent >= COMPLETE_AT:
        resume_percent = 0   # finished documents reopen from the top
    session = ReadingSession.objects.create(
        user=request.user, document=doc, started_at=timezone.now())

    return render(request, 'dashboard/reader.html', {
        'doc': doc,
        'content': bionize(text, profile.fixation_intensity),
        'profile': profile,
        'intensity': float(profile.fixation_intensity),
        'resume_percent': resume_percent,
        'session_id': session.session_id,
        'themes': THEMES,
        'font_sizes': FONT_SIZE_CHOICES,
    })


@login_required
@require_POST
def save_progress(request, pk):
    """Called by the reader's JavaScript: stores position and updates the session."""
    doc = get_object_or_404(Document, pk=pk, user=request.user)
    try:
        data = json.loads(request.body or b'{}')
        percent = float(data.get('percent', 0))
        start = float(data.get('start_percent', 0))
        furthest = float(data.get('furthest', percent))
    except (ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'bad data'}, status=400)

    progress = _apply_progress(doc, percent)

    session = ReadingSession.objects.filter(
        pk=data.get('session_id') or 0, user=request.user, document=doc).first()
    if session:
        now = timezone.now()
        duration = max(0, int((now - session.started_at).total_seconds()))
        covered = max(0.0, min(100.0, furthest) - max(0.0, min(100.0, start)))
        words = int(doc.word_count * covered / 100)
        wpm = 0
        if duration >= MIN_WPM_SECONDS and words > 0:
            wpm = min(MAX_WPM, int(words / (duration / 60)))
        session.ended_at = now
        session.duration_seconds = duration
        session.words_read = words
        session.reading_speed_wpm = wpm
        session.save()

    recalculate_stats(request.user)
    return JsonResponse({
        'ok': True,
        'percent': float(progress.progress_percent),
        'status': progress.status,
    })


@login_required
@require_POST
def reader_settings(request, pk):
    """Save display preferences to the user's profile, then return to the reader."""
    doc = get_object_or_404(Document, pk=pk, user=request.user)
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    theme = request.POST.get('theme')
    if theme in THEMES:
        profile.theme_preference = theme
    font = request.POST.get('font_size')
    if font in FONT_SIZES:
        profile.font_size_pref = font
    if 'fixation_intensity' in request.POST:
        profile.fixation_intensity = Decimal(
            str(round(clamp_intensity(request.POST['fixation_intensity']), 2)))
    profile.save()

    # keep the reader's place across the reload
    try:
        _apply_progress(doc, float(request.POST.get('percent', '')))
    except ValueError:
        pass

    return redirect('dashboard:reader', pk=doc.pk)
