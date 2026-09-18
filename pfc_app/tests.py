from datetime import date

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings

from pfc_app.calendar_invites import (
    build_course_invite_ics,
    send_course_calendar_invite,
)
from pfc_app.models import Curso, Inscricao, StatusCurso, StatusInscricao, User


class OrdenacaoInstrutoresTests(TestCase):
    def setUp(self):
        status_curso = StatusCurso.objects.create(nome="A INICIAR")
        self.status_inscricao = StatusInscricao.objects.create(nome="APROVADA")
        self.curso = Curso.objects.create(
            nome_curso="Curso Teste",
            ementa_curso="Ementa",
            ch_curso=8,
            vagas=20,
            data_inicio="2026-01-10",
            status=status_curso,
        )

    def _criar_instrutor(self, numero, *, principal=False):
        participante = User.objects.create_user(
            username=f"instrutor{numero}",
            cpf=f"{numero:011d}",
            nome=f"Instrutor {numero}",
            email=f"instrutor{numero}@example.com",
            password="123",
        )
        return Inscricao.objects.create(
            curso=self.curso,
            participante=participante,
            status=self.status_inscricao,
            condicao_na_acao="DOCENTE",
            instrutor_principal=principal,
        )

    def test_instrutor_principal_fica_em_primeiro(self):
        primeiro = self._criar_instrutor(1)
        principal = self._criar_instrutor(2, principal=True)

        instrutores = Inscricao.objects.filter(
            curso=self.curso, condicao_na_acao="DOCENTE"
        ).ordenar_instrutores()

        self.assertEqual(list(instrutores), [principal, primeiro])

    def test_sem_principal_mantem_ordem_de_inscricao(self):
        primeiro = self._criar_instrutor(1)
        segundo = self._criar_instrutor(2)

        instrutores = Inscricao.objects.filter(
            curso=self.curso, condicao_na_acao="DOCENTE"
        ).ordenar_instrutores()

        self.assertEqual(list(instrutores), [primeiro, segundo])


class CalendarInviteTests(SimpleTestCase):
    def _inscricao(self, horario="08:30 as 12:00", data_termino=None):
        curso = Curso(
            id=10,
            nome_curso="Curso PFC",
            ementa_curso="Ementa do curso",
            ch_curso=4,
            vagas=20,
            data_inicio=date(2026, 6, 1),
            data_termino=data_termino,
            horario=horario,
            descricao="Descricao",
        )
        participante = User(
            id=20,
            nome="Participante Teste",
            email="participante@example.com",
            cpf="12345678901",
            username="12345678901",
        )
        return Inscricao(id=30, curso=curso, participante=participante)

    @override_settings(TIME_ZONE="America/Sao_Paulo")
    def test_build_course_invite_ics_uses_course_time(self):
        ics = build_course_invite_ics(self._inscricao())

        self.assertIn("METHOD:REQUEST", ics)
        self.assertIn("SUMMARY:Curso PFC", ics)
        self.assertIn("DTSTART;TZID=America/Sao_Paulo:20260601T083000", ics)
        self.assertIn("DTEND;TZID=America/Sao_Paulo:20260601T120000", ics)
        self.assertIn("ATTENDEE;CN=Participante Teste", ics)

    def test_build_course_invite_ics_uses_all_day_without_time(self):
        ics = build_course_invite_ics(
            self._inscricao(horario="", data_termino=date(2026, 6, 3))
        )

        self.assertIn("DTSTART;VALUE=DATE:20260601", ics)
        self.assertIn("DTEND;VALUE=DATE:20260604", ics)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
        DEFAULT_FROM_EMAIL="PFC SEPLAG <pfc@example.com>",
    )
    def test_send_course_calendar_invite_attaches_ics(self):
        sent = send_course_calendar_invite(self._inscricao())

        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["participante@example.com"])
        self.assertEqual(mail.outbox[0].attachments[0][0], "convite-pfc.ics")
        self.assertIn("text/calendar", mail.outbox[0].attachments[0][2])
