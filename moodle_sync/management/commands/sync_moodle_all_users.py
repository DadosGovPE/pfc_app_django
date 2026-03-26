import json

from django.core.management.base import BaseCommand

from moodle_sync.services import sincronizar_todos_usuarios_moodle


class Command(BaseCommand):
    help = "Sincroniza cursos concluídos do Moodle para todos os usuários do sistema."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Limita a quantidade de usuários processados.",
        )
        parser.add_argument(
            "--only-errors",
            action="store_true",
            help="Exibe no final apenas os usuários com erro.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Imprime o resumo final em JSON.",
        )
        parser.add_argument(
            "--carreira-sigla",
            type=str,
            default=None,
            help="Filtra usuários pela sigla da carreira, por exemplo GGPOG.",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        only_errors = options["only_errors"]
        output_json = options["json"]
        carreira_sigla = options["carreira_sigla"]

        descricao = "todos os usuários"
        if carreira_sigla:
            descricao = f"usuários com carreira={carreira_sigla}"
        self.stdout.write(f"Iniciando sincronização do Moodle para {descricao}...")
        resultado = sincronizar_todos_usuarios_moodle(
            limit=limit,
            carreira_sigla=carreira_sigla,
        )

        for item in resultado["resultados"]:
            if only_errors and item["ok"]:
                continue
            status = "OK" if item["ok"] else "ERRO"
            self.stdout.write(
                f"[{status}] usuario={item['usuario']} cpf={item.get('cpf', '')} "
                f"salvos={item.get('cursos_salvos', 0)} "
                f"concluidos={item.get('cursos_concluidos', 0)} "
                f"duracao={item['duration_seconds']}s "
                f"mensagem={item['message']}"
            )

        resumo = {
            "total_processados": resultado["total_processados"],
            "total_sucesso": resultado["total_sucesso"],
            "total_erro": resultado["total_erro"],
            "total_cursos_salvos": resultado["total_cursos_salvos"],
            "duration_seconds": resultado["duration_seconds"],
        }

        if output_json:
            self.stdout.write(json.dumps(resumo, ensure_ascii=False))
        else:
            self.stdout.write("")
            self.stdout.write("Resumo da sincronização:")
            self.stdout.write(f"- Usuários processados: {resultado['total_processados']}")
            self.stdout.write(f"- Usuários com sucesso: {resultado['total_sucesso']}")
            self.stdout.write(f"- Usuários com erro: {resultado['total_erro']}")
            self.stdout.write(f"- Novos cursos salvos: {resultado['total_cursos_salvos']}")
            self.stdout.write(f"- Duração total: {resultado['duration_seconds']}s")
