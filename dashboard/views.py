import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import get_valid_filename
from django.views.decorators.http import require_POST

from accounts.models import UserStats

from .forms import UploadForm
from .models import Document, ReadingProgress


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
