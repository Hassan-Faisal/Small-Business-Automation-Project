# Zero-credit classifier benchmark plan

This plan is based only on the local repository. No OpenAI calls, API key, network access, commit, or push is required.

## What was measured

The runner calls StructuredIntentClassifier.build_prompt() with _context_for_classifier(case). The prompt contains the fixed classifier instructions plus compact JSON SemanticContext:

- customer message
- recent turns
- cart items
- pending clarification/action
- pending options
- catalog candidates present in the case
- active order

It does not send the full product catalog. Using the installed tiktoken o200k_base encoding:

| Set | Cases | Input tokens | Average | Range |
|---|---:|---:|---:|---:|
| Full dataset | 100 | 40,453 | 404.5 | 391–430 |
| Stage 1 | 25 | 10,191 | 407.6 | 394–430 |

These are estimates of prompt tokens, not provider-billed usage. Actual billing may include provider-specific framing/cached-token treatment.

### Output estimate

The structured schema has 15 fields, many nullable/defaulted. For planning:

- base estimate: 60 output tokens per classification
- conservative output estimate: 100 output tokens per classification

The base cost tables below use 60 output tokens. A 30% safety margin is then applied for planning. Actual live results must use returned usage metadata when available; offline mode never fabricates token data.

## Pricing inputs

Configured planning prices:

| Model | Input / 1M | Output / 1M |
|---|---:|---:|
| gpt-5.6-luna | $1.00 | $6.00 |
| gpt-5.6-terra | $2.50 | $15.00 |
| gpt-5.5 | not present locally | not present locally |

For a model with input price P_in and output price P_out, the full 100-case estimate is:

0.040453 * P_in + 0.006000 * P_out

The Stage-1 estimate is:

0.010191 * P_in + 0.001500 * P_out

## Estimated live benchmark cost

Using 404.53 input tokens and 60 output tokens per case:

| Model | 100 cases | 30% safety margin |
|---|---:|---:|
| gpt-5.6-luna | $0.0765 | $0.0994 |
| gpt-5.6-terra | $0.1911 | $0.2485 |
| gpt-5.5 | 0.040453*P_in + 0.006000*P_out | multiply by 1.30 |
| All three | $0.2676 + gpt-5.5 cost | multiply total by 1.30 |

At the conservative 100-output-token assumption, Luna is approximately $0.0411, Terra approximately $0.1011, and the known-model combined total approximately $0.1422 before margin.

## Stage 1

The proposed label-preserving subset is app/evaluation/stage1_dataset.json and contains 25 existing cases:

- Roman Urdu: greeting, add, quantity, search, and order follow-up cases
- English: greeting, menu, product extraction, quantity, cart, and contextual cases
- Contextual cart operations: quantity-002, quantity-005, remove-004, context-004, context-005
- Ambiguous references: add-011, search-008, context-007, edge-010, edge-011
- Product extraction: add-001, add-003, add-006
- Search/filter: search-002, search-003, search-008
- Structured-output safety: invalid/ambiguous quantity and clarification cases
- Confirmation/tracking state: context-002, order-004

Stage 1 costs about $0.0192 for Luna and $0.0480 for Terra before margin. It is enough for a cheap first-pass quality screen and avoids spending credits on all three models when one is clearly below the quality bar.

## Gates

Stage 1, 25 cases:

- intent accuracy >= 95%: at least 24/25
- structured-output success = 100%: 25/25
- clarification correctness >= 98%: with 25 cases, require 25/25 because one error is 96%
- no unsafe product identity assumptions: zero cases where an ambiguous or unsupported reference is resolved as a definite product without sufficient context
- manually inspect every entity/product failure and every safety failure

Stage 2, 100 cases:

- intent accuracy >= 95%: at least 95/100
- structured-output success >= 99%: at least 99/100
- clarification safety >= 98%: at least 98/100, with zero unsafe identity assumptions
- report the known semantic-label mismatch separately; do not silently treat schema/label mismatches as model failures

The current dataset includes menu labels such as dinner_menu, lunch_menu, and breakfast_menu, while the structured classifier schema uses broader/aliased intent semantics. Stage 1 intentionally avoids those mismatch cases. Stage 2 should retain all 100 cases and report this mismatch explicitly rather than changing expected labels.

## Production economics

Using the optimized prompt estimate and 60 output tokens:

| Model | Cost / classification |
|---|---:|
| Luna | $0.0007645 |
| Terra | $0.0019113 |
| GPT-5.5 | 0.000040453*P_in + 0.000006*P_out |

Customer-message costs:

| Model | Classifier rate | 100 messages | 1,000 messages | 10,000 messages |
|---|---:|---:|---:|---:|
| Luna | 20% | $0.0153 | $0.1529 | $1.5291 |
| Luna | 40% | $0.0306 | $0.3058 | $3.0581 |
| Luna | 60% | $0.0459 | $0.4587 | $4.5872 |
| Terra | 20% | $0.0382 | $0.3823 | $3.8227 |
| Terra | 40% | $0.0765 | $0.7645 | $7.6453 |
| Terra | 60% | $0.1147 | $1.1468 | $11.4680 |
| GPT-5.5 | 20/40/60% | use formula above | use formula above | use formula above |

Approximate customer messages supported by $5:

| Model | 20% classifier rate | 40% | 60% |
|---|---:|---:|---:|
| Luna | ~3,270 | ~1,635 | ~1,090 |
| Terra | ~1,308 | ~654 | ~436 |
| GPT-5.5 | 5 / (cost_per_classification * rate) | same | same |

All economics are estimates and exclude retries, provider framing, taxes, and other application costs.

## Economic outlook before quality testing

Luna is the most economically promising of the priced candidates: it is approximately 2.5x cheaper than Terra under the supplied prices. That is only a screening observation, not a deployment recommendation. Luna must pass the safety and quality gates before it can be preferred.

GPT-5.5 cannot be ranked economically until its pricing is entered. Do not substitute a remembered or online price.

## Later commands

Run Stage 1 separately for each model after deliberately enabling live mode and setting the API key in the normal environment:

~~~powershell
$env:RUN_OPENAI_BENCHMARK = "1"

python scripts/benchmark_classifier.py --live --model gpt-5.6-luna --dataset app/evaluation/stage1_dataset.json --output-dir benchmark_results/stage1 --input-price 1.00 --output-price 6.00 --classifier-rate 0.4

python scripts/benchmark_classifier.py --live --model gpt-5.6-terra --dataset app/evaluation/stage1_dataset.json --output-dir benchmark_results/stage1 --input-price 2.50 --output-price 15.00 --classifier-rate 0.4

python scripts/benchmark_classifier.py --live --model gpt-5.5 --dataset app/evaluation/stage1_dataset.json --output-dir benchmark_results/stage1 --classifier-rate 0.4
~~~

The GPT-5.5 command intentionally omits prices until you configure them. Add --input-price and --output-price only after confirming the official values.

Compare Stage 1:

~~~powershell
python scripts/compare_benchmarks.py benchmark_results/stage1/gpt-5.6-luna.json benchmark_results/stage1/gpt-5.6-terra.json benchmark_results/stage1/gpt-5.5.json
~~~

Only models that pass Stage 1 should run Stage 2:

~~~powershell
python scripts/benchmark_classifier.py --live --model MODEL_NAME --dataset app/evaluation/dataset.json --output-dir benchmark_results/stage2 --input-price INPUT_USD_PER_1M --output-price OUTPUT_USD_PER_1M --classifier-rate 0.4
~~~
