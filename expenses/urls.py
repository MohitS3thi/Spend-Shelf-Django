from django.urls import path

from .views import (
    CSVImportView,
    AnalysisView,
    DashboardView,
    ExpenseCreateView,
    ExpenseDeleteView,
    ExpenseListView,
    ExpenseUpdateView,
    RecurringSetupView,
    UserProfileView,
    ReportView,
    SignUpView,
    UserLoginView,
    export_spending_csv,
    export_analysis_pdf,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("expenses/", ExpenseListView.as_view(), name="expense-list"),
    path("analysis/", AnalysisView.as_view(), name="analysis"),
    path("expenses/add/", ExpenseCreateView.as_view(), name="expense-add"),
    path("expenses/<int:pk>/edit/", ExpenseUpdateView.as_view(), name="expense-edit"),
    path("expenses/<int:pk>/delete/", ExpenseDeleteView.as_view(), name="expense-delete"),
    path("reports/monthly/", ReportView.as_view(), name="report-monthly"),
    path("setup/categories/", RecurringSetupView.as_view(), name="seed-categories"),
    path("recurring/", RecurringSetupView.as_view(), name="recurring-transactions"),
    path("profile/", UserProfileView.as_view(), name="profile"),
    path("imports/csv/", CSVImportView.as_view(), name="import-csv"),
    path("exports/spending.csv", export_spending_csv, name="export-spending-csv"),
    path("analysis/export/pdf/", export_analysis_pdf, name="export-analysis-pdf"),
]
