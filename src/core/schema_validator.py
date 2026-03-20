"""Validation d'un document narratif selon le schéma JSON officiel."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMAS_DIR = Path(__file__).resolve().parents[2] / "schemas"
DEFAULT_SCHEMA_PATH = SCHEMAS_DIR / "narrative.v1.schema.json"
ENRICHED_SCHEMA_PATH = SCHEMAS_DIR / "narrative.enriched.v1.schema.json"


class NarrativeValidationError(ValueError):
    """Erreur de validation d'un document narratif."""


def load_narrative_schema(schema_path: str | Path = DEFAULT_SCHEMA_PATH) -> dict[str, Any]:
    """Charge un schéma narratif depuis le dossier `schemas/`."""
    source = Path(schema_path)
    return json.loads(source.read_text(encoding="utf-8"))


def validate_narrative_document(
    document: dict[str, Any],
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> None:
    """Valide un document narratif, lève `NarrativeValidationError` en cas d'échec."""
    schema = load_narrative_schema(schema_path=schema_path)
    _validate(document, schema, path="$")


def validate_narrative_file(
    path: str | Path,
    schema_path: str | Path = DEFAULT_SCHEMA_PATH,
) -> dict[str, Any]:
    """Charge et valide un fichier JSON narratif."""
    source = Path(path)
    document = json.loads(source.read_text(encoding="utf-8"))
    validate_narrative_document(document, schema_path=schema_path)
    return document


def _validate(value: Any, schema: dict[str, Any], path: str) -> None:
    expected_type = schema.get("type")
    if expected_type is not None:
        _validate_type(value, expected_type, path)

    if "const" in schema and value != schema["const"]:
        raise NarrativeValidationError(
            f"{path}: valeur attendue {schema['const']!r}, valeur reçue {value!r}."
        )

    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        raise NarrativeValidationError(
            f"{path}: longueur minimale attendue {schema['minLength']}, valeur reçue {len(value)}."
        )


    if "maxLength" in schema and isinstance(value, str) and len(value) > schema["maxLength"]:
        raise NarrativeValidationError(
            f"{path}: longueur maximale attendue {schema['maxLength']}, valeur reçue {len(value)}."
        )

    if "enum" in schema and value not in schema["enum"]:
        raise NarrativeValidationError(
            f"{path}: valeur attendue dans {schema['enum']!r}, valeur reçue {value!r}."
        )

    if "pattern" in schema and isinstance(value, str) and re.match(schema["pattern"], value) is None:
        raise NarrativeValidationError(
            f"{path}: format invalide, motif attendu {schema['pattern']!r}."
        )
    if "minimum" in schema and isinstance(value, (int, float)) and value < schema["minimum"]:
        raise NarrativeValidationError(
            f"{path}: minimum attendu {schema['minimum']}, valeur reçue {value}."
        )

    if "maximum" in schema and isinstance(value, (int, float)) and value > schema["maximum"]:
        raise NarrativeValidationError(
            f"{path}: maximum attendu {schema['maximum']}, valeur reçue {value}."
        )

    if "exclusiveMinimum" in schema and isinstance(value, (int, float)) and value <= schema["exclusiveMinimum"]:
        raise NarrativeValidationError(
            f"{path}: strictement supérieur à {schema['exclusiveMinimum']} attendu, valeur reçue {value}."
        )

    if isinstance(value, dict):
        _validate_object(value, schema, path)
    elif isinstance(value, list):
        _validate_array(value, schema, path)


def _validate_type(value: Any, expected_type: str, path: str) -> None:
    type_checks = {
        "object": lambda item: isinstance(item, dict),
        "array": lambda item: isinstance(item, list),
        "string": lambda item: isinstance(item, str),
        "boolean": lambda item: isinstance(item, bool),
        "integer": lambda item: isinstance(item, int) and not isinstance(item, bool),
        "number": lambda item: (isinstance(item, (int, float)) and not isinstance(item, bool)),
    }

    checker = type_checks.get(expected_type)
    if checker is None:
        raise NarrativeValidationError(f"{path}: type JSON Schema non supporté: {expected_type!r}.")

    if not checker(value):
        raise NarrativeValidationError(f"{path}: type attendu {expected_type}, valeur reçue {type(value).__name__}.")


def _validate_object(value: dict[str, Any], schema: dict[str, Any], path: str) -> None:
    required_fields = schema.get("required", [])
    for field in required_fields:
        if field not in value:
            raise NarrativeValidationError(f"{path}: champ obligatoire manquant '{field}'.")

    properties = schema.get("properties", {})
    additional_properties = schema.get("additionalProperties", True)

    if additional_properties is False:
        unknown_keys = sorted(set(value) - set(properties))
        if unknown_keys:
            raise NarrativeValidationError(
                f"{path}: propriétés non autorisées: {', '.join(unknown_keys)}."
            )

    for key, child_schema in properties.items():
        if key in value:
            _validate(value[key], child_schema, path=f"{path}.{key}")


def _validate_array(value: list[Any], schema: dict[str, Any], path: str) -> None:
    if "minItems" in schema and len(value) < schema["minItems"]:
        raise NarrativeValidationError(
            f"{path}: nombre minimum d'éléments attendu {schema['minItems']}, reçu {len(value)}."
        )

    if "maxItems" in schema and len(value) > schema["maxItems"]:
        raise NarrativeValidationError(
            f"{path}: nombre maximum d'éléments attendu {schema['maxItems']}, reçu {len(value)}."
        )

    item_schema = schema.get("items")
    if item_schema:
        for index, item in enumerate(value):
            _validate(item, item_schema, path=f"{path}[{index}]")
