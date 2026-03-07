from django.conf.urls import include
from django.urls import path

from apps.commons.api.v1.router import common_router
from apps.users.api.v1.router import auth_urls, user_router
from apps.projects.api.v1.router import projects_router
from apps.environments.api.v1.router import environments_router
from apps.tags.api.v1.router import tags_router
from apps.cases.api.v1.router import cases_router
from apps.runs.api.v1.router import runs_router
from apps.results.api.v1.router import results_router
from apps.runs.api.v1.report_views import UploadReportView

api_v1_0_urls = [
    path("common/", include((common_router.urls, "common"), namespace="common")),
    path("user/", include((user_router.urls, "user"), namespace="user")),

    # Endpoint específico para upload do relatório do Playwright Hub Reporter.
    path("runs/upload-report/",UploadReportView.as_view(),name="runs-upload-report"),

    path("", include((projects_router.urls, "projects"), namespace="projects")),
    path("", include((environments_router.urls, "environments"), namespace="environments")),
    path("", include((tags_router.urls, "tags"), namespace="tags")),
    path("", include((cases_router.urls, "cases"), namespace="cases")),
    path("", include((runs_router.urls, "runs"), namespace="runs")),
    path("", include((results_router.urls, "results"), namespace="results")),
] + auth_urls
