r"""Compare as consultas atuais sem acessar o banco configurado no app.

Execute: .venv\Scripts\python.exe docs/diagnostico_carga_horaria.py
Usa os models reais e extrai as consultas diretamente de views.py por AST.
O banco SQLite existe apenas em memoria; nenhum dado real e alterado.
"""

import ast
from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from django.conf import settings

settings.configure(
    INSTALLED_APPS=["django.contrib.auth", "django.contrib.contenttypes", "pfc_app"],
    DATABASES={
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
        "migration_test": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"},
    },
    AUTH_USER_MODEL="pfc_app.User",
    SECRET_KEY="isolated-diagnostic",
    USE_TZ=True,
)

import django

django.setup()

from django.apps import apps
from django.db import connection, connections, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.db.models import Max, OuterRef, Q, Subquery, Sum
from django.test.utils import CaptureQueriesContext
from pfc_app.models import Curso, Inscricao, StatusCurso, StatusInscricao, Turma, User
from pfc_app.carga_horaria import inscricoes_ch_unicas, total_ch_pfc

TREE = ast.parse((ROOT / "pfc_app/views.py").read_text(encoding="utf-8"))
FUNCTIONS = {node.name: node for node in TREE.body if isinstance(node, ast.FunctionDef)}


def execute(nodes, namespace):
    module = ast.Module(body=nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), "pfc_app/views.py", "exec"), namespace)


def assignments(function, names):
    return sorted([
        node for node in ast.walk(FUNCTIONS[function])
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id in names for target in node.targets)
    ], key=lambda node: node.lineno)


def compare(user, start=date(2026, 3, 1), end=date(2027, 2, 28)):
    namespace = dict(
        Inscricao=Inscricao, Q=Q, Sum=Sum, Max=Max, OuterRef=OuterRef,
        usuario=user, data_corte=start, data_fim_considerada=end,
        total_ch_pfc=total_ch_pfc,
    )
    # A API executa seu filtro e seu agrupamento originais.
    execute(assignments("carga_horaria_por_cpf", {"carga_pfc"}), namespace)
    api = namespace["carga_pfc"]
    # Usa o mesmo conjunto elegivel para isolar a diferenca da agregacao da tela.
    namespace["inscricoes_do_usuario"] = Inscricao.objects.filter(
        ~Q(status__nome="CANCELADA"), ~Q(status__nome="EM FILA"),
        curso__status__nome="FINALIZADO", concluido=True, participante=user,
        curso__data_termino__gte=start, curso__data_termino__lte=end,
    )
    namespace.update(data_inicio_filtro=start, data_fim_filtro=end,
                     data_inicio_ciclo=start, data_fim_padrao=end, usuario_alvo=user)
    execute(assignments("carga_horaria", {"carga_horaria_pfc"}), namespace)
    screen = namespace["carga_horaria_pfc"]
    report_namespace = dict(
        Inscricao=Inscricao, Q=Q, Sum=Sum, OuterRef=OuterRef,
        data_inicio=start, data_fim=end,
        inscricoes_ch_unicas=inscricoes_ch_unicas,
    )
    report_body = FUNCTIONS["usuarios_sem_ch"].body
    first = next(i for i, n in enumerate(report_body) if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == "inscricoes" for t in n.targets))
    last = next(i for i, n in enumerate(report_body) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "validacoes" for t in n.targets))
    execute(report_body[first:last], report_namespace)
    report = User.objects.filter(pk=user.pk).annotate(
        total=Subquery(report_namespace["inscricoes"])
    ).values_list("total", flat=True).get() or 0
    return screen, report, api


class DiagnosticoCH(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with connection.schema_editor() as editor:
            for model in apps.get_models():
                editor.create_model(model)
        cls.finalizado = StatusCurso.objects.create(nome="FINALIZADO")
        cls.aberto = StatusCurso.objects.create(nome="A INICIAR")
        cls.aprovada = StatusInscricao.objects.create(nome="APROVADA")
        cls.cancelada = StatusInscricao.objects.create(nome="CANCELADA")

    def setUp(self):
        index = User.objects.count() + 1
        self.user = User.objects.create(
            username=f"teste{index}", cpf=f"{index:011d}",
            nome="Teste", email=f"teste{index}@example.com",
        )

    def course(self, name, hours, turma="TURMA1", end=date(2026, 6, 1),
               completed=True, canceled=False, finalized=True):
        curso = Curso.objects.create(
            nome_curso=name, ementa_curso="Teste", ch_curso=hours, vagas=20,
            data_inicio=end, data_termino=end,
            turma=Turma.objects.get_or_create(
                codigo=turma, defaults={"nome": turma.replace("TURMA", "TURMA ")}
            )[0],
            status=self.finalizado if finalized else self.aberto,
        )
        inscricao = Inscricao.objects.create(
            curso=curso, participante=self.user, status=self.aprovada, concluido=completed,
        )
        if canceled:
            Inscricao.objects.filter(pk=inscricao.pk).update(status=self.cancelada)
        return curso

    def check(self, label, expected, **kwargs):
        with CaptureQueriesContext(connection) as queries:
            actual = compare(self.user, **kwargs)
        self.last_sql = [query["sql"] for query in queries.captured_queries]
        print(f"{label}: tela={actual[0]}, relatorio={actual[1]}, API={actual[2]}")
        self.assertEqual(actual, expected)

    def test_01_single(self):
        self.course("Excel", 20)
        self.check("Uma conclusao", (20, 20, 20))

    def test_02_same_name_same_hours(self):
        self.course("Excel", 20)
        self.course("Excel", 20, "TURMA2")
        self.check("Mesmo nome, 20h + 20h", (20, 20, 20))

    def test_03_same_name_different_hours(self):
        self.course("Excel", 20)
        self.course("Excel", 30, "TURMA2")
        self.check("Mesmo nome, 20h + 30h", (30, 30, 30))

    def test_04_different_names_same_hours(self):
        self.course("Excel", 20)
        self.course("Python", 20)
        self.check("Nomes diferentes, 20h + 20h", (40, 40, 40))

    def test_05_separate_cycles(self):
        self.course("Excel", 20, end=date(2027, 2, 28))
        self.course("Excel", 20, "TURMA2", end=date(2027, 3, 1))
        self.check("Conclusoes em ciclos distintos: ciclo 2026", (20, 20, 20))
        self.check("Conclusoes em ciclos distintos: ciclo 2027", (20, 20, 20),
                   start=date(2027, 3, 1), end=date(2028, 2, 29))

    def test_06_ineligible(self):
        self.course("Excel", 20)
        self.course("Excel", 30, "TURMA2", completed=False)
        self.course("Excel", 40, "TURMA3", finalized=False)
        self.check("Nao concluido / nao finalizado excluidos", (20, 20, 20))

    def test_07_canceled(self):
        self.course("Excel", 20, canceled=True)
        self.check("Concluido marcado como cancelado", (0, 0, 0))

    def test_08_name_variation(self):
        self.course("Excel", 20)
        self.course("Excel ", 20, "TURMA2")
        self.check("Nome com espaco adicional", (40, 40, 40))

    def test_09_leap_year(self):
        import calendar
        namespace = dict(date=date, calendar=calendar)
        node = FUNCTIONS["obter_periodo_referencia_ch"]
        execute([node], namespace)
        period = namespace["obter_periodo_referencia_ch"]
        self.assertEqual(period(date(2028, 2, 29)), (date(2027, 3, 1), date(2028, 2, 29)))
        self.assertEqual(period(date(2028, 3, 1)), (date(2028, 3, 1), date(2029, 2, 28)))

    def test_10_multiple_repeated_hours(self):
        self.course("Excel", 20)
        self.course("Excel", 20, "TURMA2")
        self.course("Excel", 30, "TURMA3")
        self.check("Mesmo nome, 20h + 20h + 30h", (30, 30, 30))

    def test_11_dynamic_turma(self):
        turma = Turma.objects.create(nome="  Grupo avançado  ", ordem=15)
        curso = self.course("Excel", 20)
        curso.turma = turma
        curso.save()
        self.assertEqual(curso.get_turma_display(), "Grupo avançado")
        self.assertEqual(curso.nome_formatado, "Excel - Grupo avançado")
        self.assertTrue(curso.exibir_turma)
        with self.assertRaises(ProtectedError):
            turma.delete()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Turma.objects.create(nome="grupo avançado")

    def test_12_participants_do_not_mix(self):
        self.course("Excel", 20)
        other = User.objects.create(username="outro", cpf="99999999999", email="outro@example.com")
        curso = self.course("Excel", 100, "TURMA2", completed=False)
        Inscricao.objects.create(curso=curso, participante=other, status=self.aprovada, concluido=True)
        self.check("Outro participante com CH maior", (20, 20, 20))

    def test_13_default_display(self):
        curso = self.course("Excel", 20)
        self.assertFalse(curso.exibir_turma)
        self.assertEqual(curso.nome_formatado, "Excel")


class MigrationTurmaTests(unittest.TestCase):
    def test_preserves_existing_courses_and_enrollments(self):
        conn = connections["migration_test"]
        executor = MigrationExecutor(conn)
        old_target = [("pfc_app", "0107_normaliza_instituicao_promotora_enap")]
        new_target = [("pfc_app", "0108_turma_dinamica")]
        executor.migrate(old_target)
        old_apps = executor.loader.project_state(old_target).apps
        def old_model(name):
            return old_apps.get_model("pfc_app", name).objects.using("migration_test")
        status = old_model("StatusCurso").create(nome="FINALIZADO")
        user = old_model("User").create(username="migracao", cpf="88888888888", email="m@example.com")
        approved = old_model("StatusInscricao").create(nome="APROVADA")
        courses = []
        for code in ["TURMA1", "TURMA2", "TURMA10", "EXTRA"]:
            curso = old_model("Curso").create(
                nome_curso="Excel", ementa_curso="Teste", ch_curso=20, vagas=10,
                data_inicio=date(2026, 3, 1), data_termino=date(2026, 4, 1),
                status_id=status.pk, turma=code,
            )
            enrollment = old_model("Inscricao").create(
                curso_id=curso.pk, participante_id=user.pk, status_id=approved.pk,
                concluido=True, ch_valida=20,
            )
            courses.append((curso.pk, code, enrollment.pk))
        executor = MigrationExecutor(conn)
        executor.migrate(new_target)
        new_apps = executor.loader.project_state(new_target).apps
        for course_id, code, enrollment_id in courses:
            curso = new_apps.get_model("pfc_app", "Curso").objects.using("migration_test").get(pk=course_id)
            self.assertEqual(curso.turma.codigo, code)
            enrollment = new_apps.get_model("pfc_app", "Inscricao").objects.using("migration_test").get(pk=enrollment_id)
            self.assertEqual(enrollment.curso_id, course_id)
            self.assertEqual(enrollment.ch_valida, 20)
        executor = MigrationExecutor(conn)
        executor.migrate(old_target)
        for course_id, code, _ in courses:
            self.assertEqual(old_model("Curso").get(pk=course_id).turma, code)
        executor = MigrationExecutor(conn)
        executor.migrate(new_target)


if __name__ == "__main__":
    unittest.main(verbosity=2)
