import csv
import statistics
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO, TextIOWrapper

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, ListView, TemplateView, UpdateView

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .forms import CSVImportForm, CategoryForm, ExpenseForm, FinancialProfileForm, RecurringTransactionForm, SignUpForm, ProfileForm
from django.contrib.auth.models import User
from .models import Category, Expense, FinancialProfile, RecurringTransaction


def _increment_due_date(current_date, frequency):
    if frequency == RecurringTransaction.FREQUENCY_WEEKLY:
        return current_date + timedelta(days=7)

    next_month = current_date.month + 1
    year = current_date.year
    if next_month > 12:
        next_month = 1
        year += 1

    day = min(current_date.day, monthrange(year, next_month)[1])
    return current_date.replace(year=year, month=next_month, day=day)


def _build_analysis_context(user, get_params, analysis_options):
    expenses = Expense.objects.filter(user=user)
    selected_analysis = get_params.get("analysis", "overview")
    if selected_analysis not in analysis_options:
        selected_analysis = "overview"

    default_end_date = datetime.now().date()
    default_start_month = default_end_date.month - 11
    default_start_year = default_end_date.year
    if default_start_month <= 0:
        default_start_month += 12
        default_start_year -= 1
    default_start_date = datetime(default_start_year, default_start_month, 1).date()

    start_date = get_params.get("start_date")
    end_date = get_params.get("end_date")
    try:
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else default_start_date
    except (TypeError, ValueError):
        start_date = default_start_date
    try:
        end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else default_end_date
    except (TypeError, ValueError):
        end_date = default_end_date

    if start_date > end_date:
        start_date, end_date = end_date, start_date

    filtered_expenses = expenses.filter(date__gte=start_date, date__lte=end_date)
    amounts = list(filtered_expenses.values_list("amount", flat=True))

    monthly_totals = list(
        filtered_expenses.annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Sum("amount"))
        .order_by("month")
    )
    category_totals = list(
        filtered_expenses.values("category__name")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    summary = filtered_expenses.aggregate(
        total=Sum("amount"),
        count=Count("id"),
    )
    average = (summary["total"] / summary["count"]) if summary["total"] and summary["count"] else 0
    median = statistics.median(amounts) if amounts else 0
    standard_deviation = statistics.pstdev(amounts) if len(amounts) > 1 else 0
    trend_labels = [entry["month"].strftime("%b %Y") for entry in monthly_totals]
    trend_values = [float(entry["total"]) for entry in monthly_totals]
    projection = 0
    trend_slope = 0
    if trend_values:
        if len(trend_values) > 1:
            x_mean = (len(trend_values) - 1) / 2
            y_mean = sum(trend_values) / len(trend_values)
            denominator = sum((index - x_mean) ** 2 for index in range(len(trend_values)))
            trend_slope = sum(
                (index - x_mean) * (value - y_mean)
                for index, value in enumerate(trend_values)
            ) / denominator
            trend_intercept = y_mean - trend_slope * x_mean
            trend_line_values = [
                round(trend_intercept + trend_slope * index, 2)
                for index in range(len(trend_values) + 1)
            ]
        else:
            projection = trend_values[0]
            trend_line_values = [trend_values[0], trend_values[0]]
        projection = trend_line_values[-1]
        last_month = monthly_totals[-1]["month"]
        next_month = last_month.month + 1
        next_year = last_month.year
        if next_month > 12:
            next_month = 1
            next_year += 1
        trend_labels.append(datetime(next_year, next_month, 1).strftime("%b %Y"))
        trend_values.append(None)
    else:
        trend_line_values = []

    month_over_month = []
    for previous, current in zip(monthly_totals, monthly_totals[1:]):
        previous_total = previous["total"]
        current_total = current["total"]
        change = ((current_total - previous_total) / previous_total * 100) if previous_total else None
        month_over_month.append({
            "month": current["month"].strftime("%b %Y"),
            "total": current_total,
            "change": round(change, 2) if change is not None else None,
        })

    category_amounts = {}
    for category_name, amount in filtered_expenses.values_list("category__name", "amount"):
        category_amounts.setdefault(category_name, []).append(amount)
    category_variances = []
    for category_name, category_values in category_amounts.items():
        category_variances.append({
            "name": category_name,
            "count": len(category_values),
            "variance": round(statistics.pvariance(category_values), 2) if len(category_values) > 1 else 0,
        })
    category_variances.sort(key=lambda row: row["variance"], reverse=True)

    range_description = (
        "Your latest 12 months of recorded spending."
        if start_date == default_start_date and end_date == default_end_date
        else f"Spending from {start_date.strftime('%b %d, %Y')} through {end_date.strftime('%b %d, %Y')}."
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "analysis_month_labels": [entry["month"].strftime("%b %Y") for entry in monthly_totals],
        "analysis_month_values": [float(entry["total"]) for entry in monthly_totals],
        "chart_labels": trend_labels if selected_analysis == "trend_projection" else [entry["month"].strftime("%b %Y") for entry in monthly_totals],
        "chart_values": trend_values if selected_analysis == "trend_projection" else [float(entry["total"]) for entry in monthly_totals],
        "show_trend_line": selected_analysis == "trend_projection",
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "trend_line_values": trend_line_values,
        "trend_projection": round(projection, 2),
        "trend_slope": round(trend_slope, 2),
        "category_labels": [entry["category__name"] for entry in category_totals],
        "category_values": [float(entry["total"]) for entry in category_totals],
        "category_totals": category_totals,
        "analysis_total": summary["total"] or 0,
        "analysis_count": summary["count"] or 0,
        "analysis_average": round(average, 2),
        "analysis_median": round(median, 2),
        "analysis_standard_deviation": round(standard_deviation, 2),
        "month_over_month": month_over_month,
        "category_variances": category_variances,
        "analysis_options": analysis_options.items(),
        "selected_analysis": selected_analysis,
        "selected_analysis_label": analysis_options[selected_analysis],
        "largest_expense": filtered_expenses.select_related("category").order_by("-amount", "-date").first(),
        "range_description": range_description,
    }


class UserLoginView(LoginView):
    template_name = "registration/login.html"


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("login")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expenses = Expense.objects.filter(user=self.request.user)

        monthly_expenses = (
            expenses.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )

        month_totals = list(monthly_expenses)[-6:]
        context["chart_labels"] = [entry["month"].strftime("%b %Y") for entry in month_totals]
        context["chart_values"] = [float(entry["total"]) for entry in month_totals]

        current_month = datetime.now().month
        current_year = datetime.now().year
        context["current_month_total"] = (
            expenses.filter(date__month=current_month, date__year=current_year).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        context["lifetime_total"] = expenses.aggregate(total=Sum("amount"))["total"] or 0
        context["recent_expenses"] = expenses.select_related("category")[:5]

        financial_profile, _ = FinancialProfile.objects.get_or_create(user=self.request.user)
        context["financial_profile"] = financial_profile

        budget_used_percentage = None
        if financial_profile.monthly_budget and financial_profile.monthly_budget > 0:
            budget_used_percentage = round((context["current_month_total"] / financial_profile.monthly_budget) * 100, 1)
            if budget_used_percentage >= 100:
                context["budget_alert"] = "danger"
                context["budget_alert_message"] = "You are over your monthly budget."
            elif budget_used_percentage >= 80:
                context["budget_alert"] = "warning"
                context["budget_alert_message"] = "You are close to your monthly budget limit."
            else:
                context["budget_alert"] = "ok"
                context["budget_alert_message"] = "Spending is within your monthly budget."

        context["budget_used_percentage"] = budget_used_percentage

        current_month_expenses = expenses.filter(date__month=current_month, date__year=current_year)
        top_category = (
            current_month_expenses.values("category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
            .first()
        )
        context["top_category"] = top_category
        context["avg_daily_spend"] = round(context["current_month_total"] / datetime.now().day, 2)

        if financial_profile.monthly_salary and financial_profile.monthly_salary > 0:
            context["salary_spend_ratio"] = round((context["current_month_total"] / financial_profile.monthly_salary) * 100, 1)
        else:
            context["salary_spend_ratio"] = None

        context["due_recurring_count"] = RecurringTransaction.objects.filter(
            user=self.request.user,
            is_active=True,
            next_due_date__lte=datetime.now().date(),
        ).count()
        return context


class AnalysisView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/analysis.html"
    ANALYSIS_OPTIONS = {
        "overview": "Overview",
        "median": "Median expense",
        "standard_deviation": "Standard deviation",
        "month_over_month": "Month-over-month change",
        "category_variance": "Category-wise variance",
        "trend_projection": "Trend projection",
    }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        expenses = Expense.objects.filter(user=self.request.user)
        selected_analysis = self.request.GET.get("analysis", "overview")
        if selected_analysis not in self.ANALYSIS_OPTIONS:
            selected_analysis = "overview"

        default_end_date = datetime.now().date()
        default_start_month = default_end_date.month - 11
        default_start_year = default_end_date.year
        if default_start_month <= 0:
            default_start_month += 12
            default_start_year -= 1
        default_start_date = datetime(default_start_year, default_start_month, 1).date()

        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        try:
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else default_start_date
        except (TypeError, ValueError):
            start_date = default_start_date
        try:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else default_end_date
        except (TypeError, ValueError):
            end_date = default_end_date

        if start_date > end_date:
            start_date, end_date = end_date, start_date

        filtered_expenses = expenses.filter(date__gte=start_date, date__lte=end_date)
        amounts = list(filtered_expenses.values_list("amount", flat=True))

        monthly_totals = list(
            filtered_expenses.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )
        category_totals = list(
            filtered_expenses.values("category__name")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )
        summary = filtered_expenses.aggregate(
            total=Sum("amount"),
            count=Count("id"),
        )
        average = (summary["total"] / summary["count"]) if summary["total"] and summary["count"] else 0
        median = statistics.median(amounts) if amounts else 0
        standard_deviation = statistics.pstdev(amounts) if len(amounts) > 1 else 0
        trend_labels = [entry["month"].strftime("%b %Y") for entry in monthly_totals]
        trend_values = [float(entry["total"]) for entry in monthly_totals]
        projection = 0
        trend_slope = 0
        if trend_values:
            if len(trend_values) > 1:
                x_mean = (len(trend_values) - 1) / 2
                y_mean = sum(trend_values) / len(trend_values)
                denominator = sum((index - x_mean) ** 2 for index in range(len(trend_values)))
                trend_slope = sum(
                    (index - x_mean) * (value - y_mean)
                    for index, value in enumerate(trend_values)
                ) / denominator
                trend_intercept = y_mean - trend_slope * x_mean
                trend_line_values = [
                    round(trend_intercept + trend_slope * index, 2)
                    for index in range(len(trend_values) + 1)
                ]
            else:
                projection = trend_values[0]
                trend_line_values = [trend_values[0], trend_values[0]]
            projection = trend_line_values[-1]
            last_month = monthly_totals[-1]["month"]
            next_month = last_month.month + 1
            next_year = last_month.year
            if next_month > 12:
                next_month = 1
                next_year += 1
            trend_labels.append(datetime(next_year, next_month, 1).strftime("%b %Y"))
            trend_values.append(None)
        else:
            trend_line_values = []
        month_over_month = []
        for previous, current in zip(monthly_totals, monthly_totals[1:]):
            previous_total = previous["total"]
            current_total = current["total"]
            change = ((current_total - previous_total) / previous_total * 100) if previous_total else None
            month_over_month.append({
                "month": current["month"].strftime("%b %Y"),
                "total": current_total,
                "change": round(change, 2) if change is not None else None,
            })

        category_amounts = {}
        for category_name, amount in filtered_expenses.values_list("category__name", "amount"):
            category_amounts.setdefault(category_name, []).append(amount)
        category_variances = []
        for category_name, category_values in category_amounts.items():
            category_variances.append({
                "name": category_name,
                "count": len(category_values),
                "variance": round(statistics.pvariance(category_values), 2) if len(category_values) > 1 else 0,
            })
        category_variances.sort(key=lambda row: row["variance"], reverse=True)

        range_description = (
            "Your latest 12 months of recorded spending."
            if start_date == default_start_date and end_date == default_end_date
            else f"Spending from {start_date.strftime('%b %d, %Y')} through {end_date.strftime('%b %d, %Y')}.")

        context["start_date"] = start_date.isoformat()
        context["end_date"] = end_date.isoformat()
        context["analysis_month_labels"] = [entry["month"].strftime("%b %Y") for entry in monthly_totals]
        context["analysis_month_values"] = [float(entry["total"]) for entry in monthly_totals]
        context["chart_labels"] = trend_labels if selected_analysis == "trend_projection" else context["analysis_month_labels"]
        context["chart_values"] = trend_values if selected_analysis == "trend_projection" else context["analysis_month_values"]
        context["show_trend_line"] = selected_analysis == "trend_projection"
        context["trend_labels"] = trend_labels
        context["trend_values"] = trend_values
        context["trend_line_values"] = trend_line_values
        context["trend_projection"] = round(projection, 2)
        context["trend_slope"] = round(trend_slope, 2)
        context["category_labels"] = [entry["category__name"] for entry in category_totals]
        context["category_values"] = [float(entry["total"]) for entry in category_totals]
        context["category_totals"] = category_totals
        context["analysis_total"] = summary["total"] or 0
        context["analysis_count"] = summary["count"] or 0
        context["analysis_average"] = round(average, 2)
        context["analysis_median"] = round(median, 2)
        context["analysis_standard_deviation"] = round(standard_deviation, 2)
        context["month_over_month"] = month_over_month
        context["category_variances"] = category_variances
        context["analysis_options"] = self.ANALYSIS_OPTIONS.items()
        context["selected_analysis"] = selected_analysis
        context["selected_analysis_label"] = self.ANALYSIS_OPTIONS[selected_analysis]
        context["largest_expense"] = filtered_expenses.select_related("category").order_by("-amount", "-date").first()
        context["range_description"] = range_description
        return context


class ExpenseListView(LoginRequiredMixin, ListView):
    model = Expense
    template_name = "expenses/expense_list.html"
    context_object_name = "expenses"
    paginate_by = 10

    SORT_OPTIONS = {
        "date_desc": ("-date", "-created_at"),
        "date_asc": ("date", "created_at"),
        "amount_desc": ("-amount", "-date", "-created_at"),
        "amount_asc": ("amount", "date", "created_at"),
        "title_asc": ("title", "-date", "-created_at"),
        "title_desc": ("-title", "-date", "-created_at"),
    }

    def get_queryset(self):
        self.sort = self.request.GET.get("sort", "date_desc")
        ordering = self.SORT_OPTIONS.get(self.sort, self.SORT_OPTIONS["date_desc"])
        return (
            Expense.objects.filter(user=self.request.user)
            .select_related("category")
            .order_by(*ordering)
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query_params = self.request.GET.copy()
        query_params.pop("page", None)
        context["pagination_query"] = query_params.urlencode()
        context["current_sort"] = getattr(self, "sort", "date_desc")
        return context


class ExpenseCreateView(LoginRequiredMixin, CreateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/expense_form.html"
    success_url = reverse_lazy("expense-list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class ExpenseUpdateView(LoginRequiredMixin, UpdateView):
    model = Expense
    form_class = ExpenseForm
    template_name = "expenses/expense_form.html"
    success_url = reverse_lazy("expense-list")

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class ExpenseDeleteView(LoginRequiredMixin, DeleteView):
    model = Expense
    template_name = "expenses/expense_confirm_delete.html"
    success_url = reverse_lazy("expense-list")

    def get_queryset(self):
        return Expense.objects.filter(user=self.request.user)


class ReportView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/report_monthly.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        month_param = self.request.GET.get("month")

        if month_param:
            try:
                selected_month = datetime.strptime(month_param, "%Y-%m")
            except ValueError:
                now = datetime.now()
                selected_month = datetime(now.year, now.month, 1)
        else:
            now = datetime.now()
            selected_month = datetime(now.year, now.month, 1)

        expenses = Expense.objects.filter(
            user=self.request.user,
            date__year=selected_month.year,
            date__month=selected_month.month,
        ).select_related("category")

        category_breakdown = (
            expenses.values("category__name")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        context["selected_month"] = selected_month.strftime("%Y-%m")
        context["expenses"] = expenses
        context["month_total"] = expenses.aggregate(total=Sum("amount"))["total"] or 0
        context["category_breakdown"] = category_breakdown
        return context


class RecurringSetupView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/recurring_transactions.html"
    default_categories = ["Food", "Transport", "Bills", "Entertainment", "Healthcare", "Other"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_form"] = kwargs.get("category_form") or CategoryForm()
        context["categories"] = self.request.user.category_set.all()
        context["recurring_form"] = kwargs.get("recurring_form") or RecurringTransactionForm(user=self.request.user)
        context["recurring_items"] = RecurringTransaction.objects.filter(user=self.request.user).select_related("category")
        # include financial profile form/context so Personalize page can manage financials
        profile, _ = FinancialProfile.objects.get_or_create(user=self.request.user)
        context["profile_form"] = kwargs.get("profile_form") or FinancialProfileForm(instance=profile)
        context["financial_profile"] = profile
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

        if action == "seed":
            created_count = 0
            for name in self.default_categories:
                _, created = request.user.category_set.get_or_create(name=name)
                if created:
                    created_count += 1

            if created_count:
                messages.success(request, f"Added {created_count} default categories.")
            else:
                messages.info(request, "Default categories are already set up.")

            return redirect("recurring-transactions")

        if action == "process-due":
            today = datetime.now().date()
            created_expenses = 0
            recurring_items = RecurringTransaction.objects.filter(
                user=request.user,
                is_active=True,
                next_due_date__lte=today,
            ).select_related("category")

            for item in recurring_items:
                run_guard = 0
                while item.next_due_date <= today and run_guard < 24:
                    Expense.objects.create(
                        user=request.user,
                        category=item.category,
                        title=item.title,
                        amount=item.amount,
                        date=item.next_due_date,
                        notes=item.notes,
                    )
                    created_expenses += 1
                    item.next_due_date = _increment_due_date(item.next_due_date, item.frequency)
                    run_guard += 1

                item.save(update_fields=["next_due_date"])

            if created_expenses:
                messages.success(request, f"Processed {created_expenses} recurring transactions.")
            else:
                messages.info(request, "No recurring transactions were due.")
            return redirect("recurring-transactions")

        if action == "add-category":
            category_form = CategoryForm(request.POST)
            if category_form.is_valid():
                request.user.category_set.get_or_create(name=category_form.cleaned_data["name"])
                messages.success(request, "Category saved.")
                return redirect("recurring-transactions")
            return self.render_to_response(self.get_context_data(category_form=category_form))

        if action == "add-recurring":
            recurring_form = RecurringTransactionForm(request.POST, user=request.user)
            if recurring_form.is_valid():
                recurring_transaction = recurring_form.save(commit=False)
                recurring_transaction.user = request.user
                recurring_transaction.save()
                messages.success(request, "Recurring transaction added.")
                return redirect("recurring-transactions")
            return self.render_to_response(self.get_context_data(recurring_form=recurring_form))

        if action == "update-financial":
            profile, _ = FinancialProfile.objects.get_or_create(user=request.user)
            profile_form = FinancialProfileForm(request.POST, instance=profile)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Financial profile updated.")
                return redirect("recurring-transactions")
            return self.render_to_response(self.get_context_data(profile_form=profile_form))

        return self.render_to_response(self.get_context_data())


class UserProfileView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileForm
    template_name = "expenses/profile.html"
    success_url = reverse_lazy("dashboard")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Profile updated.")
        return super().form_valid(form)


class CSVImportView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/import_csv.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["import_form"] = kwargs.get("import_form") or CSVImportForm()
        return context

    def post(self, request, *args, **kwargs):
        import_form = CSVImportForm(request.POST, request.FILES)
        if not import_form.is_valid():
            return self.render_to_response(self.get_context_data(import_form=import_form))

        csv_file = import_form.cleaned_data["csv_file"]
        try:
            reader = csv.DictReader(TextIOWrapper(csv_file.file, encoding="utf-8"))
        except UnicodeDecodeError:
            messages.error(request, "File encoding not supported. Please upload UTF-8 CSV.")
            return redirect("import-csv")

        required_columns = {"date", "title", "category", "amount"}
        if not reader.fieldnames or not required_columns.issubset({name.strip().lower() for name in reader.fieldnames}):
            messages.error(request, "CSV must include headers: date,title,category,amount")
            return redirect("import-csv")

        created_count = 0
        failed_count = 0
        for row in reader:
            try:
                normalized_row = {key.strip().lower(): (value or "").strip() for key, value in row.items() if key}
                date_value = datetime.strptime(normalized_row.get("date", ""), "%Y-%m-%d").date()
                title_value = normalized_row.get("title", "")
                category_name = normalized_row.get("category", "")
                amount_value = Decimal(normalized_row.get("amount", "0"))
                notes_value = normalized_row.get("notes", "")

                if not title_value or not category_name or amount_value <= 0:
                    failed_count += 1
                    continue

                category, _ = Category.objects.get_or_create(user=request.user, name=category_name)
                Expense.objects.create(
                    user=request.user,
                    category=category,
                    title=title_value,
                    amount=amount_value,
                    date=date_value,
                    notes=notes_value,
                )
                created_count += 1
            except (ValueError, InvalidOperation, AttributeError):
                failed_count += 1

        if created_count:
            messages.success(request, f"Imported {created_count} expense rows.")
        if failed_count:
            messages.warning(request, f"Skipped {failed_count} invalid rows.")

        return redirect("import-csv")


@login_required
def seed_default_categories(request):
    # Backwards-compatible endpoint; keep behavior for old links while moving users to setup page.
    if request.method == "POST":
        default_categories = ["Food", "Transport", "Bills", "Entertainment", "Healthcare", "Other"]
        for name in default_categories:
            request.user.category_set.get_or_create(name=name)
    return redirect("seed-categories")


@login_required
def export_spending_csv(request):
    expenses = Expense.objects.filter(user=request.user).select_related("category").order_by("-date")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = "attachment; filename=spending_export.csv"
    writer = csv.writer(response)
    writer.writerow(["Date", "Title", "Category", "Amount", "Notes"])
    for expense in expenses:
        writer.writerow([
            expense.date.strftime("%Y-%m-%d"),
            expense.title,
            expense.category.name,
            f"{expense.amount:.2f}",
            expense.notes,
        ])
    return response


@login_required
def export_analysis_pdf(request):
    context = _build_analysis_context(request.user, request.GET, AnalysisView.ANALYSIS_OPTIONS)
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=inch / 2, leftMargin=inch / 2, topMargin=inch / 2, bottomMargin=inch / 2)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("Spend Shelf Analysis Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Report generated on: {datetime.now().strftime('%b %d, %Y')}", styles["Normal"]),
        Paragraph(context["range_description"], styles["Normal"]),
        Paragraph(f"Selected measure: {context['selected_analysis_label']}", styles["Normal"]),
        Spacer(1, 16),
    ]

    summary_data = [
        ["Metric", "Value"],
        ["Total spend", f"₹{context['analysis_total']:.2f}"],
        ["Average expense", f"₹{context['analysis_average']:.2f}"],
        ["Expense entries", str(context['analysis_count'])],
        ["Median expense", f"₹{context['analysis_median']:.2f}"],
        ["Standard deviation", f"₹{context['analysis_standard_deviation']:.2f}"],
        ["Trend projection", f"₹{context['trend_projection']:.2f}"],
        ["Trend slope", f"₹{context['trend_slope']:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([Paragraph("Summary", styles["Heading2"]), Spacer(1, 8), summary_table, Spacer(1, 16)])

    story.append(Paragraph("Month-over-Month Change", styles["Heading2"]))
    if context["month_over_month"]:
        month_rows = [["Month", "Total", "Change"]] + [
            [row["month"], f"₹{row['total']:.2f}", f"{row['change']:.2f}%" if row["change"] is not None else "New baseline"]
            for row in context["month_over_month"]
        ]
        month_table = Table(month_rows, colWidths=[2.5 * inch, 2 * inch, 2 * inch])
        month_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.extend([Spacer(1, 8), month_table, Spacer(1, 16)])
    else:
        story.extend([Spacer(1, 8), Paragraph("At least two months of data are needed.", styles["Normal"]), Spacer(1, 16)])

    story.append(Paragraph("Category Variance", styles["Heading2"]))
    if context["category_variances"]:
        variance_rows = [["Category", "Entries", "Variance"]] + [
            [row["name"], str(row["count"]), f"₹{row['variance']:.2f}"]
            for row in context["category_variances"]
        ]
        variance_table = Table(variance_rows, colWidths=[3 * inch, 1.5 * inch, 2 * inch])
        variance_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.extend([Spacer(1, 8), variance_table, Spacer(1, 16)])
    else:
        story.extend([Spacer(1, 8), Paragraph("No category variance data available.", styles["Normal"]), Spacer(1, 16)])

    story.append(Paragraph("Category Totals", styles["Heading2"]))
    if context["category_totals"]:
        totals_rows = [["Category", "Entries", "Total"]] + [
            [entry["category__name"], str(entry["count"]), f"₹{float(entry['total']):.2f}"]
            for entry in context["category_totals"]
        ]
        totals_table = Table(totals_rows, colWidths=[3 * inch, 1.5 * inch, 2 * inch])
        totals_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.gray),
                ]
            )
        )
        story.extend([Spacer(1, 8), totals_table])
    else:
        story.extend([Spacer(1, 8), Paragraph("No category totals available.", styles["Normal"])])

    def render_chart_image(labels, values, trend_labels=None, trend_values=None, title="Monthly Spending"):
        if not labels or not values:
            return None

        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
        ax.bar(labels, values, color="#f97316", label="Monthly spend")
        ax.set_title(title)
        ax.set_ylabel("Amount")
        ax.set_xlabel("Month")
        ax.tick_params(axis="x", rotation=45)

        if trend_labels and trend_values:
            cleaned_labels = [label for label, value in zip(trend_labels, trend_values) if value is not None]
            cleaned_values = [value for value in trend_values if value is not None]
            if cleaned_labels and cleaned_values:
                ax.plot(cleaned_labels, cleaned_values, marker="o", color="#1f2937", label="Trend line")
                ax.legend()

        fig.tight_layout()
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format="png", transparent=False)
        plt.close(fig)
        image_buffer.seek(0)
        return image_buffer

    def render_category_chart(labels, values, title="Spending by Category"):
        if not labels or not values:
            return None

        fig, ax = plt.subplots(figsize=(6, 3.5), dpi=100)
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=140, wedgeprops={"linewidth": 0.8, "edgecolor": "white"})
        ax.set_title(title)
        centre_circle = plt.Circle((0, 0), 0.60, fc="white")
        fig.gca().add_artist(centre_circle)
        fig.tight_layout()
        image_buffer = BytesIO()
        fig.savefig(image_buffer, format="png", transparent=False)
        plt.close(fig)
        image_buffer.seek(0)
        return image_buffer

    chart_image = render_chart_image(
        context["chart_labels"],
        context["chart_values"],
        trend_labels=context.get("trend_labels"),
        trend_values=context.get("trend_line_values"),
        title="Monthly Spending with Trend Line",
    )
    category_image = render_category_chart(context["category_labels"], context["category_values"])

    if chart_image:
        story.extend([Spacer(1, 16), Image(chart_image, width=6.5 * inch, height=3.5 * inch)])
    if category_image:
        story.extend([Spacer(1, 16), Image(category_image, width=6.5 * inch, height=3.5 * inch)])

    doc.build(story)
    buffer.seek(0)

    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = "attachment; filename=spend_shelf_analysis.pdf"
    return response
