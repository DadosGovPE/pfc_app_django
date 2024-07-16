# Generated by Django 4.2.4 on 2024-07-16 03:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pfc_app', '0074_ajustespesquisa_pesquisacursospriorizados_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='cursopriorizado',
            options={'ordering': ['-mes_competencia', 'nome_sugestao_acao'], 'verbose_name_plural': 'cursos priorizados'},
        ),
        migrations.AlterField(
            model_name='curso',
            name='nome_curso',
            field=models.CharField(db_index=True, max_length=400),
        ),
        migrations.AlterField(
            model_name='curso',
            name='turma',
            field=models.CharField(choices=[('TURMA1', 'TURMA 1'), ('TURMA2', 'TURMA 2'), ('TURMA3', 'TURMA 3'), ('TURMA4', 'TURMA 4'), ('TURMA5', 'TURMA 5'), ('TURMA6', 'TURMA 6'), ('TURMA7', 'TURMA 7'), ('TURMA8', 'TURMA 8'), ('TURMA9', 'TURMA 9'), ('TURMA10', 'TURMA 10')], default='TURMA1', max_length=10),
        ),
        migrations.AddIndex(
            model_name='inscricao',
            index=models.Index(fields=['curso', 'participante'], name='pfc_app_ins_curso_i_8a0d77_idx'),
        ),
    ]