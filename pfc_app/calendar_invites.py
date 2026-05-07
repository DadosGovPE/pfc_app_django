import re
from datetime import datetime, time, timedelta
from email.utils import parseaddr
from uuid import uuid5, NAMESPACE_URL

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone


TIME_RE = re.compile(r"\b([01]?\d|2[0-3])(?::|h)?([0-5]\d)?\b")


def _escape_ics_text(value):
    if not value:
        return ""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


def _fold_ics_line(line):
    # RFC 5545 recommends folding long content lines. Keeping this byte-aware
    # avoids breaking accents in the middle of a UTF-8 sequence.
    encoded = line.encode("utf-8")
    if len(encoded) <= 75:
        return line

    parts = []
    current = ""
    current_len = 0
    for char in line:
        char_len = len(char.encode("utf-8"))
        limit = 75 if not parts else 74
        if current and current_len + char_len > limit:
            parts.append(current)
            current = char
            current_len = char_len
        else:
            current += char
            current_len += char_len
    if current:
        parts.append(current)
    return "\r\n ".join(parts)


def _format_datetime(value):
    value = timezone.localtime(value)
    return value.strftime("%Y%m%dT%H%M%S")


def _parse_course_times(horario):
    if not horario:
        return None, None

    matches = TIME_RE.findall(horario)
    if not matches:
        return None, None

    parsed = []
    for hour, minute in matches[:2]:
        parsed.append(time(int(hour), int(minute or 0)))

    start_time = parsed[0]
    end_time = parsed[1] if len(parsed) > 1 else None
    if end_time and end_time <= start_time:
        end_time = None
    return start_time, end_time


def _event_dates(curso):
    end_date = curso.data_termino or curso.data_inicio
    start_time, end_time = _parse_course_times(curso.horario)

    if not start_time:
        return {
            "all_day": True,
            "start": curso.data_inicio.strftime("%Y%m%d"),
            "end": (end_date + timedelta(days=1)).strftime("%Y%m%d"),
        }

    if not end_time:
        end_time = (
            datetime.combine(curso.data_inicio, start_time) + timedelta(hours=1)
        ).time()

    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(curso.data_inicio, start_time), tz)
    end = timezone.make_aware(datetime.combine(end_date, end_time), tz)
    if end <= start:
        end = start + timedelta(hours=1)

    return {"all_day": False, "start": start, "end": end}


def _build_description(curso):
    parts = []
    if curso.descricao:
        parts.append(curso.descricao)
    if curso.ementa_curso:
        parts.append(f"Ementa: {curso.ementa_curso}")
    if curso.horario:
        parts.append(f"Horario informado: {curso.horario}")
    if curso.observacao:
        parts.append(f"Observacao: {curso.observacao}")
    return "\n\n".join(parts)


def build_course_invite_ics(inscricao):
    curso = inscricao.curso
    participante = inscricao.participante
    dates = _event_dates(curso)
    uid = uuid5(
        NAMESPACE_URL,
        f"pfc-app:inscricao:{inscricao.pk}:curso:{curso.pk}:user:{participante.pk}",
    )
    from_email = parseaddr(settings.DEFAULT_FROM_EMAIL)[1] or settings.DEFAULT_FROM_EMAIL
    organizer_name = getattr(settings, "PFC_CALENDAR_ORGANIZER_NAME", "PFC SEPLAG")
    location = getattr(settings, "PFC_CALENDAR_DEFAULT_LOCATION", "")
    sequence = getattr(settings, "PFC_CALENDAR_SEQUENCE", 0)

    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//PFC SEPLAG//Inscricoes//PT-BR",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:{uid}@pfc-app",
        f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
        f"SEQUENCE:{sequence}",
        f"SUMMARY:{_escape_ics_text(curso.nome_formatado)}",
        f"DESCRIPTION:{_escape_ics_text(_build_description(curso))}",
        f"LOCATION:{_escape_ics_text(location)}",
        f"ORGANIZER;CN={_escape_ics_text(organizer_name)}:mailto:{from_email}",
        (
            f"ATTENDEE;CN={_escape_ics_text(participante.nome)};ROLE=REQ-PARTICIPANT;"
            f"PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{participante.email}"
        ),
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",
    ]

    if dates["all_day"]:
        lines.extend(
            [
                f"DTSTART;VALUE=DATE:{dates['start']}",
                f"DTEND;VALUE=DATE:{dates['end']}",
            ]
        )
    else:
        tzid = settings.TIME_ZONE
        lines.extend(
            [
                f"DTSTART;TZID={tzid}:{_format_datetime(dates['start'])}",
                f"DTEND;TZID={tzid}:{_format_datetime(dates['end'])}",
            ]
        )

    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    return "\r\n".join(_fold_ics_line(line) for line in lines) + "\r\n"


def send_course_calendar_invite(inscricao):
    participante = inscricao.participante
    if not participante.email:
        return False

    curso = inscricao.curso
    subject = f"Convite de agenda: {curso.nome_formatado}"
    body = (
        f"Ola, {participante.nome}.\n\n"
        f"Sua inscricao em \"{curso.nome_formatado}\" foi realizada no PFC.\n"
        "Segue um convite de calendario para adicionar o curso a sua agenda Google.\n"
    )

    email = EmailMultiAlternatives(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[participante.email],
    )
    ics_content = build_course_invite_ics(inscricao)
    calendar_mimetype = 'text/calendar; method=REQUEST; charset="UTF-8"'
    email.attach_alternative(ics_content, calendar_mimetype)
    email.attach(
        filename="convite-pfc.ics",
        content=ics_content,
        mimetype=calendar_mimetype,
    )
    email.extra_headers = {"Content-class": "urn:content-classes:calendarmessage"}
    email.send(fail_silently=False)
    return True
