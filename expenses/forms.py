from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Category, Expense, FinancialProfile, RecurringTransaction


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["title", "category", "amount", "date", "notes"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = user.category_set.all()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean_date(self):
        expense_date = self.cleaned_data["date"]
        if expense_date > timezone.localdate():
            raise forms.ValidationError("Expense date cannot be in the future.")
        return expense_date


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]

    def clean_name(self):
        return self.cleaned_data["name"].strip()


class FinancialProfileForm(forms.ModelForm):
    class Meta:
        model = FinancialProfile
        fields = ["current_savings", "monthly_salary", "monthly_budget"]


class RecurringTransactionForm(forms.ModelForm):
    class Meta:
        model = RecurringTransaction
        fields = ["title", "category", "amount", "frequency", "next_due_date", "notes", "is_active"]
        widgets = {
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop("user")
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = user.category_set.all()

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(help_text="CSV with columns: date,title,category,amount,notes")
