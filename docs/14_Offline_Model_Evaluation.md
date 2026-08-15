# Offline classifier model evaluation

The harness uses the same StructuredIntentClassifier and IntentClassification schema as production. It is offline by default and never constructs an OpenAI client or sends a request. Its offline mode replays each case's expected structured result through the production classifier path; this validates dataset loading, context conversion, schema validation, scoring, and result serialization. It is a harness check, not a claim about model quality.

## Offline

From the repository root:

~~~powershell
python scripts/benchmark_classifier.py
python -m pytest -q tests/test_evaluation_harness.py
~~~

The default dataset is app/evaluation/dataset.json (100 cases). Results are written to benchmark_results/offline-reference.json unless --output-dir is supplied.

## Live, deliberate opt-in

After adding credits and configuring the key, run one model explicitly:

~~~powershell
$env:RUN_OPENAI_BENCHMARK = "1"
python scripts/benchmark_classifier.py --live --model MODEL_NAME --input-price INPUT_USD_PER_1M --output-price OUTPUT_USD_PER_1M --classifier-rate 0.4
~~~

Both --live and RUN_OPENAI_BENCHMARK=1 are required. Pytest does not enable this mode. Token and latency fields remain null when the provider does not expose usage metadata; the harness never fabricates token counts.

## Compare runs

~~~powershell
python scripts/compare_benchmarks.py benchmark_results/model-a.json benchmark_results/model-b.json
~~~

Thresholds default to intent >= 95%, structured output >= 99%, and clarification correctness >= 98%; CLI flags can override them. A model is considered for cheapest-model review only after it meets all thresholds and has configured pricing. No model is recommended from price alone.

## Cost

Prices are supplied per million input/output tokens on the live command. The result includes cost per classification, per 100 classifications, per 1,000 classifications, and estimated cost per 1,000 customer messages. The latter is cost_per_classification * 1000 * classifier_rate; for example, --classifier-rate 0.4 models a classifier invoked for 40% of messages.
