from drf_spectacular.views import SpectacularAPIView
from drf_spectacular.renderers import (
    OpenApiJsonRenderer2,
    OpenApiJsonRenderer,
    OpenApiYamlRenderer2,
    OpenApiYamlRenderer
)


class SpectacularJSONExportView(SpectacularAPIView):
    """
    Exports the OpenAPI 3.0 schema directly in JSON format (application/json).
    Accepts ?download=1 to force attachment download.
    """
    renderer_classes = [OpenApiJsonRenderer2, OpenApiJsonRenderer]

    def _get_schema_response(self, request):
        response = super()._get_schema_response(request)
        is_download = request.GET.get('download') in ('1', 'true', 'yes')
        disposition = 'attachment' if is_download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="sbp-fms-openapi-schema.json"'
        response['Access-Control-Allow-Origin'] = '*'
        return response


class SpectacularYAMLExportView(SpectacularAPIView):
    """
    Exports the OpenAPI 3.0 schema directly in YAML format (application/yaml).
    Accepts ?download=1 to force attachment download.
    """
    renderer_classes = [OpenApiYamlRenderer2, OpenApiYamlRenderer]

    def _get_schema_response(self, request):
        response = super()._get_schema_response(request)
        is_download = request.GET.get('download') in ('1', 'true', 'yes')
        disposition = 'attachment' if is_download else 'inline'
        response['Content-Disposition'] = f'{disposition}; filename="sbp-fms-openapi-schema.yaml"'
        response['Access-Control-Allow-Origin'] = '*'
        return response


class SpectacularDownloadView(SpectacularAPIView):
    """
    Forces file download of the OpenAPI schema in requested format (default: json).
    Usage:
      GET /api/schema/download/?format=json
      GET /api/schema/download/?format=yaml
    """
    def _get_schema_response(self, request):
        fmt = request.GET.get('format', 'json').lower()
        if 'yaml' in fmt:
            self.renderer_classes = [OpenApiYamlRenderer2, OpenApiYamlRenderer]
            ext = 'yaml'
        else:
            self.renderer_classes = [OpenApiJsonRenderer2, OpenApiJsonRenderer]
            ext = 'json'

        response = super()._get_schema_response(request)
        response['Content-Disposition'] = f'attachment; filename="sbp-fms-openapi-schema.{ext}"'
        response['Access-Control-Allow-Origin'] = '*'
        return response
