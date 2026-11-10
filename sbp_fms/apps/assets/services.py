from decimal import Decimal
from datetime import datetime, date
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.common.cache import CacheManager
from apps.ledger.models import Account
from apps.ledger.services import LedgerService
from apps.treasury.models import BankAccount
from .models import (
    AssetCategory, FixedAsset, AssetStatus,
    DepreciationMethod, DepreciationRun, DepreciationRunStatus,
    DepreciationScheduleLine
)


class AssetsService:
    @staticmethod
    @transaction.atomic
    def asset_category_create(*, code: str, name: str, asset_gl_account_id,
                              accumulated_depr_gl_account_id, depr_expense_gl_account_id,
                              default_useful_life_years: int = 5,
                              default_depreciation_method: str = DepreciationMethod.STRAIGHT_LINE,
                              country_code: str = 'GH') -> AssetCategory:
        if AssetCategory.objects.filter(code=code).exists():
            raise ValidationError(f"Asset Category with code '{code}' already exists.")

        cat = AssetCategory.objects.create(
            code=code.strip().upper(),
            name=name.strip(),
            default_useful_life_years=default_useful_life_years,
            default_depreciation_method=default_depreciation_method,
            asset_gl_account_id=asset_gl_account_id,
            accumulated_depr_gl_account_id=accumulated_depr_gl_account_id,
            depr_expense_gl_account_id=depr_expense_gl_account_id,
            country_code=country_code.strip().upper()
        )
        CacheManager.invalidate_assets()
        return cat

    @staticmethod
    @transaction.atomic
    def asset_category_update(*, category_id, **fields) -> AssetCategory:
        cat = AssetCategory.objects.select_for_update().get(id=category_id)
        for k, v in fields.items():
            if hasattr(cat, k) and v is not None:
                setattr(cat, k, v)
        cat.save()
        CacheManager.invalidate_assets()
        return cat

    @staticmethod
    @transaction.atomic
    def fixed_asset_create(*, asset_tag: str, name: str, category_id,
                           purchase_date: date, purchase_cost: Decimal,
                           salvage_value: Decimal = Decimal('0.0000'),
                           useful_life_years: int = None,
                           depreciation_method: str = None,
                           depreciation_rate_pct: Decimal = Decimal('0.0000'),
                           department: str = '', cost_centre: str = '',
                           location: str = '', description: str = '',
                           country_code: str = 'GH') -> FixedAsset:
        if FixedAsset.objects.filter(asset_tag=asset_tag).exists():
            raise ValidationError(f"Fixed asset tag '{asset_tag}' already exists.")

        category = AssetCategory.objects.get(id=category_id)
        method = depreciation_method or category.default_depreciation_method
        life_years = useful_life_years or category.default_useful_life_years

        purchase_cost = Decimal(str(purchase_cost))
        salvage_value = Decimal(str(salvage_value))
        depreciation_rate_pct = Decimal(str(depreciation_rate_pct))

        asset = FixedAsset.objects.create(
            asset_tag=asset_tag.strip().upper(),
            name=name.strip(),
            description=description.strip(),
            category=category,
            purchase_date=purchase_date,
            purchase_cost=purchase_cost,
            salvage_value=salvage_value,
            useful_life_years=life_years,
            depreciation_method=method,
            depreciation_rate_pct=depreciation_rate_pct,
            accumulated_depreciation=Decimal('0.0000'),
            net_book_value=purchase_cost,
            status=AssetStatus.ACTIVE,
            department=department.strip(),
            cost_centre=cost_centre.strip(),
            location=location.strip(),
            country_code=country_code.strip().upper()
        )
        CacheManager.invalidate_assets()
        return asset

    @staticmethod
    @transaction.atomic
    def depreciation_run_calculate(*, period_end_date: date, user=None) -> DepreciationRun:
        """
        Calculates monthly depreciation across all active fixed assets.
        Supports STRAIGHT_LINE and REDUCING_BALANCE methods.
        """
        run_number = f"DEP-{period_end_date.strftime('%Y%m')}-{datetime.now().strftime('%H%M%S')}"

        active_assets = FixedAsset.objects.select_for_update().filter(
            status=AssetStatus.ACTIVE,
            purchase_date__lte=period_end_date,
            net_book_value__gt=models.F('salvage_value')
        ).select_related('category')

        run = DepreciationRun.objects.create(
            run_number=run_number,
            period_end_date=period_end_date,
            status=DepreciationRunStatus.DRAFT,
            run_by=user
        )

        total_depr = Decimal('0.0000')
        lines = []

        for asset in active_assets:
            if asset.net_book_value <= asset.salvage_value:
                continue

            # Monthly depreciation calculation
            if asset.depreciation_method == DepreciationMethod.STRAIGHT_LINE:
                depreciable_base = asset.purchase_cost - asset.salvage_value
                total_months = asset.useful_life_years * 12
                monthly_amount = (depreciable_base / Decimal(str(total_months))).quantize(Decimal('0.0001'))
            else:  # REDUCING_BALANCE
                rate = asset.depreciation_rate_pct / Decimal('100.0') if asset.depreciation_rate_pct > 0 else (Decimal('1.0') / Decimal(str(asset.useful_life_years)) * Decimal('2.0'))
                monthly_amount = (asset.net_book_value * rate / Decimal('12.0')).quantize(Decimal('0.0001'))

            max_allowed = asset.net_book_value - asset.salvage_value
            if monthly_amount > max_allowed:
                monthly_amount = max_allowed

            if monthly_amount <= 0:
                continue

            accum_before = asset.accumulated_depreciation
            accum_after = accum_before + monthly_amount
            nbv_after = asset.net_book_value - monthly_amount

            lines.append(
                DepreciationScheduleLine(
                    asset=asset,
                    depreciation_run=run,
                    period_date=period_end_date,
                    depreciation_amount=monthly_amount,
                    accumulated_before=accum_before,
                    accumulated_after=accum_after,
                    book_value_after=nbv_after
                )
            )
            total_depr += monthly_amount

        DepreciationScheduleLine.objects.bulk_create(lines)
        run.total_depreciation = total_depr
        run.total_assets_processed = len(lines)
        run.save(update_fields=['total_depreciation', 'total_assets_processed'])

        CacheManager.invalidate_assets()
        return run

    @staticmethod
    @transaction.atomic
    def depreciation_run_post(*, depreciation_run_id: str, user) -> DepreciationRun:
        """
        Posts double-entry GL journal for the calculated depreciation run:
        DR Depreciation Expense (by AssetCategory)
        CR Accumulated Depreciation (by AssetCategory)
        and updates the asset net book values and accumulated depreciation.
        """
        run = DepreciationRun.objects.select_for_update().get(id=depreciation_run_id)
        if run.status == DepreciationRunStatus.POSTED:
            raise ValidationError("This depreciation run is already posted.")

        lines = run.schedule_lines.select_related('asset__category', 'asset').all()
        if not lines:
            raise ValidationError("No depreciation lines found to post.")

        # Aggregate by Category
        category_totals = {}
        for line in lines:
            cat = line.asset.category
            category_totals[cat] = category_totals.get(cat, Decimal('0.0000')) + line.depreciation_amount

        # Build GL lines
        gl_lines = []
        for cat, amount in category_totals.items():
            if amount > 0:
                gl_lines.append({
                    'account': cat.depr_expense_gl_account,
                    'debit': amount,
                    'credit': Decimal('0.0000')
                })
                gl_lines.append({
                    'account': cat.accumulated_depr_gl_account,
                    'debit': Decimal('0.0000'),
                    'credit': amount
                })

        entry_number = f"DEP-JV-{run.period_end_date.strftime('%Y%m')}-{run.id.hex[:6].upper()}"
        journal_entry = LedgerService.post_journal_entry(
            entry_number=entry_number,
            posting_date=run.period_end_date,
            description=f"Monthly Depreciation Run for period ending {run.period_end_date}",
            source_module='fixed_assets',
            source_ref=str(run.id),
            user=user,
            lines_data=gl_lines
        )

        # Update FixedAsset records
        for line in lines:
            asset = line.asset
            asset.accumulated_depreciation = line.accumulated_after
            asset.net_book_value = line.book_value_after
            if asset.net_book_value <= asset.salvage_value:
                asset.status = AssetStatus.FULLY_DEPRECIATED
            asset.save(update_fields=['accumulated_depreciation', 'net_book_value', 'status'])

        run.status = DepreciationRunStatus.POSTED
        run.journal_entry = journal_entry
        run.save(update_fields=['status', 'journal_entry'])

        CacheManager.invalidate_assets()
        return run

    @staticmethod
    @transaction.atomic
    def fixed_asset_dispose(*, asset_id: str, disposal_date: date,
                            sale_proceeds: Decimal, bank_account_id: str = None,
                            gain_loss_account_id: str = None, user=None) -> FixedAsset:
        asset = FixedAsset.objects.select_for_update().get(id=asset_id)
        if asset.status == AssetStatus.DISPOSED:
            raise ValidationError("Asset is already disposed.")

        sale_proceeds = Decimal(str(sale_proceeds))
        gain_loss = sale_proceeds - asset.net_book_value

        cat = asset.category
        lines_data = []

        # 1. DR Bank (Proceeds) if bank_account provided and proceeds > 0
        if bank_account_id and sale_proceeds > 0:
            bank = BankAccount.objects.get(id=bank_account_id)
            lines_data.append({'account': bank.gl_account, 'debit': sale_proceeds, 'credit': Decimal('0.0000')})

        # 2. DR Accumulated Depreciation
        if asset.accumulated_depreciation > 0:
            lines_data.append({
                'account': cat.accumulated_depr_gl_account,
                'debit': asset.accumulated_depreciation,
                'credit': Decimal('0.0000')
            })

        # 3. CR Asset Cost Account (Original Cost)
        lines_data.append({
            'account': cat.asset_gl_account,
            'debit': Decimal('0.0000'),
            'credit': asset.purchase_cost
        })

        # 4. Gain or Loss offset
        if gain_loss_account_id and gain_loss != 0:
            gl_acc = Account.objects.get(id=gain_loss_account_id)
            if gain_loss > 0:
                lines_data.append({'account': gl_acc, 'debit': Decimal('0.0000'), 'credit': gain_loss})
            else:
                lines_data.append({'account': gl_acc, 'debit': abs(gain_loss), 'credit': Decimal('0.0000')})

        # Post derecognition entry if balanced
        total_dr = sum(l['debit'] for l in lines_data)
        total_cr = sum(l['credit'] for l in lines_data)
        if total_dr == total_cr and len(lines_data) >= 2:
            LedgerService.post_journal_entry(
                entry_number=f"DISP-{asset.asset_tag}-{disposal_date.strftime('%Y%m%d')}",
                posting_date=disposal_date,
                description=f"Disposal of Asset {asset.asset_tag} - {asset.name}",
                source_module='fixed_assets',
                source_ref=str(asset.id),
                user=user,
                lines_data=lines_data
            )

        asset.status = AssetStatus.DISPOSED
        asset.disposal_date = disposal_date
        asset.disposal_proceeds = sale_proceeds
        asset.disposal_gain_loss = gain_loss
        asset.save(update_fields=['status', 'disposal_date', 'disposal_proceeds', 'disposal_gain_loss'])

        CacheManager.invalidate_assets()
        return asset
