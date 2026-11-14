from fastapi import APIRouter

from app.core.authentication import Authenticated
from app.schemas.responses import Me

router = APIRouter()


@router.get('/me', response_model=Me, tags=['authentication'])
def me(principal: Authenticated):
    return principal.user
