from rest_framework.views import APIView
from rest_framework.response import Response
from apps.taxation.selectors import tax_rule_list
from apps.taxation.serializers import TaxRuleOutputSerializer

class TaxRuleListAdminApi(APIView):
    def get(self, request):
        rules = tax_rule_list(country_code=request.query_params.get('country'))
        return Response(TaxRuleOutputSerializer(rules, many=True).data)
