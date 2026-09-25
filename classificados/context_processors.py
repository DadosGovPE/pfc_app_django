from .models import Comment


def unread_comments_count(user):
    if not user.is_authenticated:
        return 0
    return (
        Comment.objects.filter(product__creator_id=user.pk, read_at__isnull=True)
        .exclude(author_id=user.pk)
        .count()
    )


def unread_comments(request):
    return {"classificados_unread_comments": unread_comments_count(request.user)}
