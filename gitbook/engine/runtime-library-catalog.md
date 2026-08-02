---
icon: books
description: The full catalog of Algenta runtime-library modules — vision, LLM, ML, tensors, statistics, signal, crypto, and more — callable through /v1/libraries.
---

# Runtime library catalog

The engine ships a compiled runtime library of **631 modules** and **5970 functions** — the low-level building blocks the high-level engines are made of. You can call any one directly with a `module` + `function` name; see [Runtime libraries](runtime-libraries.md) for how to list, check, and execute them.

{% hint style="info" %}
The catalog is **self-describing** — `GET /v1/libraries` returns every module and its exported functions live, and `GET /v1/libraries?q=<term>` filters by name (for example `?q=image` for the vision modules, `?q=llm` for sampling). This page groups the modules so you can see what is available; the endpoint is the authoritative, always-current list.
{% endhint %}

## Flagship domains

A few of the most-used domains, with example modules. **Computer vision** — `image_ops`, `image_features`, `image_similarity`, `image_morphology`, `image_resize`, `image_quality`, `image_regions`, `image_palette`, `document_vision`, `vision_gate`. **LLM** — `llm_sampling`, `vision_attention_scale`. Discover any of them with `GET /v1/libraries?q=image` or `?q=llm`.

## Vision & imaging

12 modules.

| Module | Functions |
| --- | --- |
| `document_vision` | 9 |
| `endocrinology` | 10 |
| `geomorphology` | 12 |
| `image_features` | 11 |
| `image_morphology` | 9 |
| `image_ops` | 11 |
| `image_palette` | 8 |
| `image_quality` | 15 |
| `image_regions` | 6 |
| `image_resize` | 9 |
| `image_similarity` | 8 |
| `vision_gate` | 5 |

## LLM & attention

18 modules.

| Module | Functions |
| --- | --- |
| `attnk.rope` | 6 |
| `bpe_tokenizer` | 10 |
| `causal_inference.propensity` | 5 |
| `embeddings` | 12 |
| `flash_attention` | 10 |
| `kv_cache` | 10 |
| `llm_sampling` | 11 |
| `llmk.contract` | 4 |
| `llmk.generate` | 2 |
| `llmk.residual` | 1 |
| `mlpk.embedding` | 3 |
| `paged_kv_cache` | 10 |
| `propensity` | 9 |
| `sparse_attention` | 10 |
| `text.tokenizer` | 10 |
| `token_bucket` | 11 |
| `transformer_attention` | 11 |
| `transformer_blocks` | 10 |

## Machine learning

42 modules.

| Module | Functions |
| --- | --- |
| `activations` | 10 |
| `bayesian_inference` | 10 |
| `calibration` | 5 |
| `causal_inference.base` | 13 |
| `causal_inference.dag` | 6 |
| `causal_inference.estimators` | 5 |
| `causal_inference.panel` | 2 |
| `causal_inference.sensitivity` | 7 |
| `causal_inference.uplift` | 2 |
| `config.toml_parser` | 5 |
| `config.yaml_parser` | 5 |
| `constraint` | 8 |
| `decision_ml_fusion` | 10 |
| `gemm.quantized` | 4 |
| `gradient_descent` | 10 |
| `inference.assume` | 5 |
| `inference.core` | 18 |
| `inference.glm` | 3 |
| `inference.multiplicity` | 5 |
| `inference.power` | 5 |
| `inference.resample` | 3 |
| `inference.robust` | 3 |
| `inference_cost_latency` | 11 |
| `inference_engine` | 10 |
| `inference_security` | 10 |
| `latency_optimizer` | 10 |
| `loss_functions` | 11 |
| `lossk.contract` | 8 |
| `lossk.cross_entropy` | 5 |
| `ml_metrics_extended` | 10 |
| `mlpk.activation` | 7 |
| `nn_layers` | 11 |
| `normalization_layers` | 10 |
| `normk.layernorm` | 4 |
| `optimization_constrained` | 8 |
| `optimizer_full` | 10 |
| `quantization` | 10 |
| `quantization_stack` | 10 |
| `seq2_trainer` | 10 |
| `seq_training` | 4 |
| `state_space_models` | 10 |
| `training_stability` | 10 |

## Tensors & linear algebra

19 modules.

| Module | Functions |
| --- | --- |
| `eigen_full` | 2 |
| `gpu_kernels` | 10 |
| `linalg` | 16 |
| `linalg_ext` | 8 |
| `matrix_decomp` | 11 |
| `matrix_ops` | 12 |
| `tensor` | 29 |
| `tensor2d` | 11 |
| `tensor_ops` | 10 |
| `tensorx.contract` | 6 |
| `tensorx.dtype` | 14 |
| `tensorx.pack` | 12 |
| `time_series_decompose` | 9 |
| `vector_kernels.batch_ranker` | 1 |
| `vector_kernels.dot` | 4 |
| `vector_kernels.ranker` | 1 |
| `vector_kernels.repo_ranker` | 1 |
| `vector_kernels.table` | 4 |
| `vector_kernels.test_table` | 1 |

## Statistics & probability

21 modules.

| Module | Functions |
| --- | --- |
| `ab_testing` | 10 |
| `bayesian` | 10 |
| `degradation_state` | 13 |
| `distribution_fit` | 10 |
| `distributions` | 25 |
| `electrostatics` | 10 |
| `forecasting.interval` | 3 |
| `hypothesis` | 6 |
| `interval` | 13 |
| `ml.naive_bayes` | 8 |
| `probability` | 11 |
| `real_estate` | 12 |
| `regression` | 8 |
| `regression_tree` | 8 |
| `sampling` | 6 |
| `scipy_stats_ops` | 10 |
| `stat_tests` | 9 |
| `stateful_runtime` | 10 |
| `stats` | 12 |
| `stats_bootstrap` | 10 |
| `timeseries_stats` | 9 |

## Signal & audio

11 modules.

| Module | Functions |
| --- | --- |
| `acoustics` | 12 |
| `audio` | 10 |
| `fft` | 7 |
| `psychoacoustics` | 10 |
| `signal.dsp` | 10 |
| `signal.filter` | 11 |
| `signal_processing` | 10 |
| `spectral` | 10 |
| `spectroscopy` | 12 |
| `traffic_signal` | 12 |
| `wavelet` | 10 |

## Cryptography & hashing

10 modules.

| Module | Functions |
| --- | --- |
| `crypto.aes_sbox` | 8 |
| `crypto.base64` | 4 |
| `crypto.chacha20` | 8 |
| `crypto.crc32` | 3 |
| `crypto.hash_chain` | 9 |
| `crypto.hmac` | 2 |
| `crypto.pbkdf2` | 7 |
| `crypto.uuid` | 2 |
| `feature_hashing` | 4 |
| `perceptual_hash` | 8 |

## Text & language

6 modules.

| Module | Functions |
| --- | --- |
| `string_distance` | 10 |
| `text.column_scorer` | 4 |
| `text.fuzzy` | 7 |
| `text.regex` | 7 |
| `text.string_utils` | 16 |
| `textile` | 12 |

## Graph & automata

23 modules.

| Module | Functions |
| --- | --- |
| `autograd_graph` | 10 |
| `cartography` | 12 |
| `cellular_automata` | 10 |
| `chromatography` | 10 |
| `crystallography` | 12 |
| `demographics` | 12 |
| `graph.algorithms` | 8 |
| `graph.weighted` | 9 |
| `graph_algorithms` | 10 |
| `graph_analytics.adjacency` | 35 |
| `graph_analytics.centrality` | 9 |
| `graph_analytics.community` | 19 |
| `graph_analytics.temporal` | 16 |
| `graph_compiler` | 10 |
| `graph_decision` | 10 |
| `heap` | 13 |
| `oceanography` | 10 |
| `rag_retrieval` | 10 |
| `retrieval.fuse` | 2 |
| `retrieval.score` | 8 |
| `stratigraphy` | 10 |
| `topology` | 10 |
| `trie` | 7 |

## Serialization & data

17 modules.

| Module | Functions |
| --- | --- |
| `compression.delta` | 11 |
| `compression.huffman` | 7 |
| `compression.lz77` | 6 |
| `compression.rle` | 5 |
| `data.csv_parser` | 4 |
| `data_feedback_loop` | 10 |
| `data_pipeline` | 10 |
| `data_quality.contract` | 18 |
| `data_quality.duplicates` | 4 |
| `data_quality.expect` | 6 |
| `data_quality.leakage` | 3 |
| `data_quality.profile` | 5 |
| `json.parser` | 15 |
| `json.writer` | 12 |
| `model_serialization` | 10 |
| `serialization.msgpack` | 10 |
| `serialization_io` | 3 |

## Bits, numbers & time

7 modules.

| Module | Functions |
| --- | --- |
| `agent_runtime` | 10 |
| `bitops` | 13 |
| `datetime` | 14 |
| `discrete_event.calendar` | 4 |
| `number_theory` | 12 |
| `sentiment` | 10 |
| `time_zone` | 10 |

## Geometry & spatial

13 modules.

| Module | Functions |
| --- | --- |
| `biogeochemistry` | 10 |
| `geochemistry` | 10 |
| `geodesy` | 10 |
| `geometry` | 9 |
| `geophysics` | 10 |
| `geospatial.contract` | 19 |
| `geospatial.frame` | 8 |
| `geospatial.index` | 6 |
| `geospatial.join` | 4 |
| `geospatial.mapmatch` | 2 |
| `geospatial.polygon` | 6 |
| `geotechnical` | 12 |
| `hydrogeology` | 10 |

## Networking & systems

15 modules.

| Module | Functions |
| --- | --- |
| `compiler_theory` | 12 |
| `epigenetics` | 10 |
| `genetic` | 8 |
| `kinetics` | 10 |
| `magnetism` | 10 |
| `memory_system` | 10 |
| `net.url` | 7 |
| `network_analysis` | 11 |
| `network_protocol` | 11 |
| `paleomagnetism` | 13 |
| `petri_net` | 13 |
| `pharmacokinetics` | 12 |
| `population_genetics` | 10 |
| `social_network` | 9 |
| `toxicokinetics` | 10 |

## Finance & business

4 modules.

| Module | Functions |
| --- | --- |
| `accounting` | 12 |
| `finance` | 12 |
| `option_greeks_batch` | 1 |
| `option_pricing` | 10 |

## General & domain modules

413 modules.

| Module | Functions |
| --- | --- |
| `accel.contract` | 6 |
| `accel.device` | 3 |
| `accel.gemm_metal` | 3 |
| `actuarial` | 12 |
| `adhesives` | 12 |
| `aerospace` | 12 |
| `agriculture` | 12 |
| `agronomy` | 10 |
| `allocation` | 10 |
| `anomaly` | 10 |
| `antenna` | 12 |
| `apiculture` | 12 |
| `aquaculture` | 12 |
| `archaeology` | 12 |
| `arima` | 8 |
| `astrobiology` | 10 |
| `astronomy` | 12 |
| `atmospheric_chemistry` | 10 |
| `attnk.backward` | 2 |
| `attnk.contract` | 5 |
| `attnk.flash` | 3 |
| `attnk.mask` | 7 |
| `attnk.sdpa` | 3 |
| `auction` | 11 |
| `autograd_ops` | 10 |
| `automl` | 4 |
| `autonomous_vehicles` | 12 |
| `aviation` | 10 |
| `battery` | 12 |
| `behavioral_economics` | 12 |
| `bioinformatics` | 12 |
| `biomechanics` | 12 |
| `biomedical` | 12 |
| `blockchain` | 12 |
| `bloom_counting` | 9 |
| `boolean_algebra` | 13 |
| `brewing` | 12 |
| `bryology` | 10 |
| `cache` | 8 |
| `cardiology` | 10 |
| `category_theory` | 10 |
| `causal` | 10 |
| `cellular` | 11 |
| `ceramics` | 12 |
| `chaos` | 10 |
| `checksum` | 11 |
| `climate` | 11 |
| `clustering_metrics` | 8 |
| `color` | 11 |
| `color_check` | 16 |
| `color_science` | 12 |
| `column_rank` | 1 |
| `combinatorial` | 10 |
| `combustion` | 12 |
| `composites` | 12 |
| `concrete` | 12 |
| `conformal` | 6 |
| `contest_strategy` | 7 |
| `continuous_batching` | 10 |
| `contrastive_learning` | 10 |
| `control` | 9 |
| `convex` | 9 |
| `copula` | 5 |
| `correlation` | 4 |
| `corrosion` | 12 |
| `cosmology` | 12 |
| `cost_router` | 10 |
| `counter_rng` | 11 |
| `cryogenics` | 12 |
| `cryology` | 10 |
| `cryptanalysis` | 12 |
| `currency` | 12 |
| `cytology` | 10 |
| `cytometry` | 10 |
| `data.dataframe` | 1 |
| `database` | 9 |
| `decision_analysis` | 10 |
| `dendrochronology` | 10 |
| `dendrology` | 12 |
| `dentistry` | 12 |
| `dependency` | 8 |
| `differentiate` | 6 |
| `diffusion_models` | 10 |
| `dimensionality` | 8 |
| `dimensions` | 10 |
| `discrete_event.contract` | 18 |
| `discrete_event.queue_sim` | 5 |
| `discrete_event.replicate` | 2 |
| `discrete_event.resource` | 2 |
| `discrete_event.warmup` | 2 |
| `distillation` | 12 |
| `distributed_collectives` | 10 |
| `document_layout` | 7 |
| `dosimetry` | 10 |
| `drones` | 12 |
| `earth` | 10 |
| `ecohydrology` | 10 |
| `ecology` | 12 |
| `economic_indicators` | 12 |
| `ecophysiology` | 10 |
| `election` | 8 |
| `electrical` | 14 |
| `electrochemistry` | 10 |
| `elevator` | 12 |
| `encoding` | 7 |
| `encryption_modes` | 12 |
| `ensembles` | 4 |
| `entomology` | 12 |
| `env` | 5 |
| `epidemiology` | 10 |
| `ergonomics` | 12 |
| `esrnn.bias_correction` | 2 |
| `esrnn.global_residual` | 7 |
| `esrnn.per_frequency` | 2 |
| `etiology` | 10 |
| `evaluation.binning` | 4 |
| `evaluation.contract` | 13 |
| `evaluation.gates` | 3 |
| `evaluation.resample` | 3 |
| `evaluation.scores` | 6 |
| `evaluation_feedback` | 10 |
| `evolutionary_search` | 7 |
| `exactnum.eft` | 24 |
| `exactnum.lstsq` | 9 |
| `execution_planner` | 10 |
| `explainability` | 4 |
| `fault_tolerance` | 10 |
| `feature_engineering` | 10 |
| `feature_selection` | 9 |
| `fermentation` | 10 |
| `filepath.pathlib` | 8 |
| `fire_safety` | 12 |
| `fisheries` | 12 |
| `fluid` | 12 |
| `food_science` | 12 |
| `forecast_metrics` | 10 |
| `forecasting.backtest` | 4 |
| `forecasting.bagging` | 3 |
| `forecasting.contract` | 18 |
| `forecasting.fitted` | 7 |
| `forecasting.hierarchy` | 5 |
| `forecasting.intermittent` | 4 |
| `forecasting.origin_select` | 3 |
| `forecasting.point` | 8 |
| `forecasting.pool` | 5 |
| `forecasting.select` | 2 |
| `forensics` | 12 |
| `formal_logic` | 14 |
| `fused_kernels` | 10 |
| `fuzzy_logic` | 11 |
| `game_physics` | 12 |
| `game_theory` | 8 |
| `gaussian_process` | 5 |
| `gbdt` | 4 |
| `gemm.blocked` | 4 |
| `gemm.contract` | 5 |
| `generation_loop` | 10 |
| `genomics` | 10 |
| `glaciology` | 10 |
| `greenhouse` | 12 |
| `hematology` | 10 |
| `hmm` | 4 |
| `horticulture` | 10 |
| `hvac` | 12 |
| `hybrid_reasoning` | 10 |
| `hydraulics` | 12 |
| `hydrology` | 12 |
| `hydrometeorology` | 10 |
| `hydroponics` | 12 |
| `imbalance` | 5 |
| `immunology` | 10 |
| `information_theory` | 10 |
| `insurance` | 12 |
| `integrate` | 6 |
| `interpolate` | 6 |
| `inventory` | 11 |
| `kalman` | 11 |
| `laundry` | 12 |
| `lidar` | 12 |
| `lidar_mapping` | 10 |
| `limnochemistry` | 11 |
| `limnology` | 10 |
| `linear_models` | 4 |
| `linear_programming` | 8 |
| `linguistics` | 12 |
| `logging.logger` | 1 |
| `logic_circuit` | 13 |
| `logistics` | 12 |
| `lora_adapters` | 10 |
| `lottery` | 12 |
| `marine` | 12 |
| `materials` | 12 |
| `metabolomics` | 10 |
| `metallurgy` | 12 |
| `meteorology` | 10 |
| `metrics_agg` | 12 |
| `microbiology` | 10 |
| `mineralogy` | 10 |
| `mining` | 12 |
| `mixture_models` | 5 |
| `mixture_of_experts` | 10 |
| `ml.classifiers` | 7 |
| `ml.clustering` | 4 |
| `ml.knn` | 10 |
| `ml.metrics` | 7 |
| `ml.preprocessing` | 6 |
| `ml.random_forest` | 8 |
| `mlpk.contract` | 7 |
| `model_abi` | 10 |
| `model_compare` | 4 |
| `model_interop` | 10 |
| `model_parallel` | 10 |
| `model_router` | 10 |
| `model_selection` | 5 |
| `moe_production` | 10 |
| `moe_routing` | 10 |
| `multi_objective` | 7 |
| `multimodal` | 10 |
| `museum` | 12 |
| `music_theory` | 12 |
| `mycology` | 10 |
| `nanotechnology` | 12 |
| `nephrology` | 10 |
| `neuropharmacology` | 10 |
| `neurophysics` | 10 |
| `nlp` | 11 |
| `normk.contract` | 5 |
| `normk.rmsnorm` | 4 |
| `nuclear` | 12 |
| `numerical_stability` | 12 |
| `numismatics` | 12 |
| `numpy_ops` | 10 |
| `nutrition` | 12 |
| `observability` | 10 |
| `ode` | 8 |
| `online_learning` | 10 |
| `operations_research` | 13 |
| `ophthalmology` | 10 |
| `optics` | 10 |
| `optimization.assignment` | 7 |
| `optimization.explain` | 12 |
| `optimization.flow` | 10 |
| `optimization.integer` | 6 |
| `optimization.linear` | 9 |
| `optimization.model` | 37 |
| `optimization.multiobjective` | 14 |
| `optimization.quadratic` | 8 |
| `optimization.robust` | 9 |
| `optimization.routing` | 15 |
| `optimization.scheduling` | 10 |
| `optimization_meta` | 7 |
| `optimize` | 8 |
| `optmodel.formulation` | 5 |
| `optmodel.judge` | 3 |
| `optmodel.solve` | 2 |
| `orthodontics` | 10 |
| `packaging` | 12 |
| `paleontology` | 12 |
| `palynology` | 10 |
| `pandas_groupby` | 10 |
| `paper_science` | 12 |
| `pattern` | 12 |
| `pde` | 10 |
| `pedology` | 10 |
| `pension` | 12 |
| `perfumery` | 12 |
| `persistence` | 11 |
| `pest_control` | 12 |
| `pharmacology` | 10 |
| `photonics` | 12 |
| `photovoltaics` | 10 |
| `physics` | 12 |
| `phytochemistry` | 10 |
| `pipeline` | 12 |
| `pipelines` | 5 |
| `plasma_physics` | 10 |
| `pls` | 4 |
| `plumbing` | 12 |
| `pneumatics` | 12 |
| `polymer` | 12 |
| `polynomial` | 10 |
| `population` | 10 |
| `positional_encoding` | 10 |
| `power_systems` | 12 |
| `printing` | 12 |
| `privacy` | 10 |
| `procurement` | 12 |
| `progexec.contract` | 1 |
| `progexec.exec` | 1 |
| `progexec.roundexact` | 1 |
| `project_management` | 12 |
| `proteomics` | 10 |
| `protocol` | 10 |
| `psychometrics` | 12 |
| `pulmonology` | 10 |
| `quantum` | 11 |
| `quantum_computing` | 12 |
| `queue_ds` | 12 |
| `queueing` | 11 |
| `radar` | 12 |
| `radiometry` | 10 |
| `random_utils` | 7 |
| `recommender` | 9 |
| `refrigeration` | 12 |
| `regex_engine` | 9 |
| `reinforcement` | 8 |
| `reliability` | 11 |
| `rerank_eval` | 9 |
| `reservoir` | 7 |
| `rheology` | 10 |
| `risk` | 11 |
| `rlhf_dpo` | 10 |
| `robotics` | 12 |
| `robustness` | 8 |
| `root_finding` | 9 |
| `rubber` | 12 |
| `scheduler_ops` | 10 |
| `scheduling_algo` | 9 |
| `scipy_optimize_ops` | 10 |
| `scoring` | 11 |
| `security_governance` | 10 |
| `sedimentology` | 10 |
| `seismology` | 12 |
| `semiconductors` | 12 |
| `seq_nn` | 9 |
| `series` | 10 |
| `set_ops` | 12 |
| `sheet.api` | 2 |
| `sheet.engine` | 1 |
| `sheet.formula` | 3 |
| `sheet.grid` | 1 |
| `sheet.refs` | 7 |
| `sheet.values` | 19 |
| `silviculture` | 10 |
| `simulation` | 8 |
| `sketch` | 9 |
| `soil_mechanics` | 10 |
| `soil_science` | 12 |
| `solar_energy` | 12 |
| `sorting` | 10 |
| `sparse` | 6 |
| `sparse_numerics.csr` | 34 |
| `sparse_numerics.diagnostics` | 21 |
| `sparse_numerics.factor` | 11 |
| `sparse_numerics.iterative` | 18 |
| `sparse_numerics.spmv` | 16 |
| `sparse_vector` | 10 |
| `special_functions` | 12 |
| `speculative_decoding` | 10 |
| `speleology` | 10 |
| `sports_analytics` | 12 |
| `stochastic` | 10 |
| `strategy.contract` | 42 |
| `strategy.crn` | 17 |
| `strategy.equilibrium` | 22 |
| `strategy.policy` | 8 |
| `strategy.tournament` | 8 |
| `streaming.contract` | 21 |
| `streaming.distinct` | 11 |
| `streaming.drift` | 8 |
| `streaming.frequency` | 16 |
| `streaming.quantiles` | 15 |
| `streaming.windows` | 10 |
| `structs.containers` | 2 |
| `structural` | 12 |
| `structured_output` | 10 |
| `supply_chain` | 12 |
| `survival` | 8 |
| `survival_analysis.base` | 9 |
| `survival_analysis.competing` | 3 |
| `survival_analysis.cox` | 3 |
| `survival_analysis.hazard` | 2 |
| `survival_analysis.km` | 3 |
| `survival_analysis.parametric` | 2 |
| `sustainability` | 12 |
| `svm_kernel` | 9 |
| `svm_solver` | 5 |
| `taphonomy` | 10 |
| `telecommunications` | 12 |
| `thermodynamics` | 11 |
| `timber` | 12 |
| `toxicology` | 12 |
| `transform` | 12 |
| `transportation` | 12 |
| `tribochemistry` | 10 |
| `tribology` | 12 |
| `ultrasonics` | 10 |
| `units` | 8 |
| `urban_planning` | 12 |
| `vector_search` | 10 |
| `vector_similarity` | 10 |
| `veterinary` | 12 |
| `video_accessibility` | 9 |
| `video_color` | 9 |
| `video_features` | 5 |
| `video_gate` | 6 |
| `video_ops` | 8 |
| `video_quality` | 6 |
| `video_regions` | 7 |
| `video_similarity` | 7 |
| `video_storyboard` | 6 |
| `virology` | 10 |
| `viticulture` | 12 |
| `volcanology` | 12 |
| `voting` | 11 |
| `wastewater` | 12 |
| `watchmaking` | 12 |
| `water_chemistry` | 10 |
| `weight_loader` | 10 |
| `welding` | 12 |
| `wind_energy` | 12 |
| `wood_science` | 10 |
| `workflow_engine` | 10 |

## Call a module

Every module here is callable through the same surface — the HTTP API, the `de` CLI, and the MCP tools. See [Runtime libraries](runtime-libraries.md) for the `GET /v1/libraries`, `GET /v1/libraries/health`, and `POST /v1/libraries/execute` details.

<table data-view="cards">
<thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Run a library function</strong></td><td>List, check, and execute modules over the API, CLI, or MCP.</td><td><a href="runtime-libraries.md">runtime-libraries.md</a></td></tr>
<tr><td><strong>Engine catalog</strong></td><td>The high-level engines these functions compose into.</td><td><a href="catalog.md">catalog.md</a></td></tr>
<tr><td><strong>How the engine works</strong></td><td>Where the runtime library sits in the architecture.</td><td><a href="../concepts/engine.md">../concepts/engine.md</a></td></tr>
</tbody>
</table>
