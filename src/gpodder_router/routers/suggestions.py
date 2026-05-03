from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from gpodder_router.deps import authenticate
from gpodder_router.formats import render_generic
from gpodder_router.schemas.common import Format

router = APIRouter(tags=["Suggestions"])


@router.get("/suggestions/{number}.{format}", dependencies=[Depends(authenticate)])
async def suggested_podcasts(
    number: Annotated[int, Path(ge=1, le=1000)],
    format: Annotated[Format, Path()],
    jsonp: Annotated[str | None, Query()] = None,
) -> Response:
    """Self-hosted servers don't compute personalized suggestions; return empty."""
    return render_generic(format, [], jsonp=jsonp)
