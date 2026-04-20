"""
engines/field_map.mojo — Instant data field mapping using FieldMapper.

Input:
  {
    "engine_type": "field_map",
    "data": {"REVENUE": [120000, 85000, 200000], "COST": [70000, 60000, 120000]},
    "engine": "auto"          // optional: engine recommendation
  }

Output:
  {
    "variables": [...],
    "objective_function": "REVENUE - COST",
    "engine": "monte_carlo",
    "field_count": 2,
    "field_analysis": {
      "REVENUE": {"polarity": 1, "distribution": "lognormal", "unit": "currency", "confidence": 0.9},
      ...
    }
  }

Uses field_mapper.mojo for zero-Python polarity detection and distribution inference.
"""

from field_mapper import (
    map_fields,
    build_objective_function,
    build_variables_json,
    FieldMapping,
)
from json.parser import json_get_string, json_get_object, json_get_float


fn run_field_map(raw: String) raises -> String:
    """
    Map arbitrary data fields to simulation variables using FieldMapper.

    Routes:
    - "data" key: JSON object where values are scalar, {low,high}, or arrays
    - Calls map_fields() for polarity + distribution detection
    - Builds canonical variables JSON and objective function
    - Returns complete field analysis
    """
    # Extract the "data" sub-object
    var data_json = json_get_object(raw, "data")
    if len(data_json) == 0:
        return '{"error":"field_map requires a data object","example":{"engine_type":"field_map","data":{"revenue":[100,200],"cost":[50,80]}}}'

    # Run field mapper
    var mappings = map_fields(data_json)
    var n = len(mappings)

    if n == 0:
        return '{"error":"no mappable numeric fields found in data","variables":[],"objective_function":""}'

    # Build output
    var variables_json = build_variables_json(mappings)
    var obj_fn = build_objective_function(mappings)

    # Build field_analysis JSON
    var field_analysis = String("{")
    for i in range(n):
        if i > 0:
            field_analysis += ","
        var m = mappings[i].copy()
        field_analysis += '"' + m.original_name + '":{'
        field_analysis += '"polarity":' + String(m.polarity) + ','
        field_analysis += '"distribution":"' + m.suggested_distribution + '",'
        field_analysis += '"params":' + m.distribution_params + ','
        field_analysis += '"unit":"' + m.unit_hint + '",'
        field_analysis += '"confidence":' + String(m.confidence)
        field_analysis += "}"
    field_analysis += "}"

    # Auto engine selection heuristic (mirrors engine_selector.py)
    var engine = String("monte_carlo")
    if n >= 6:
        engine = "lhs"

    var result = String('{"variables":')
    result += variables_json
    result += String(',"objective_function":"')
    result += obj_fn
    result += String('","engine":"')
    result += engine
    result += String('","field_count":')
    result += String(n)
    result += String(',"field_analysis":')
    result += field_analysis
    result += String("}")

    return result
