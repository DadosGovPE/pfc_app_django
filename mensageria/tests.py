from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from mensageria.models import EmailStatusBatch, EmailStatusBatchItem, MensagemTemplate
from mensageria.render import build_email_bodies, render_text
from mensageria.status_batch import create_status_batch, process_email_status_batch
from pfc_app.models import Curso, Inscricao, StatusCurso, StatusInscricao, User


class MensageriaRenderTests(SimpleTestCase):
    def test_build_email_bodies_preserva_texto_puro(self):
        corpo = "Ola [user_nome]\nAcesse https://exemplo.com"

        plain_body, html_body = build_email_bodies(corpo)

        self.assertEqual(plain_body, corpo)
        self.assertEqual(html_body, "Ola [user_nome]<br>\nAcesse https://exemplo.com")

    def test_build_email_bodies_gera_fallback_texto_para_html(self):
        corpo = 'Clique em <a href="https://exemplo.com/curso">inscrever-se</a>'

        plain_body, html_body = build_email_bodies(corpo)

        self.assertEqual(plain_body, "Clique em inscrever-se")
        self.assertEqual(html_body, corpo)

    def test_build_email_bodies_converte_quebra_de_linha_em_br_no_html(self):
        corpo = 'Prezado(a),\n\nClique no <a href="https://exemplo.com">link</a>\nEquipe'

        plain_body, html_body = build_email_bodies(corpo)

        self.assertEqual(plain_body, "Prezado(a),\n\nClique no link\nEquipe")
        self.assertEqual(
            html_body,
            'Prezado(a),<br>\n<br>\nClique no <a href="https://exemplo.com">link</a><br>\nEquipe',
        )

    def test_render_text_mantem_substituicao_de_tags(self):
        class Tag:
            ativa = True
            contexto_alias = "user"
            path = "nome"
            padrao = ""

        class User:
            nome = "Maria"

        resultado = render_text(
            'Clique em <a href="https://exemplo.com">[user_nome]</a>',
            {"user_nome": Tag()},
            {"user": User()},
        )

        self.assertEqual(
            resultado, 'Clique em <a href="https://exemplo.com">Maria</a>'
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class EmailStatusBatchTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="admin",
            cpf="00000000001",
            nome="Admin",
            email="admin@example.com",
            password="123",
            role="ADMIN",
        )
        self.user1 = User.objects.create_user(
            username="user1",
            cpf="00000000002",
            nome="Maria",
            email="maria@example.com",
            password="123",
        )
        self.user2 = User.objects.create_user(
            username="user2",
            cpf="00000000003",
            nome="Joao",
            email="joao@example.com",
            password="123",
        )
        self.status_curso = StatusCurso.objects.create(nome="A INICIAR")
        self.status_pendente = StatusInscricao.objects.create(nome="PENDENTE")
        self.status_aprovada = StatusInscricao.objects.create(nome="APROVADA")
        self.curso = Curso.objects.create(
            nome_curso="Curso Teste",
            ementa_curso="Ementa",
            ch_curso=8,
            vagas=20,
            data_inicio="2026-01-10",
            status=self.status_curso,
        )
        self.inscricao1 = Inscricao.objects.create(
            curso=self.curso,
            participante=self.user1,
            status=self.status_pendente,
        )
        self.inscricao2 = Inscricao.objects.create(
            curso=self.curso,
            participante=self.user2,
            status=self.status_aprovada,
        )
        self.template = MensagemTemplate.objects.create(
            nome="Alteracao",
            assunto="Status de [curso_nome_curso]",
            corpo="Ola [user_nome], status alterado para [status_inscricao_nome].",
        )

    def test_create_status_batch_altera_status_e_ignora_ja_alterados(self):
        batch = create_status_batch(
            curso=self.curso,
            inscricao_ids=[self.inscricao1.id, self.inscricao2.id],
            status_destino=self.status_aprovada,
            enviar_email=False,
            template=None,
            assunto="",
            corpo="",
            admin=self.admin,
        )

        self.inscricao1.refresh_from_db()
        self.inscricao2.refresh_from_db()
        self.assertEqual(self.inscricao1.status, self.status_aprovada)
        self.assertEqual(self.inscricao2.status, self.status_aprovada)
        self.assertEqual(batch.total_selecionado, 2)
        self.assertEqual(batch.total_alterado, 1)
        self.assertEqual(batch.total_ignorado, 1)
        self.assertEqual(batch.status, EmailStatusBatch.Status.COMPLETED)
        self.assertEqual(batch.items.count(), 0)

    def test_process_email_status_batch_envia_apenas_para_alterados(self):
        batch = create_status_batch(
            curso=self.curso,
            inscricao_ids=[self.inscricao1.id, self.inscricao2.id],
            status_destino=self.status_aprovada,
            enviar_email=True,
            template=self.template,
            assunto="",
            corpo="",
            admin=self.admin,
        )

        processed = process_email_status_batch(batch.job_id)

        batch.refresh_from_db()
        self.assertTrue(processed)
        self.assertEqual(batch.status, EmailStatusBatch.Status.COMPLETED)
        self.assertEqual(batch.total_enviado, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["maria@example.com"])
        self.assertIn("Curso Teste", mail.outbox[0].subject)
        self.assertEqual(
            batch.items.get().status,
            EmailStatusBatchItem.Status.SENT,
        )
