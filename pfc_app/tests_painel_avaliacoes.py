import copy
import hashlib
import importlib.util
import json
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError
from django.template.loader import render_to_string
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PainelAvaliacoes, User
from .sentimento.services import (
    COLUNAS, DadosInvalidos, consultar_explorer, fonte_avaliacoes, hash_texto,
    normalizar_resultado, publicar_resultados,
)
from .views_avaliacoes import painel_avaliacoes

TOKEN = "token-exclusivo-de-teste-" + "x" * 40

def linha(texto="Ótimo curso", participante="1", curso="10"):
    return {"p": participante, "id_curso": curso, "t": "1", "curso": "Curso teste",
            "mes": "2026-11", "txt": texto}

def classificacao(texto="Ótimo curso", sentimento="Positivo"):
    return {"text_hash": hash_texto(texto), "sentimento": sentimento,
            "confianca": .92, "temas": ["Instrutor e didática"]}

class PermissoesPainelTests(SimpleTestCase):
    def test_visitante_redirecionado_antes_de_ler_dados(self):
        request = RequestFactory().get("/dashboard/avaliacoes/")
        request.user = AnonymousUser()
        self.assertEqual(painel_avaliacoes(request).status_code, 302)

    def test_staff_superusuario_e_gespe_sem_role_admin_nao_acessam(self):
        for role in ("USER", "GESPE"):
            request = RequestFactory().get("/dashboard/avaliacoes/")
            request.user = SimpleNamespace(is_authenticated=True, is_active=True,
                                           role=role, is_staff=True, is_superuser=True)
            with self.assertRaises(PermissionDenied): painel_avaliacoes(request)

    def test_admin_inativo_bloqueado(self):
        request = RequestFactory().get("/dashboard/avaliacoes/")
        request.user = SimpleNamespace(is_authenticated=True, is_active=False, role="ADMIN")
        with self.assertRaises(PermissionDenied): painel_avaliacoes(request)

    def test_menu_somente_no_dropdown_do_usuario_admin(self):
        for role in ("ADMIN", "USER"):
            user = SimpleNamespace(is_authenticated=True, role=role, username="teste", groups=Mock())
            user.groups.filter.return_value.exists.return_value = False
            html = render_to_string("parciais/_nav.html", {"user": user})
            self.assertEqual("Dashboard de Avaliações" in html, role == "ADMIN")
            if role == "ADMIN": self.assertLess(html.index("Meu Perfil"), html.index("Dashboard de Avaliações"))

class NormalizacaoPainelTests(SimpleTestCase):
    def test_colunas_originais_tipos_postgres_e_privacidade(self):
        dados = normalizar_resultado([*COLUNAS, "Nome"], [
            [1, 10, 2, " Curso ", date(2026, 11, 9), " Bom _x000D_\n  curso  ", "NOME PRIVADO"],
            [2, 10, 2, " Curso ", date(2026, 11, 9), None, "OUTRO NOME"],
        ])
        self.assertEqual(dados[0]["txt"], "Bom\ncurso")
        self.assertEqual(dados[0]["mes"], "2026-11")
        self.assertEqual(dados[1]["txt"], "")
        self.assertNotIn("Nome", dados[0])

    def test_datas_invalidas_e_colunas_ausentes(self):
        with self.assertRaises(DadosInvalidos): normalizar_resultado(["Nome"], [])
        with self.assertRaises(DadosInvalidos): normalizar_resultado(COLUNAS, [[1, 2, 3, "Curso", None, "Texto"]])

    @patch("pfc_app.sentimento.services.Query.objects.get")
    def test_sql_com_escrita_ou_multiplas_instrucoes_recusado(self, get):
        for sql in ("DELETE FROM pfc_app_user", "SELECT 1; SELECT 2;"):
            get.return_value.final_sql.return_value = sql
            with self.assertRaises(DadosInvalidos): consultar_explorer()
            get.return_value.execute_query_only.assert_not_called()

    @patch("pfc_app.sentimento.services.consultar_explorer")
    def test_hash_independente_da_ordem_mas_detecta_alteracoes(self, consulta):
        consulta.return_value = [linha(), linha("Outro texto")]
        a = fonte_avaliacoes()
        consulta.return_value.reverse()
        self.assertEqual(fonte_avaliacoes()["source_hash"], a["source_hash"])
        consulta.return_value[0]["txt"] = "Alterado"
        self.assertNotEqual(fonte_avaliacoes()["source_hash"], a["source_hash"])

@override_settings(PFC_AVALIACOES_SYNC_TOKEN=TOKEN)
class ApiAvaliacoesTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.auth = {"HTTP_AUTHORIZATION": "Bearer " + TOKEN}
        self.rows = [linha(), linha(participante="2"), linha("", curso="20")]
        self.mock = patch("pfc_app.sentimento.services.consultar_explorer", return_value=self.rows)
        self.mock.start(); self.addCleanup(self.mock.stop)
        self.fonte = fonte_avaliacoes()
        self.payload = {"schema_version": 1, "source_hash": self.fonte["source_hash"],
                        "model_version": "modelo-teste-1", "generated_at": timezone.now().isoformat(),
                        "resultados": [classificacao()]}

    def post(self, data=None, **kwargs):
        return self.client.post(reverse("api_resultados_avaliacoes"),
                                data=json.dumps(self.payload if data is None else data),
                                content_type="application/json", **self.auth, **kwargs)

    def test_ambas_as_rotas_exigem_token_dedicado(self):
        for route in ("api_fonte_avaliacoes", "api_resultados_avaliacoes"):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 401)
        user = User.objects.create_user(username="admin", cpf="00000000000", nome="Admin", email="a@example.com", role="ADMIN")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("api_fonte_avaliacoes")).status_code, 401)
        self.assertEqual(self.client.get(reverse("api_fonte_avaliacoes"), HTTP_AUTHORIZATION="Bearer errado").status_code, 401)

    def test_token_nao_configurado_falha_fechado(self):
        for token in ("", "curto"):
            with override_settings(PFC_AVALIACOES_SYNC_TOKEN=token):
                self.assertEqual(self.client.get(reverse("api_fonte_avaliacoes"), **self.auth).status_code, 503)

    def test_fonte_e_publicacao_sem_csrf_mas_com_token(self):
        response = self.client.get(reverse("api_fonte_avaliacoes"), **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True, "alterado": True, "avaliacoes": 3, "comentarios": 2, "cursos": 1})
        publicado = PainelAvaliacoes.objects.get(pk=1).publicado
        self.assertEqual(len(publicado["registros"]), 2)
        self.assertNotIn("text_hash", publicado["registros"][0])

    def test_reenvio_idempotente(self):
        self.post()
        quando = PainelAvaliacoes.objects.get(pk=1).atualizado_em
        self.assertFalse(self.post().json()["alterado"])
        self.assertEqual(PainelAvaliacoes.objects.get(pk=1).atualizado_em, quando)

    def test_fonte_alterada_nao_sobrescreve(self):
        PainelAvaliacoes.objects.create(pk=1, publicado={"anterior": True})
        self.rows[0]["txt"] = "Alterado durante análise"
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(PainelAvaliacoes.objects.get(pk=1).publicado, {"anterior": True})

    def test_análise_incompleta_extra_duplicada_ou_invalida_recusada(self):
        variantes = [[], [classificacao(), classificacao()], [classificacao("Desconhecido")]]
        for campo, valor in (("sentimento", "aleatório"), ("sentimento", []), ("confianca", True),
                             ("confianca", float("nan")), ("confianca", 1.1), ("temas", ["Tema inválido"]),
                             ("temas", ["Instrutor e didática"]*2), ("temas", [[]])):
            r = classificacao(); r[campo] = valor; variantes.append([r])
        for resultados in variantes:
            data = {**self.payload, "resultados": resultados}
            self.assertEqual(self.post(data).status_code, 422, data)
        self.assertFalse(PainelAvaliacoes.objects.exists())

    def test_dados_excluidos_saem_da_proxima_publicacao(self):
        self.post()
        self.rows.clear()
        data = {**self.payload, "source_hash": fonte_avaliacoes()["source_hash"], "resultados": []}
        response = self.post(data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(PainelAvaliacoes.objects.get(pk=1).publicado["registros"], [])

    def test_analise_antiga_nao_substitui_a_mais_recente(self):
        self.post()
        data = copy.deepcopy(self.payload)
        data["model_version"] = "outro-modelo"
        data["generated_at"] = (timezone.now()-timedelta(days=1)).isoformat()
        self.assertEqual(self.post(data).status_code, 409)
        self.assertEqual(PainelAvaliacoes.objects.get(pk=1).publicado["model_version"], "modelo-teste-1")

    def test_formato_e_tamanho(self):
        route = reverse("api_resultados_avaliacoes")
        self.assertEqual(self.client.post(route, data="{", content_type="application/json", **self.auth).status_code, 400)
        self.assertEqual(self.client.post(route, data="{}", content_type="text/plain", **self.auth).status_code, 415)
        with override_settings(PFC_AVALIACOES_SYNC_MAX_BYTES=2): self.assertEqual(self.post().status_code, 413)
        self.assertEqual(self.client.get(route, **self.auth).status_code, 405)

    def test_erros_de_banco_nao_expoem_sql(self):
        with patch("pfc_app.views_avaliacoes.fonte_avaliacoes", side_effect=DatabaseError("SQL privado")):
            with self.assertLogs("pfc_app.views_avaliacoes", level="ERROR"):
                response = self.client.get(reverse("api_fonte_avaliacoes"), **self.auth)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(b"SQL privado", response.content)

    def test_dashboard_escape_e_sem_classificacao_local(self):
        user = User.objects.create_user(username="admin", cpf="00000000000", nome="Admin", email="a@example.com", role="ADMIN")
        self.client.force_login(user)
        PainelAvaliacoes.objects.create(pk=1, publicado={"registros": [{**linha("</script><script>alert(1)</script>"), "sent":"Positivo", "conf":.9, "temas":[]}], "total_linhas":1,"total_cursos":1})
        response = self.client.get(reverse("painel_avaliacoes"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recarregar painel")
        self.assertNotContains(response, "atualizar-form")
        self.assertNotContains(response, "</script><script>alert(1)</script>")
        self.assertContains(response, r"\u003C/script\u003E")
        self.assertIn("no-store", response["Cache-Control"])

class ClienteSincronizacaoTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        path = Path(__file__).resolve().parent.parent / "integracoes/pfc_sync/sincronizar_pfc.py"
        spec = importlib.util.spec_from_file_location("pfc_sync_tests", path)
        cls.sync = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.sync)

    def test_deduplica_reutiliza_cache_e_omite_textos_vazios(self):
        fonte = {"schema_version":1,"registros":[{**linha(t),"text_hash":hash_texto(t)} for t in ("Texto", "Texto", "")]}
        cache = {}; classificar = Mock(return_value=[{"sentimento":"Positivo","confianca":.9,"temas":[]}])
        a = self.sync.analisar(fonte, cache, classificar)
        self.assertEqual(len(a), 1)
        classificar.assert_called_once_with(["Texto"])
        self.sync.analisar(fonte, cache, classificar)
        self.assertEqual(classificar.call_count, 1)

    def test_http_exige_opcao_explicita(self):
        with self.assertRaises(self.sync.ErroIntegracao): self.sync.requisicao("http://127.0.0.1", "api/avaliacoes/fonte/", TOKEN)

    def test_redirect_nao_encaminha_token(self):
        redirect = self.sync.SemRedirecionamento()
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://outro.invalid/"))
