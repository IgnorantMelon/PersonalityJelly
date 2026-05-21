"""Evaluation services for roleplay quality checks."""

from personality_jelly.evaluation.benchmark import (
    BENCHMARK_CASE_SUITES,
    BenchmarkCase,
    BenchmarkRunResult,
    DEFAULT_BENCHMARK_CASE_SUITE,
    DEFAULT_OOC_BENCHMARK_CASES,
    EXPANDED_BENCHMARK_CASE_SUITE,
    EXPANDED_BOUNDARY_BENCHMARK_CASES,
    get_benchmark_cases,
    run_ooc_benchmark,
)
from personality_jelly.evaluation.retrieval_benchmark import (
    DEFAULT_RETRIEVAL_TEST_SUITE,
    RetrievalBenchmarkCase,
    RetrievalBenchmarkRunResult,
    build_default_retrieval_benchmark_cases,
    run_retrieval_benchmark,
)

__all__ = [
    "BenchmarkCase",
    "BenchmarkRunResult",
    "BENCHMARK_CASE_SUITES",
    "DEFAULT_BENCHMARK_CASE_SUITE",
    "DEFAULT_OOC_BENCHMARK_CASES",
    "DEFAULT_RETRIEVAL_TEST_SUITE",
    "EXPANDED_BENCHMARK_CASE_SUITE",
    "EXPANDED_BOUNDARY_BENCHMARK_CASES",
    "RetrievalBenchmarkCase",
    "RetrievalBenchmarkRunResult",
    "build_default_retrieval_benchmark_cases",
    "get_benchmark_cases",
    "run_ooc_benchmark",
    "run_retrieval_benchmark",
]
