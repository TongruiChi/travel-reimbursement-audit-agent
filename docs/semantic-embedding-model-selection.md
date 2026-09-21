# Semantic embedding model selection

Checked 2026-09-19 against the official Hugging Face model cards.

| Attribute | BGE-small-zh-v1.5 | multilingual-E5-small |
|---|---|---|
| Model ID | `BAAI/bge-small-zh-v1.5` | `intfloat/multilingual-e5-small` |
| Revision | `7999e1d3359715c523056ef9478215996d62a620` | `614241f622f53c4eeff9890bdc4f31cfecc418b3` |
| License | MIT | MIT |
| Language | Chinese | 94 languages, including Chinese |
| Parameters | 24M | N/A from model card |
| Dimension | 512 | 384 |
| Max sequence length | 512 | 512 |
| Weight file | 95.8 MB | 471 MB |
| Repository download size | about 192 MB | about 2.28 GB (includes alternate formats) |
| Query format | Chinese retrieval instruction | `query: ` prefix |
| Passage format | unchanged passage | `passage: ` prefix |
| Normalization | L2 | L2 |
| Device | CPU baseline; GPU not required | CPU baseline; GPU not required |
| External API | no | no |

Sources: https://huggingface.co/BAAI/bge-small-zh-v1.5 and
https://huggingface.co/intfloat/multilingual-e5-small.

## Pilot result and selection

The experiment uses the unchanged 10-rule Policy Registry corpus and the approved
12-query Pilot Golden Dataset. No similarity threshold was applied in the first
baseline. E5 achieved higher Recall@1, Set Recall@3, and MRR than BGE, while BGE
was smaller and faster. `intfloat/multilingual-e5-small` is selected for
`embedding-v2` because retrieval quality is the primary requirement for this
small CPU-local demonstration. This is a project-specific Pilot decision, not a
claim that E5 is universally superior.

Both semantic models returned a nearest neighbour for the negative query, so
Negative No-result Accuracy was 0%. Threshold calibration is deliberately deferred
to a later, larger dataset instead of tuning to one negative example.

| Metric | BGE-small-zh-v1.5 | multilingual-E5-small |
|---|---:|---:|
| Recall@1 | 90.91% | 100.00% |
| Recall@3 | 100.00% | 100.00% |
| Set Recall@3 | 90.91% | 95.45% |
| MRR | 95.45% | 100.00% |
| Negative accuracy | 0.00% | 0.00% |
| Model load | 4216.73 ms | 7185.67 ms |
| Index build | 200.86 ms | 268.69 ms |
| CPU query p50 | 28.590 ms | 43.618 ms |
| CPU query p95 | 44.236 ms | 63.952 ms |
| Selected | no | yes |

Selection reasons are kept separate rather than collapsed into an arbitrary
weighted score: E5 won the frozen Pilot on Recall@1, Set Recall@3, and MRR; its
documented multilingual contract includes Chinese; and its 384-dimensional
vectors are smaller than BGE's 512-dimensional vectors. The decision explicitly
accepts E5's larger weight, slower load, and higher CPU query latency. Latency is
a development-machine diagnostic, not a production benchmark.

## Sealed retrieval decision

`embedding-v2` is the available E5 semantic path. `hybrid-v2` combines it with
BM25 using the unchanged RRF k=60, but it is not the default retriever: its Pilot
Set Recall@3 was 95.45% versus 100% for `hybrid-v1`, and its negative accuracy
was 0% versus 100%. The existing default/strong baseline therefore remains
unchanged.

Resume evidence:

- Evaluated BGE-small-zh-v1.5 and multilingual-E5-small for Chinese policy
  retrieval across Recall@K, MRR, CPU latency, model size, and deployment cost.
- Implemented local pretrained semantic retrieval and BM25 + semantic RRF, then
  compared all six retrieval paths on the fixed Golden Dataset.
- E5 raised hash-vector Recall@1 from 90.91% to 100%, while exposing the
  no-threshold negative-accuracy regression from 100% to 0%.
