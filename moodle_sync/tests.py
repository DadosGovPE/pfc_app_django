from unittest.mock import patch

from django.test import SimpleTestCase

from moodle_sync.services import obter_data_conclusao_atividades_curso, obter_data_conclusao_curso


class MoodleConclusaoCursoTests(SimpleTestCase):
    @patch("moodle_sync.services.moodle_api_get")
    def test_obter_data_conclusao_curso_prioriza_status_do_curso(self, moodle_api_get_mock):
        moodle_api_get_mock.return_value = {
            "completionstatus": {
                "completions": [
                    {"complete": True, "timecompleted": 1711929600},
                    {"complete": False, "timecompleted": 1711843200},
                ]
            }
        }

        data = obter_data_conclusao_curso(userid=10, courseid=20)

        self.assertIsNotNone(data)
        self.assertEqual(int(data.timestamp()), 1711929600)
        moodle_api_get_mock.assert_called_once_with(
            "core_completion_get_course_completion_status",
            userid=10,
            courseid=20,
        )

    @patch("moodle_sync.services.moodle_api_get")
    def test_obter_data_conclusao_curso_usa_atividades_como_fallback(self, moodle_api_get_mock):
        moodle_api_get_mock.side_effect = [
            {"completionstatus": {"completions": []}},
            {
                "statuses": [
                    {"timecompleted": 1711843200},
                    {"timecompleted": 1712016000},
                    {"timecompleted": None},
                ]
            },
        ]

        data = obter_data_conclusao_curso(userid=10, courseid=20)

        self.assertIsNotNone(data)
        self.assertEqual(int(data.timestamp()), 1712016000)
        self.assertEqual(moodle_api_get_mock.call_count, 2)

    @patch("moodle_sync.services.moodle_api_get")
    def test_obter_data_conclusao_curso_usa_atividades_quando_curso_nao_tem_criterios(self, moodle_api_get_mock):
        moodle_api_get_mock.side_effect = [
            ValueError("Não existem critérios de conclusão para este curso"),
            {
                "statuses": [
                    {"timecompleted": 1712102400},
                ]
            },
        ]

        data = obter_data_conclusao_curso(userid=10, courseid=20)

        self.assertIsNotNone(data)
        self.assertEqual(int(data.timestamp()), 1712102400)
        self.assertEqual(moodle_api_get_mock.call_count, 2)

    @patch("moodle_sync.services.moodle_api_get")
    def test_obter_data_conclusao_atividades_curso_retorna_none_sem_datas(self, moodle_api_get_mock):
        moodle_api_get_mock.return_value = {
            "statuses": [
                {"timecompleted": None},
                {},
            ]
        }

        data = obter_data_conclusao_atividades_curso(userid=10, courseid=20)

        self.assertIsNone(data)
