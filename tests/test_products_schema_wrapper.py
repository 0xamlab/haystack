from apps.api_server.routers import products
from apps.api_server.schemas import products as product_schemas


def test_products_router_reexports_schema_models() -> None:
    assert products.DecisionInput is product_schemas.DecisionInput
    assert products.DecisionRequest is product_schemas.DecisionRequest
    assert products.DecisionResponse is product_schemas.DecisionResponse
    assert products.AgentStep is product_schemas.AgentStep
    assert products.AgentRunRequest is product_schemas.AgentRunRequest
    assert products.AgentRunResponse is product_schemas.AgentRunResponse
    assert products.OptimizeVariable is product_schemas.OptimizeVariable
    assert products.OptimizeConstraint is product_schemas.OptimizeConstraint
    assert products.OptimizeRequest is product_schemas.OptimizeRequest
    assert products.OptimizeResponse is product_schemas.OptimizeResponse
    assert products.RetrieveDocument is product_schemas.RetrieveDocument
    assert products.RetrieveRequest is product_schemas.RetrieveRequest
    assert products.RetrieveResult is product_schemas.RetrieveResult
    assert products.RetrieveResponse is product_schemas.RetrieveResponse
    assert products.ForecastRequest is product_schemas.ForecastRequest
    assert products.ForecastPeriod is product_schemas.ForecastPeriod
    assert products.ForecastResponse is product_schemas.ForecastResponse
