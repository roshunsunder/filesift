# Advanced FileSift Usage

## Daemon management

The daemon keeps indexes in memory for faster repeated searches. It starts automatically when you run `filesift find` or `filesift index`.

```bash
# Check if daemon is running
filesift daemon status

# Manually start/stop
filesift daemon start
filesift daemon stop

# Kill all daemon processes
filesift daemon kill --all
```

The daemon auto-shuts down after 5 minutes of inactivity (configurable).

## Configuration

```bash
# View all settings
filesift config list --all

# Common adjustments
filesift config set search.MAX_RESULTS 20
filesift config set search.SIMILARITY_THRESHOLD 0.3
filesift config set daemon.INACTIVITY_TIMEOUT 600

# Add directories to exclude from indexing
filesift config add-ignore ".idea" "coverage" "tmp"

# View current ignore patterns
filesift config list-ignore
```

## How search works

FileSift uses two search tiers merged via Reciprocal Rank Fusion (RRF):

1. **Fast tier (BM25)**: Keyword and structural matching against function names, class names, imports, and tokenized content. Available immediately after indexing.
2. **Semantic tier (FAISS)**: Embedding-based similarity using the Nomic model. Available after background indexing completes.

Results from both tiers are merged with equal weighting (alpha=0.5). If only one tier is available, results come from that tier alone.

## Troubleshooting

**"No index found"**: Run `filesift index <path>` first.

**Results seem keyword-only**: Semantic index may still be building. Wait 1-3 minutes and re-search, or check with `filesift daemon status`.

**Stale results after code changes**: Run `filesift index <path>` to incrementally update, or `filesift index <path> --reindex` for a full rebuild.

**Daemon won't start**: Check for orphaned processes with `filesift daemon list` and kill them with `filesift daemon kill --all`.
