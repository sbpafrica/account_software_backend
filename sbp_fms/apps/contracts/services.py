from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.common.cache import CacheManager
from apps.receivables.models import Client
from .models import Contract, ContractStatus


class ContractService:
    @staticmethod
    @transaction.atomic
    def contract_create(*, contract_number: str, client_id: str, title: str,
                        start_date, end_date=None,
                        total_contract_value: Decimal = Decimal('0.0000'),
                        cost_centre: str = '', notes: str = '') -> Contract:
        c_num = contract_number.strip().upper()
        if Contract.objects.filter(contract_number=c_num).exists():
            raise ValidationError(f"Contract '{c_num}' already exists.")

        client = Client.objects.get(id=client_id)
        val = Decimal(str(total_contract_value))
        if val < 0:
            raise ValidationError("Total contract value cannot be negative.")

        contract = Contract.objects.create(
            contract_number=c_num,
            client=client,
            title=title.strip(),
            start_date=start_date,
            end_date=end_date,
            total_contract_value=val,
            status=ContractStatus.ACTIVE,
            cost_centre=cost_centre.strip(),
            notes=notes.strip()
        )
        CacheManager.invalidate_contracts()
        return contract

    @staticmethod
    @transaction.atomic
    def contract_update(*, contract_id: str, title: str = None,
                        status: str = None, total_contract_value: Decimal = None,
                        cost_centre: str = None, notes: str = None) -> Contract:
        contract = Contract.objects.select_for_update().get(id=contract_id)
        if title is not None:
            contract.title = title.strip()
        if status is not None:
            contract.status = status
        if total_contract_value is not None:
            contract.total_contract_value = Decimal(str(total_contract_value))
        if cost_centre is not None:
            contract.cost_centre = cost_centre.strip()
        if notes is not None:
            contract.notes = notes.strip()
        contract.save()
        CacheManager.invalidate_contracts()
        return contract
