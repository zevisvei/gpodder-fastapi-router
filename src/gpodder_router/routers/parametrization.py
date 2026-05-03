from __future__ import annotations

from fastapi import APIRouter

from gpodder_router.deps import ConfigDep
from gpodder_router.schemas.parametrization import ClientConfiguration, _UrlBlock

router = APIRouter(tags=["Client Parametrization"])


@router.get("/clientconfig.json", response_model=ClientConfiguration, response_model_by_alias=True)
async def get_client_configuration(config: ConfigDep) -> ClientConfiguration:
    return ClientConfiguration(
        mygpo=_UrlBlock(baseurl=config.base_url),
        mygpo_feedservice=_UrlBlock(baseurl=config.feedservice_url),
        update_timeout=config.update_timeout,
    )
