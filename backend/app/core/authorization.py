from fastapi import HTTPException

from app.core.authentication import Authenticated, Principal


def require_admin(principal: Authenticated) -> Principal:
    if principal.user.role != 'admin':
        raise HTTPException(403, 'Admin role required')
    return principal


def can_retrieve_document(role: str, document: dict) -> bool:
    return (role in ('student', 'admin') and document.get('review_status') == 'approved'
            and (document.get('visibility') == 'public'
                 or (role == 'admin' and document.get('visibility') == 'restricted')))
