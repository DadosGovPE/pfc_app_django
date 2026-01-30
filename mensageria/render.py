import re

TAG_PATTERN = re.compile(r"\[([a-z][a-z0-9_]*)\]")

BLOCKED_ATTRS = {
    "__class__",
    "__dict__",
    "__getattribute__",
    "__globals__",
    "__subclasses__",
    "__mro__",
    "__init__",
    "__call__",
    "__code__",
    "__closure__",
    "__func__",
}


def safe_getattr(obj, attr: str):
    if "__" in attr or attr in BLOCKED_ATTRS or attr.startswith("_"):
        raise AttributeError("Atributo bloqueado.")
    return getattr(obj, attr)


def resolve_path(root_obj, path: str, allow_callables: bool = False):
    cur = root_obj
    for part in path.split("."):
        part = part.strip()
        if not part:
            continue
        if cur is None:
            return None
        cur = safe_getattr(cur, part)
        if allow_callables and callable(cur):
            cur = cur()
    return cur


def render_text(text: str, tags_by_name: dict, context: dict) -> str:
    def repl(match):
        tag_name = match.group(1)
        tag = tags_by_name.get(tag_name)
        if not tag or not tag.ativa:
            return match.group(0)

        root = context.get(tag.contexto_alias)
        if root is None:
            return tag.padrao or ""

        try:
            value = resolve_path(root, tag.path, allow_callables=False)
        except Exception:
            return tag.padrao or ""

        if value is None:
            return tag.padrao or ""

        return str(value)

    return TAG_PATTERN.sub(repl, text)


def render_template(template, context: dict, tags_queryset):
    tags_by_name = {t.nome: t for t in tags_queryset}
    return {
        "assunto": render_text(template.assunto, tags_by_name, context),
        "corpo": render_text(template.corpo, tags_by_name, context),
    }
