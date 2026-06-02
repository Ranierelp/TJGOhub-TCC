from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from tools.utils import send_email
from rest_framework.throttling import AnonRateThrottle

from django.contrib.auth.models import Group, Permission

from apps.commons.api.v1.permissions import IsAdmin, MineOrReadOnly
from apps.commons.api.v1.viewsets import BaseModelApiViewSet
from apps.commons.models import Email
from apps.users.api.v1 import exceptions, serializers


class UserViewSet(BaseModelApiViewSet):
    """
    Gerenciamento de usuários — operações restritas a Admin.

    Exceção: `get_me` (GET /users/me/) é acessível a qualquer autenticado;
    o usuário precisa conseguir ler o próprio perfil pra montar a navbar e
    descobrir os próprios grupos/permissões.
    """
    model = apps.get_model("users", "User")
    permission_classes = [IsAuthenticated, IsAdmin]

    def get_serializer_class(self):
        # /me/ sempre responde com UserSerializer (groups como objetos, não IDs)
        if self.action == "get_me":
            return serializers.UserSerializer
        if self.request and self.request.method in ("PATCH", "PUT"):
            return serializers.UserUpdateSerializer
        return serializers.UserSerializer

    # ── /users/me/ ─────────────────────────────────────────────────────────
    @action(
        methods=["get", "patch"],
        detail=False,
        url_path="me",
        # Sobrescreve o IsAdmin do viewset — qualquer autenticado acessa o próprio perfil.
        permission_classes=[IsAuthenticated],
    )
    def get_me(self, request, *args, **kwargs):
        if request.method == "PATCH":
            serializer = serializers.UserSelfUpdateSerializer(
                request.user, data=request.data, partial=True
            )
            serializer.is_valid(raise_exception=True)
            serializer.save()
            # Retorna o perfil completo após salvar
            return Response(
                self.get_serializer(request.user).data,
                status=status.HTTP_200_OK,
            )
        return Response(self.get_serializer(self.request.user, many=False).data, status=status.HTTP_200_OK)

    # ── Email de boas-vindas após criação ──────────────────────────────────
    def perform_create(self, serializer):
        super().perform_create(serializer)
        user = serializer.instance

        try:
            token = default_token_generator.make_token(user)
            link = f"{settings.SITE_URL}/auth/nova-senha?id={user.id}&key={token}"

            email_model, _ = Email.objects.get_or_create()
            template = email_model.user_welcome
            if not template:
                template_path = settings.APPS_DIR / "commons/templates/emails/user_welcome.html"
                with open(template_path, "r", encoding="utf-8") as f:
                    template = f.read()

            send_email(
                email_model.user_welcome_subject,
                settings.EMAIL_HOST_USER,
                user.email,
                {"email": user.email, "link": link},
                template,
            )
        except Exception:
            pass

    # ── Trocar grupo do usuário ────────────────────────────────────────────
    @extend_schema(
        summary="Atribui um grupo (perfil) a um usuário",
        description=(
            "Remove todos os grupos atuais do usuário e atribui o grupo passado em "
            "`group` (nome). Útil pra promover Visualizador → QA, demover QA → "
            "Visualizador, etc."
        ),
        request={"application/json": {"type": "object", "properties": {"group": {"type": "string"}}}},
        tags=["Usuários"],
    )
    @action(detail=True, methods=["post"], url_path="set-group")
    def set_group(self, request, id=None):
        user = self.get_object()
        group_name = request.data.get("group")

        if not group_name:
            return Response(
                {"detail": "É necessário informar o nome do grupo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        group = Group.objects.filter(name=group_name).first()
        if not group:
            return Response(
                {"detail": f"Grupo '{group_name}' não existe."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mantemos a regra "um perfil por usuário" — clear() antes do add()
        # garante que trocar Visualizador → QA não deixe ambos atrelados.
        user.groups.clear()
        user.groups.add(group)
        return Response(self.get_serializer(user).data, status=status.HTTP_200_OK)



class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = serializers.TokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)

            email = request.data.get("email")
            if not email:
                return Response({"error": _("O campo e-mail é obrigatório.")}, status=status.HTTP_400_BAD_REQUEST)

            User = apps.get_model("users", "User")
            try:
                user = User.objects.get(email=email)
                user.last_login = timezone.now()
                user.save()
            except User.DoesNotExist:
                return Response({"error": _("Usuário não encontrado.")}, status=status.HTTP_404_NOT_FOUND)

            # Monta a resposta com dados extras
            response_data = serializer.validated_data
            response_data["user"] = {
                "id": str(user.id),
                "email": user.email,
                "name": user.get_full_name(),
                "is_active": user.is_active
            }

        except TokenError as e:
            raise InvalidToken(e.args[0])

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get("refresh")

        if not refresh_token:
            return Response({"error": _("O refresh token é obrigatório.")}, status=status.HTTP_400_BAD_REQUEST)

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception:
            return Response({"error": _("Refresh token inválido.")}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": _("Logout realizado com sucesso.")}, status=status.HTTP_200_OK)


class RegisterView(APIView):
    http_method_names = ["post"]
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]

    def post(self, *args, **kwargs):
        serializer = serializers.UserRegisterSerializer(data=self.request.data)

        if serializer.is_valid(raise_exception=True):
            email_model, created = Email.objects.get_or_create()
            subject = email_model.user_welcome_subject
            template = email_model.user_welcome

            new_user = get_user_model().objects.create_user(**serializer.validated_data)

            data = {
                "email": serializer.validated_data["email"],
                "link": f"{settings.SITE_URL}/bem-vindo?token={RefreshToken.for_user(new_user).access_token}",
            }

            send_email(subject, settings.EMAIL_HOST_USER, serializer.validated_data["email"], data, template)
            return Response(status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PasswordResetKeyWebToken(APIView):
    http_method_names = ["post"]
    permission_classes = [AllowAny, ]

    def post(self, *args, **kwargs):
        """
        API View that receives a POST with a user's email.
        Send email to user, to reset password.
        """
        if "email" not in self.request.data:
            return Response({"error": _("É necessário informar um e-mail válido.")}, status=status.HTTP_400_BAD_REQUEST)

        serializer = serializers.PasswordResetKeyWebTokenSerializer(data={"email": self.request.data["email"]})
        if serializer.is_valid(raise_exception=True):
            if serializer.validated_data["user"] is not None:
                email_model, created = Email.objects.get_or_create()
                subject = email_model.user_reset_password_subject
                template = email_model.user_reset_password

                # Fallback para o arquivo estático se o template não estiver configurado no admin
                if not template:
                    template_path = settings.APPS_DIR / "commons/templates/emails/user_reset_password.html"
                    with open(template_path, "r", encoding="utf-8") as f:
                        template = f.read()

                data = {
                    "email": serializer.validated_data["email"],
                    "link": f"{settings.SITE_URL}/auth/nova-senha?id={serializer.validated_data['user']}&key={serializer.validated_data['token']}",
                }

                send_email(subject, settings.EMAIL_HOST_USER, serializer.validated_data["email"], data, template)

            return Response({"success": "Se o email existir, um link de recuperação foi enviado."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(auth=[])
class PasswordResetWebToken(APIView):
    authentication_classes = []
    permission_classes = [AllowAny, ]

    def post(self, request, *args, **kwargs):
        """
        API View that receives a POST with a id, key, confirm_password and new_password.
        Change paswsord and returns a JSON Web Token that can be used for authenticated requests.
        """
        serializer = serializers.PasswordResetWebTokenSerializer(data=request.data)
        if serializer.is_valid(raise_exception=True):
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# =============================================================================
# Group e Permission — alimentam a tela /dashboard/perfis/
# =============================================================================

# Apps do domínio TJGOhub. Filtra a listagem de Permission pra esconder
# permissions de apps internos do Django (admin, contenttypes, sessions, etc.)
# que poluiriam a tela do front sem servir pra nada.
PROJECT_APP_LABELS = [
    "cases", "projects", "runs", "results",
    "environments", "kanban", "tags", "users",
]


class GroupViewSet(viewsets.ModelViewSet):
    """
    CRUD de grupos (perfis). Admin-only.

    Permite:
    - GET    /user/groups/         → lista perfis com suas permissions
    - GET    /user/groups/{id}/    → detalha um perfil
    - POST   /user/groups/         → cria perfil novo (body: name + permission_ids[])
    - PATCH  /user/groups/{id}/    → atualiza nome e/ou permissions
    - DELETE /user/groups/{id}/    → remove perfil (bloqueado para os 3 grupos-base)
    """
    queryset = Group.objects.all().prefetch_related("permissions__content_type").order_by("name")
    serializer_class = serializers.GroupDetailSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = "pk"

    # Grupos criados pela migration 0004 — deletar quebra a matriz de permissões.
    _PROTECTED_GROUPS = {"Admin", "QA", "Visualizador"}

    def destroy(self, request, *args, **kwargs):
        group = self.get_object()
        if group.name in self._PROTECTED_GROUPS:
            return Response(
                {"detail": f"O grupo '{group.name}' é padrão do sistema e não pode ser removido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Lista permissions disponíveis. Read-only — permissions são geradas
    automaticamente pelo Django pra cada model registrado; não dá pra
    criar via API. Filtrado pra mostrar só apps do projeto.
    """
    queryset = Permission.objects.filter(
        content_type__app_label__in=PROJECT_APP_LABELS,
    ).select_related("content_type").order_by("content_type__app_label", "codename")
    serializer_class = serializers.PermissionSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    lookup_field = "pk"
    pagination_class = None   # lista pequena (~50 perms) — não precisa paginar
