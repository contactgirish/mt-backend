from typing import Literal

async def determine_update_type(conn, platform: Literal["google", "apple"], appversion: str) -> str:
    version_query = "SELECT * FROM mt_config LIMIT 1"
    config = await conn.fetchrow(version_query)
    if not config:
        raise Exception("Version config not found in monk_config")

    def version_tuple(v):
        return tuple(map(int, v.split(".")))

    app_v = version_tuple(appversion)

    if platform == "google":
        min_v = version_tuple(config["min_supported_version_android"])
        latest_v = version_tuple(config["latest_version_android"])
    else:
        min_v = version_tuple(config["min_supported_version_ios"])
        latest_v = version_tuple(config["latest_version_ios"])

    if app_v < min_v:
        return "ForceUpdate"
    elif app_v < latest_v:
        return "NormalUpdate"
    return "None"