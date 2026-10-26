from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from framewise.workers.models import installer

router = APIRouter(prefix="/api")


class Consent(BaseModel):
    approve_download: bool = False


@router.post("/models/install")
def install(body: Consent):
    if not body.approve_download:
        raise HTTPException(
            422, "Explicit approval is required to download approximately 350 MB of model weights"
        )
    try:
        return installer.start()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
