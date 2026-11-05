from rest_framework.views import APIView
from rest_framework.response import Response
from apps.treasury.selectors import bank_account_list, bank_transaction_list, liquidity_forecast_get
from apps.treasury.serializers import BankAccountOutputSerializer, BankTransactionOutputSerializer

class BankAccountListAdminApi(APIView):
    def get(self, request):
        accounts = bank_account_list(country_code=request.query_params.get('country'))
        return Response(BankAccountOutputSerializer(accounts, many=True).data)

class CashForecastAdminApi(APIView):
    def get(self, request):
        forecast = liquidity_forecast_get()
        return Response(forecast)

class BankTransactionListAdminApi(APIView):
    def get(self, request):
        transactions = bank_transaction_list(is_reconciled=request.query_params.get('reconciled'))
        return Response(BankTransactionOutputSerializer(transactions, many=True).data)
