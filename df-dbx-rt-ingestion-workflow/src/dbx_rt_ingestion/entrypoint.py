"""Job entrypoint.

Databricks job task (or local run):

    dfx-ingest --spec conf/apps/gbs_auth/platform_a.yaml --env dev --conf-dir conf

Also usable programmatically:

    from dbx_rt_ingestion.entrypoint import run_app
    run_app(spec_path="...", environment="dev", conf_dir="conf")
"""

from __future__ import annotations

import argparse

from dbx_rt_ingestion.config.loader import SpecLoader
from dbx_rt_ingestion.pipeline.runner import PipelineRunner


def run_app(
    *,
    spec_path: str,
    environment: str,
    conf_dir: str = "conf",
    await_termination: bool = True,
) -> PipelineRunner:
    """Load, validate, and run one application spec."""

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.getOrCreate()
    loader = SpecLoader(conf_dir=conf_dir, environment=environment)
    spec = loader.load_app_spec(spec_path)
    runner = PipelineRunner(spark, spec, loader)
    runner.run(await_termination=await_termination)
    return runner


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="dfx-ingest",
        description="df-dbx-rt-ingestion-workflow: run a spec-driven streaming app",
    )
    parser.add_argument("--spec", required=True, help="Path to the application spec YAML")
    parser.add_argument("--env", required=True, help="Environment name (dev|qa|prod)")
    parser.add_argument("--conf-dir", default="conf", help="Configuration root directory")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the spec and exit (CI gate / pre-deploy check)",
    )
    args = parser.parse_args()

    if args.validate_only:
        from dbx_rt_ingestion.config.validation import validate_app_spec

        loader = SpecLoader(conf_dir=args.conf_dir, environment=args.env)
        spec = loader.load_app_spec(args.spec)
        validate_app_spec(spec)
        print(f"OK: spec '{spec.name}' is valid for environment '{args.env}'")
        return

    run_app(spec_path=args.spec, environment=args.env, conf_dir=args.conf_dir)


if __name__ == "__main__":
    main()
