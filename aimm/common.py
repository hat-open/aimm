from hat import json
from pathlib import Path
import hat.monitor.common
import logging
import typing


mlog = logging.getLogger(__name__)


package_path: Path = Path(__file__).parent
"""Package file system path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    hat.monitor.common.json_schema_repo,
    json.SchemaRepository.from_json(package_path / "json_schema_repo.json"),
)
"""JSON schema repository"""


JSON = typing.Union[
    None, bool, int, float, str, typing.List["JSON"], typing.Dict[str, "JSON"]
]
"""JSON serializable data"""
