import json

from django.core.management.base import BaseCommand

from moodle_sync.models import CursoCompletoUsuario
from moodle_sync.services import User, sincronizar_todos_usuarios_moodle


class Command(BaseCommand):
    help = (
        "Ressincroniza apenas usuários com cursos Moodle sem data final, "
        "tentando preencher as datas faltantes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limita a quantidade de usuários processados.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Imprime o resumo final em JSON.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        output_json = options["json"]

        cursos_sem_data = CursoCompletoUsuario.objects.filter(
            data_fim_curso_moodle__isnull=True
        )
        usuarios_ids = list(
            cursos_sem_data.order_by("user_id")
            .values_list("user_id", flat=True)
            .distinct()
        )

        if limit:
            usuarios_ids = usuarios_ids[:limit]

        queryset = User.objects.filter(id__in=usuarios_ids).order_by("id")
        total_sem_data_antes = cursos_sem_data.filter(user_id__in=usuarios_ids).count()

        self.stdout.write(
            "Iniciando ressincronização do Moodle para usuários com datas vazias..."
        )
        self.stdout.write(
            f"- Usuários selecionados: {len(usuarios_ids)}"
        )
        self.stdout.write(
            f"- Cursos sem data antes: {total_sem_data_antes}"
        )

        resultado = sincronizar_todos_usuarios_moodle(queryset=queryset)

        total_sem_data_depois = CursoCompletoUsuario.objects.filter(
            user_id__in=usuarios_ids,
            data_fim_curso_moodle__isnull=True,
        ).count()
        total_preenchidos = total_sem_data_antes - total_sem_data_depois

        resumo = {
            "total_processados": resultado["total_processados"],
            "total_sucesso": resultado["total_sucesso"],
            "total_erro": resultado["total_erro"],
            "total_cursos_salvos": resultado["total_cursos_salvos"],
            "duration_seconds": resultado["duration_seconds"],
            "cursos_sem_data_antes": total_sem_data_antes,
            "cursos_sem_data_depois": total_sem_data_depois,
            "datas_preenchidas": total_preenchidos,
        }

        if output_json:
            self.stdout.write(json.dumps(resumo, ensure_ascii=False))
            return

        for item in resultado["resultados"]:
            status = "OK" if item["ok"] else "ERRO"
            self.stdout.write(
                f"[{status}] usuario={item['usuario']} cpf={item.get('cpf', '')} "
                f"salvos={item.get('cursos_salvos', 0)} "
                f"concluidos={item.get('cursos_concluidos', 0)} "
                f"duracao={item['duration_seconds']}s "
                f"mensagem={item['message']}"
            )

        self.stdout.write("")
        self.stdout.write("Resumo da ressincronização:")
        self.stdout.write(f"- Usuários processados: {resultado['total_processados']}")
        self.stdout.write(f"- Usuários com sucesso: {resultado['total_sucesso']}")
        self.stdout.write(f"- Usuários com erro: {resultado['total_erro']}")
        self.stdout.write(f"- Novos cursos salvos: {resultado['total_cursos_salvos']}")
        self.stdout.write(f"- Cursos sem data antes: {total_sem_data_antes}")
        self.stdout.write(f"- Cursos sem data depois: {total_sem_data_depois}")
        self.stdout.write(f"- Datas preenchidas: {total_preenchidos}")
        self.stdout.write(f"- Duração total: {resultado['duration_seconds']}s")
