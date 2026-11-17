from datetime import date

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from pfc_app.models import (
    AjustesPesquisa,
    Curso,
    CursoPriorizado,
    Curadoria,
    PesquisaCursosPriorizados,
    StatusCurso,
    StatusValidacao,
    Trilha,
    User,
    Validacao_CH,
)


class TrilhasAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ativa = Trilha.objects.create(nome="Trilha atual")
        cls.antiga = Trilha.objects.create(nome="Trilha antiga", ativa=False)
        cls.outra_antiga = Trilha.objects.create(nome="Outra antiga", ativa=False)
        cls.usuario = User.objects.create_superuser(
            username="admin",
            cpf="00000000001",
            nome="Admin",
            email="admin@example.com",
        )
        status_curso = StatusCurso.objects.create(nome="A INICIAR")
        status_validacao = StatusValidacao.objects.create(nome="EM ANÁLISE")
        cls.registros = [
            Curso.objects.create(
                nome_curso="Curso histórico",
                ementa_curso="Ementa",
                ch_curso=8,
                vagas=20,
                data_inicio=date(2026, 1, 10),
                status=status_curso,
                trilha=cls.antiga,
            ),
            Curadoria.objects.create(
                nome_curso="Curadoria histórica",
                mes_competencia=date(2026, 1, 1),
                trilha=cls.antiga,
            ),
            CursoPriorizado.objects.create(
                nome_sugestao_acao="Priorizado histórico",
                mes_competencia=date(2026, 1, 1),
                trilha=cls.antiga,
            ),
            PesquisaCursosPriorizados.objects.create(
                nome="Pesquisa histórica", ano_ref=2026, trilha=cls.antiga,
            ),
            Validacao_CH.objects.create(
                usuario=cls.usuario,
                nome_curso="Validação histórica",
                arquivo_pdf="validacao-teste.pdf",
                ementa="Ementa",
                data_inicio_curso=date(2026, 1, 10),
                data_termino_curso=date(2026, 1, 10),
                status=status_validacao,
                trilha=cls.antiga,
            ),
        ]

    def setUp(self):
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.usuario

    def test_cinco_cadastros_oferecem_apenas_ativas_na_criacao(self):
        for registro in self.registros:
            with self.subTest(model=type(registro).__name__):
                model_admin = admin.site._registry[type(registro)]
                form_class = model_admin.get_form(self.request, fields=("trilha",))
                form = form_class()
                self.assertEqual(list(form.fields["trilha"].queryset), [self.ativa])
                self.assertEqual(form.fields["trilha"].clean(self.ativa.pk), self.ativa)
                self.assertIsNone(form.fields["trilha"].clean(""))
                # POST e valores iniciais não podem liberar uma trilha inativa.
                form = form_class(
                    data={"trilha": self.antiga.pk}, initial={"trilha": self.antiga.pk}
                )
                self.assertFalse(form.is_valid())
                self.assertIn("trilha", form.errors)

    def test_edicao_preserva_vinculo_inativo_e_rejeita_outra_inativa(self):
        for registro in self.registros:
            with self.subTest(model=type(registro).__name__):
                model_admin = admin.site._registry[type(registro)]
                form_class = model_admin.get_form(
                    self.request, obj=registro, fields=("trilha",)
                )
                form = form_class(data={"trilha": self.antiga.pk}, instance=registro)
                self.assertCountEqual(
                    form.fields["trilha"].queryset, [self.ativa, self.antiga]
                )
                self.assertTrue(form.is_valid(), form.errors)
                form.save()
                registro.refresh_from_db()
                self.assertEqual(registro.trilha_id, self.antiga.pk)

                form = form_class(
                    data={"trilha": self.outra_antiga.pk}, instance=registro
                )
                self.assertFalse(form.is_valid())
                self.assertIn("trilha", form.errors)

    def test_pode_trocar_para_ativa_sem_liberar_retorno_para_inativa(self):
        for registro in self.registros:
            with self.subTest(model=type(registro).__name__):
                model_admin = admin.site._registry[type(registro)]
                form_class = model_admin.get_form(
                    self.request, obj=registro, fields=("trilha",)
                )
                form = form_class(data={"trilha": self.ativa.pk}, instance=registro)
                self.assertTrue(form.is_valid(), form.errors)
                form.save()
                registro.refresh_from_db()
                self.assertEqual(registro.trilha_id, self.ativa.pk)
                self.assertEqual(
                    list(form_class(instance=registro).fields["trilha"].queryset),
                    [self.ativa],
                )

    def test_edicao_em_lista_isola_opcoes_por_registro_sem_consultas_por_linha(self):
        for model in (CursoPriorizado, PesquisaCursosPriorizados):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                form_class = model_admin.get_changelist_form(self.request)
                primeiro = model.objects.get(trilha=self.antiga)
                segundo = model(trilha=self.outra_antiga)
                segundo._state.adding = False
                with self.assertNumQueries(0):
                    campo = form_class(instance=primeiro).fields["trilha"]
                    self.assertEqual(campo.clean(str(self.antiga.pk)), self.antiga)
                    with self.assertRaises(ValidationError):
                        campo.clean(str(self.outra_antiga.pk))
                    outro_campo = form_class(instance=segundo).fields["trilha"]
                    self.assertEqual(
                        outro_campo.clean(str(self.outra_antiga.pk)), self.outra_antiga
                    )
                    with self.assertRaises(ValidationError):
                        outro_campo.clean(str(self.antiga.pk))
                    novo_campo = form_class().fields["trilha"]
                    with self.assertRaises(ValidationError):
                        novo_campo.clean(str(self.antiga.pk))

    def test_edicao_em_lista_salva_vinculo_antigo_e_bloqueia_troca_inativa(self):
        for model in (CursoPriorizado, PesquisaCursosPriorizados):
            with self.subTest(model=model.__name__):
                model_admin = admin.site._registry[model]
                formset_class = model_admin.get_changelist_formset(self.request)
                registro = model.objects.get(trilha=self.antiga)
                queryset = model.objects.filter(pk=registro.pk)
                dados = {
                    "form-TOTAL_FORMS": "1",
                    "form-INITIAL_FORMS": "1",
                    "form-0-id": str(registro.pk),
                    "form-0-trilha": str(self.antiga.pk),
                    "form-0-mes_competencia": "2026-01-01",
                }
                formset = formset_class(data=dados, queryset=queryset)
                self.assertTrue(formset.is_valid(), formset.errors)
                formset.save()
                registro.refresh_from_db()
                self.assertEqual(registro.trilha_id, self.antiga.pk)

                dados["form-0-trilha"] = str(self.outra_antiga.pk)
                formset = formset_class(data=dados, queryset=queryset)
                self.assertFalse(formset.is_valid())
                self.assertIn("trilha", formset.errors[0])

    def test_consulta_historica_e_filtro_admin_incluem_trilhas_inativas(self):
        self.assertIn(self.antiga, Trilha.objects.all())
        self.client.force_login(self.usuario)
        response = self.client.get(
            reverse("admin:pfc_app_pesquisacursospriorizados_changelist")
        )
        self.assertContains(response, self.antiga.nome)
        filtro = response.context["cl"].filter_specs[0]
        self.assertIn(self.antiga.pk, [pk for pk, nome in filtro.lookup_choices])


class TrilhasPesquisaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="participante",
            cpf="00000000002",
            nome="Participante",
            email="participante@example.com",
        )
        AjustesPesquisa.objects.create(nome="padrao", ano_ref=2027, is_aberta=True)
        cls.ativa = Trilha.objects.create(nome="Trilha atual", ordem_relatorio=2)
        cls.antiga = Trilha.objects.create(
            nome="Trilha antiga", ativa=False, ordem_relatorio=1
        )
        cls.vazia = Trilha.objects.create(nome="Trilha vazia")
        cls.outro_ano = Trilha.objects.create(nome="Somente outro ano")
        cls.curso = PesquisaCursosPriorizados.objects.create(
            nome="Curso atual", ano_ref=2027, trilha=cls.ativa,
        )
        cls.curso_antigo = PesquisaCursosPriorizados.objects.create(
            nome="Curso antes escolhido", ano_ref=2027, trilha=cls.antiga,
        )
        cls.outro_inativo = PesquisaCursosPriorizados.objects.create(
            nome="Curso inativo não escolhido", ano_ref=2027, trilha=cls.antiga,
        )
        cls.historico = PesquisaCursosPriorizados.objects.create(
            nome="Curso de 2026", ano_ref=2026, trilha=cls.outro_ano,
        )

    def setUp(self):
        self.client.force_login(self.usuario)

    def _contexto_pesquisa(self):
        response = self.client.get(reverse("listar_cursos_priorizados"))
        self.assertEqual(response.status_code, 200)
        return response.context

    def test_pesquisa_oculta_inativas_vazias_e_cursos_de_outros_anos(self):
        contexto = self._contexto_pesquisa()
        self.assertEqual(list(contexto["trilhas"]), [self.ativa])
        self.assertEqual(contexto["cursos_por_trilha"][self.ativa], [self.curso])
        self.assertNotIn(self.antiga, contexto["cursos_por_trilha"])

    def test_resposta_anterior_mostra_apenas_curso_inativo_ja_escolhido(self):
        self.usuario.pesquisa_cursos_priorizados.add(self.curso_antigo, self.historico)
        contexto = self._contexto_pesquisa()
        self.assertEqual(list(contexto["trilhas"]), [self.antiga, self.ativa])
        self.assertEqual(contexto["cursos_por_trilha"][self.antiga], [self.curso_antigo])
        self.assertNotIn(self.outro_ano, contexto["cursos_por_trilha"])

    def test_varios_cursos_na_mesma_trilha_nao_duplicam_trilha_e_outro_fica_no_fim(self):
        outro = PesquisaCursosPriorizados.objects.create(
            nome="Outro", ano_ref=2027, trilha=self.ativa
        )
        contexto = self._contexto_pesquisa()
        self.assertEqual(list(contexto["trilhas"]), [self.ativa])
        self.assertEqual(contexto["cursos_por_trilha"][self.ativa], [self.curso, outro])

    def test_post_rejeita_novo_voto_em_trilha_inativa_e_preserva_historico(self):
        self.usuario.pesquisa_cursos_priorizados.add(self.historico, self.curso)
        response = self.client.post(
            reverse("votar_cursos"),
            {"ano_ref": "2027", "cursos": [self.outro_inativo.pk]},
        )
        self.assertRedirects(
            response,
            reverse("listar_cursos_priorizados"),
            fetch_redirect_response=False,
        )
        self.assertCountEqual(
            self.usuario.pesquisa_cursos_priorizados.all(), [self.historico, self.curso]
        )

    def test_atualiza_resposta_preservando_voto_inativo_existente_e_outros_anos(self):
        self.usuario.pesquisa_cursos_priorizados.add(self.historico, self.curso_antigo)
        response = self.client.post(
            reverse("votar_cursos"),
            {
                "ano_ref": "2027",
                "cursos": [self.curso.pk, self.curso_antigo.pk],
                "comentario": "Atualizado",
            },
        )
        self.assertRedirects(
            response, reverse("lista_cursos"), fetch_redirect_response=False
        )
        self.assertCountEqual(
            self.usuario.pesquisa_cursos_priorizados.all(),
            [self.historico, self.curso_antigo, self.curso],
        )
        self.assertEqual(
            self.usuario.priorizacao_respostas.get(ano_ref=2027).comentario, "Atualizado"
        )
