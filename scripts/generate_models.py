#!/usr/bin/env python3
"""
Generate Pydantic models from Navirec OpenAPI spec.

Usage:
    uv run python scripts/generate_models.py

This script generates Pydantic models for the Navirec API from the OpenAPI spec.
Only the models needed for the Home Assistant integration are generated.
The generated models are placed in custom_components/navirec/models.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Project root
ROOT = Path(__file__).parent.parent
OPENAPI_SPEC = ROOT / "docs" / "openapi-navirec-1.45.0.json"
OUTPUT_FILE = ROOT / "custom_components" / "navirec" / "models.py"

# Models we need for the integration
REQUIRED_SCHEMAS = {
    # Core models
    "Account",
    "Vehicle",
    "Sensor",
    "VehicleState",
    "Interpretation",  # Full interpretation object with unit, decimal_places, choices, etc.
    # Enums and types used by core models
    "DefaultLanguageEnum",
    "TimezoneEnum",
    "BlankEnum",
    "NullEnum",
    "FuelUsedSource",
    "FuelTypeEnum",
    "Activity2",  # Used by VehicleState.activity
    "Workhour",  # Used by Vehicle.workhours
    # Location types (GeoJSON)
    "Type12",  # Point type enum
    "Location12",  # Used by VehicleState.location
    "Trail",  # Used by VehicleState.trail
    # Interpretation type for Sensor
    "Interpretation1",
}


def extract_required_schemas(spec: dict) -> dict:
    """Extract only the required schemas from the OpenAPI spec."""
    components = spec.get("components", {})
    schemas = components.get("schemas", {})

    # Collect all required schemas and their dependencies
    required = set(REQUIRED_SCHEMAS)
    to_process = list(REQUIRED_SCHEMAS)
    processed = set()

    while to_process:
        schema_name = to_process.pop()
        if schema_name in processed:
            continue
        processed.add(schema_name)

        if schema_name not in schemas:
            continue

        schema = schemas[schema_name]
        deps = find_schema_dependencies(schema)
        for dep in deps:
            if dep not in processed:
                required.add(dep)
                to_process.append(dep)

    # Build filtered spec
    filtered_schemas = {k: v for k, v in schemas.items() if k in required}

    return {
        "openapi": spec.get("openapi", "3.0.3"),
        "info": spec.get("info", {}),
        "paths": {},  # No paths needed for model generation
        "components": {"schemas": filtered_schemas},
    }


def find_schema_dependencies(schema: dict) -> set[str]:
    """Find all schema references in a schema definition."""
    deps = set()

    def search(obj):
        if isinstance(obj, dict):
            if "$ref" in obj:
                ref = obj["$ref"]
                # Extract schema name from #/components/schemas/Name
                if ref.startswith("#/components/schemas/"):
                    deps.add(ref.split("/")[-1])
            for value in obj.values():
                search(value)
        elif isinstance(obj, list):
            for item in obj:
                search(item)

    search(schema)
    return deps


def main() -> int:
    """Generate models from OpenAPI spec."""
    if not OPENAPI_SPEC.exists():
        print(f"Error: OpenAPI spec not found at {OPENAPI_SPEC}")
        return 1

    print(f"Loading OpenAPI spec from {OPENAPI_SPEC}")

    # Load and filter the spec
    with open(OPENAPI_SPEC) as f:
        full_spec = json.load(f)

    filtered_spec = extract_required_schemas(full_spec)
    schema_count = len(filtered_spec["components"]["schemas"])
    print(
        f"Extracted {schema_count} schemas (from {len(full_spec['components']['schemas'])} total)"
    )

    # Write filtered spec to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(filtered_spec, f, indent=2)
        temp_spec = Path(f.name)

    try:
        print(f"Generating models to {OUTPUT_FILE}")

        # Run datamodel-code-generator
        cmd = [
            sys.executable,
            "-m",
            "datamodel_code_generator",
            "--input",
            str(temp_spec),
            "--input-file-type",
            "openapi",
            "--output",
            str(OUTPUT_FILE),
            "--output-model-type",
            "pydantic_v2.BaseModel",
            "--target-python-version",
            "3.13",
            "--use-standard-collections",
            "--use-union-operator",
            # Skip field constraints to be more flexible with API responses
            # "--field-constraints",
            "--ignore-enum-constraints",
            "--collapse-root-models",
            # "--use-annotated",  # decimal validations fail due to pattern=.. values
            # "--use-field-description",  # long descriptions generated inline are unnecessary
            "--use-default",
            "--formatters",
            "ruff-format",
        ]

        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"Error generating models:\n{result.stderr}")
            return 1

        # Add module docstring
        content = OUTPUT_FILE.read_text()
        header = '''"""Auto-generated Pydantic models for Navirec API.

DO NOT EDIT THIS FILE MANUALLY.
Generated from docs/openapi-navirec-1.45.0.json using:
    uv run python scripts/generate_models.py

To regenerate after API spec updates:
    1. Download new OpenAPI spec to docs/
    2. Update OPENAPI_SPEC path in scripts/generate_models.py
    3. Run: uv run python scripts/generate_models.py
"""

'''
        if not content.startswith('"""Auto-generated'):
            content = header + content
            OUTPUT_FILE.write_text(content)

        # Format with ruff
        subprocess.run(
            [sys.executable, "-m", "ruff", "format", str(OUTPUT_FILE)],
            check=False,
            capture_output=True,
        )
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", "--fix", str(OUTPUT_FILE)],
            check=False,
            capture_output=True,
        )

        # Count lines
        lines = len(OUTPUT_FILE.read_text().splitlines())
        print(f"Successfully generated {lines} lines to {OUTPUT_FILE}")
        print("Done!")
        return 0

    finally:
        temp_spec.unlink()


if __name__ == "__main__":
    sys.exit(main())
