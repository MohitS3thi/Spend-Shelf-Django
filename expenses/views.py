import csv
import statistics
from calendar import monthrange
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import TextIOWrapper

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

from .forms import CSVImportForm, CategoryForm, ExpenseForm, FinancialProfileForm, RecurringTransactionForm, SignUpForm
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
        amounts = list(expenses.values_list("amount", flat=True))

        monthly_totals = list(
            expenses.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(total=Sum("amount"))
            .order_by("month")
        )[-12:]
        category_totals = list(
            expenses.values("category__name")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("-total")
        )
        summary = expenses.aggregate(
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
        for category_name, amount in expenses.values_list("category__name", "amount"):
            category_amounts.setdefault(category_name, []).append(amount)
        category_variances = []
        for category_name, category_values in category_amounts.items():
            category_variances.append({
                "name": category_name,
                "count": len(category_values),
                "variance": round(statistics.pvariance(category_values), 2) if len(category_values) > 1 else 0,
            })
        category_variances.sort(key=lambda row: row["variance"], reverse=True)

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
        context["largest_expense"] = expenses.select_related("category").order_by("-amount", "-date").first()
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


class CategorySetupView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/category_setup.html"
    default_categories = ["Food", "Transport", "Bills", "Entertainment", "Healthcare", "Other"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category_form"] = kwargs.get("category_form") or CategoryForm()
        context["categories"] = self.request.user.category_set.all()
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

            return redirect("seed-categories")

        category_form = CategoryForm(request.POST)
        if category_form.is_valid():
            request.user.category_set.get_or_create(name=category_form.cleaned_data["name"])
            messages.success(request, "Category saved.")
            return redirect("seed-categories")

        return self.render_to_response(self.get_context_data(category_form=category_form))


class FinancialProfileView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/financial_profile.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = FinancialProfile.objects.get_or_create(user=self.request.user)
        context["profile_form"] = kwargs.get("profile_form") or FinancialProfileForm(instance=profile)
        return context

    def post(self, request, *args, **kwargs):
        profile, _ = FinancialProfile.objects.get_or_create(user=request.user)
        profile_form = FinancialProfileForm(request.POST, instance=profile)
        if profile_form.is_valid():
            profile_form.save()
            messages.success(request, "Financial profile updated.")
            return redirect("financial-profile")

        return self.render_to_response(self.get_context_data(profile_form=profile_form))


class RecurringTransactionView(LoginRequiredMixin, TemplateView):
    template_name = "expenses/recurring_transactions.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["recurring_form"] = kwargs.get("recurring_form") or RecurringTransactionForm(user=self.request.user)
        context["recurring_items"] = RecurringTransaction.objects.filter(user=self.request.user).select_related("category")
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action")

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

        recurring_form = RecurringTransactionForm(request.POST, user=request.user)
        if recurring_form.is_valid():
            recurring_transaction = recurring_form.save(commit=False)
            recurring_transaction.user = request.user
            recurring_transaction.save()
            messages.success(request, "Recurring transaction added.")
            return redirect("recurring-transactions")

        return self.render_to_response(self.get_context_data(recurring_form=recurring_form))


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
