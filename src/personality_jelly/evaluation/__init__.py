"""Evaluation services for roleplay quality checks."""

from personality_jelly.evaluation.benchmark import (
    BENCHMARK_CASE_SUITES,
    BOUNDARY_REGRESSION_BENCHMARK_CASES,
    BOUNDARY_REGRESSION_BENCHMARK_CASE_SUITE,
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
    RetrievalBenchmarkReport,
    RetrievalBenchmarkRunResult,
    build_default_retrieval_benchmark_cases,
    export_retrieval_benchmark_cases_file,
    load_retrieval_benchmark_cases_file,
    run_retrieval_benchmark,
    summarize_retrieval_benchmark,
)

__all__ = [
    "BenchmarkCase",
    "BenchmarkRunResult",
    "BENCHMARK_CASE_SUITES",
    "BOUNDARY_REGRESSION_BENCHMARK_CASES",
    "BOUNDARY_REGRESSION_BENCHMARK_CASE_SUITE",
    "DEFAULT_BENCHMARK_CASE_SUITE",
    "DEFAULT_OOC_BENCHMARK_CASES",
    "DEFAULT_RETRIEVAL_TEST_SUITE",
    "EXPANDED_BENCHMARK_CASE_SUITE",
    "EXPANDED_BOUNDARY_BENCHMARK_CASES",
    "RetrievalBenchmarkCase",
    "RetrievalBenchmarkReport",
    "RetrievalBenchmarkRunResult",
    "build_default_retrieval_benchmark_cases",
    "export_retrieval_benchmark_cases_file",
    "get_benchmark_cases",
    "load_retrieval_benchmark_cases_file",
    "run_ooc_benchmark",
    "run_retrieval_benchmark",
    "summarize_retrieval_benchmark",
]
