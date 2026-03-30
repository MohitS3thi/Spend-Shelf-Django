from django.urls import path

from .views import (
    CSVImportView,
    CategorySetupView,
    DashboardView,
    ExpenseCreateView,
    ExpenseDeleteView,
    ExpenseListView,
    ExpenseUpdateView,
    FinancialProfileView,
    ReportView,
    RecurringTransactionView,
    SignUpView,
    UserLoginView,
    export_spending_csv,
)

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("login/", UserLoginView.as_view(), name="login"),
    path("signup/", SignUpView.as_view(), name="signup"),
    path("expenses/", ExpenseListView.as_view(), name="expense-list"),
    path("expenses/add/", ExpenseCreateView.as_view(), name="expense-add"),
    path("expenses/<int:pk>/edit/", ExpenseUpdateView.as_view(), name="expense-edit"),
    path("expenses/<int:pk>/delete/", ExpenseDeleteView.as_view(), name="expense-delete"),
    path("reports/monthly/", ReportView.as_view(), name="report-monthly"),
    path("setup/categories/", CategorySetupView.as_view(), name="seed-categories"),
    path("profile/financial/", FinancialProfileView.as_view(), name="financial-profile"),
    path("recurring/", RecurringTransactionView.as_view(), name="recurring-transactions"),
    path("imports/csv/", CSVImportView.as_view(), name="import-csv"),
    path("exports/spending.csv", export_spending_csv, name="export-spending-csv"),
]
