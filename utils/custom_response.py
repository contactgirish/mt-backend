from fastapi.responses import ORJSONResponse
from typing import Any

class CustomJSONResponse(ORJSONResponse):
    def render(self, content: Any) -> bytes:
        if isinstance(content, dict) and (
            "statusCode" not in content and
            "status" not in content and
            "message" not in content and
            "data" not in content
        ):
            wrapped = {
                "statusCode": 200,
                "status": True,
                "message": "Success",
                "data": content
            }
            return super().render(wrapped)
        return super().render(content)
