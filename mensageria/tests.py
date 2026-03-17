from django.test import SimpleTestCase

from mensageria.render import build_email_bodies, render_text


class MensageriaRenderTests(SimpleTestCase):
    def test_build_email_bodies_preserva_texto_puro(self):
        corpo = "Ola [user_nome]\nAcesse https://exemplo.com"

        plain_body, html_body = build_email_bodies(corpo)

        self.assertEqual(plain_body, corpo)
        self.assertEqual(html_body, corpo)

    def test_build_email_bodies_gera_fallback_texto_para_html(self):
        corpo = 'Clique em <a href="https://exemplo.com/curso">inscrever-se</a>'

        plain_body, html_body = build_email_bodies(corpo)

        self.assertEqual(plain_body, "Clique em inscrever-se")
        self.assertEqual(html_body, corpo)

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
