from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _


@login_required
def sozlamalar(request):
    """Sozlamalar: interfeys tili (Django set_language orqali, cookie) va
    parolni almashtirish — barcha foydalanuvchilar uchun."""
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # parol almashganda sessiya uzilmasin
            messages.success(request, _("Parol almashtirildi."))
            return redirect("sozlamalar")
    else:
        form = PasswordChangeForm(request.user)
    for field in form.fields.values():
        field.help_text = ""  # parol talablari ro'yxati — sahifada alohida yozilgan
    return render(request, "core/sozlamalar.html", {"password_form": form})
