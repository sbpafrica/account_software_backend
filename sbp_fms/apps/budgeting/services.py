from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from apps.ledger.models import Account
from .models import Budget, BudgetLine, BudgetStatus


class BudgetingService:
    @staticmethod
    @transaction.atomic
    def budget_create(*, name: str, financial_year: int, department: str = '',
                      cost_centre: str = '', notes: str = '',
                      lines_data: list = None, user=None) -> Budget:
        budget = Budget.objects.create(
            name=name.strip(),
            financial_year=financial_year,
            department=department.strip(),
            cost_centre=cost_centre.strip(),
            notes=notes.strip(),
            status=BudgetStatus.DRAFT,
            created_by=user
        )

        total_planned = Decimal('0.0000')
        if lines_data:
            lines = []
            for item in lines_data:
                acct = Account.objects.get(id=item['account_id'])
                amt = Decimal(str(item['planned_amount']))
                if amt <= 0:
                    raise ValidationError("Planned amount must be greater than zero.")
                lines.append(
                    BudgetLine(
                        budget=budget,
                        account=acct,
                        period_month=item.get('period_month'),
                        planned_amount=amt,
                        notes=item.get('notes', '')
                    )
                )
                total_planned += amt
            BudgetLine.objects.bulk_create(lines)

        budget.total_budget = total_planned
        budget.save(update_fields=['total_budget'])
        CacheManager.invalidate_budgeting()
        return budget

    @staticmethod
    @transaction.atomic
    def budget_submit(*, budget_id: str) -> Budget:
        budget = Budget.objects.select_for_update().get(id=budget_id)
        if budget.status != BudgetStatus.DRAFT:
            raise ValidationError(f"Cannot submit budget with status '{budget.status}'.")
        budget.status = BudgetStatus.SUBMITTED
        budget.save(update_fields=['status'])
        CacheManager.invalidate_budgeting()
        return budget

    @staticmethod
    @transaction.atomic
    def budget_approve(*, budget_id: str, user) -> Budget:
        budget = Budget.objects.select_for_update().get(id=budget_id)
        if budget.status not in [BudgetStatus.DRAFT, BudgetStatus.SUBMITTED]:
            raise ValidationError(f"Cannot approve budget with status '{budget.status}'.")
        if budget.created_by and budget.created_by == user and not getattr(user, 'is_superuser', False):
            raise ValidationError("Segregation of duties violation: Creator cannot approve their own budget.")
        budget.status = BudgetStatus.APPROVED
        budget.approved_by = user
        budget.save(update_fields=['status', 'approved_by'])
        CacheManager.invalidate_budgeting()
        return budget

    @staticmethod
    @transaction.atomic
    def budget_close(*, budget_id: str) -> Budget:
        budget = Budget.objects.select_for_update().get(id=budget_id)
        budget.status = BudgetStatus.CLOSED
        budget.save(update_fields=['status'])
        CacheManager.invalidate_budgeting()
        return budget
