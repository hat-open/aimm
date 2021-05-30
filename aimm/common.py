from hat import json
from pathlib import Path


package_path: Path = Path(__file__).parent
"""Package file system path"""

json_schema_repo: json.SchemaRepository = json.SchemaRepository(
    json.json_schema_repo,
    json.SchemaRepository.from_json(package_path / 'json_schema_repo.json'))
"""JSON schema repository"""
