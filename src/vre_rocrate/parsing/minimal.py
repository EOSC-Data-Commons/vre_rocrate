import json

from fastapi import Form

from ..models.minimal import MinimalVRERequest


def parse_minimal_vre_form(
    parsed_data: str = Form(..., description="JSON string of MinimalVRERequest")
) -> MinimalVRERequest:
    """Parse and validate MinimalVRERequest from a multipart form field."""
    data = json.loads(parsed_data)
    return MinimalVRERequest.model_validate(data)


__all__ = ["parse_minimal_vre_form"]
