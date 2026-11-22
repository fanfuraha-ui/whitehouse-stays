import re
from datetime import timedelta

from django import forms
from django.utils import timezone

PHONE_RE = re.compile(r"^(?:\+?254|0)?([17]\d{8})$")


def normalize_ke_phone(raw: str) -> str:
    digits = re.sub(r"[\s\-()]", "", raw or "")
    match = PHONE_RE.match(digits)
    if not match:
        raise forms.ValidationError("Enter a Kenyan number, e.g. 0712 345 678.")
    return "254" + match.group(1)


class DateInput(forms.DateInput):
    input_type = "date"


class SearchForm(forms.Form):
    check_in = forms.DateField(widget=DateInput)
    check_out = forms.DateField(widget=DateInput)
    guests = forms.IntegerField(min_value=1, max_value=12, initial=2)

    def clean(self):
        data = super().clean()
        check_in, check_out = data.get("check_in"), data.get("check_out")
        if check_in and check_out:
            today = timezone.localdate()
            if check_in < today:
                raise forms.ValidationError("Check-in can't be in the past.")
            if check_out <= check_in:
                raise forms.ValidationError("Check-out must be after check-in.")
            if check_in > today + timedelta(days=365):
                raise forms.ValidationError("We take bookings up to 12 months ahead.")
        return data


class GuestDetailsForm(forms.Form):
    full_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=20, help_text="M-Pesa number if paying by M-Pesa")
    email = forms.EmailField(help_text="Your confirmation and invoice are sent here")
    address = forms.CharField(max_length=160, required=False)
    accept_terms = forms.BooleanField(label="I accept the house rules and cancellation policy")

    def clean_phone(self):
        return normalize_ke_phone(self.cleaned_data["phone"])
