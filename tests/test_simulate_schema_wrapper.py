from apps.api_server.schemas import simulate, simulate_model_configs


def test_simulate_schema_reexports_model_config_family() -> None:
    assert simulate.CorrelationSpec is simulate_model_configs.CorrelationSpec
    assert simulate.ScoringWeights is simulate_model_configs.ScoringWeights
    assert simulate.DecisionNode is simulate_model_configs.DecisionNode
    assert simulate.DecisionTreeConfig is simulate_model_configs.DecisionTreeConfig
    assert simulate.ScenarioItem is simulate_model_configs.ScenarioItem
    assert simulate.BootstrapConfig is simulate_model_configs.BootstrapConfig
    assert simulate.MCMCConfig is simulate_model_configs.MCMCConfig
    assert simulate.ScenarioConfig is simulate_model_configs.ScenarioConfig
    assert simulate.SensitivityConfig is simulate_model_configs.SensitivityConfig
    assert simulate.ImportanceSamplingConfig is simulate_model_configs.ImportanceSamplingConfig
    assert simulate.StochasticParam is simulate_model_configs.StochasticParam
    assert simulate.TimeSeriesConfig is simulate_model_configs.TimeSeriesConfig
