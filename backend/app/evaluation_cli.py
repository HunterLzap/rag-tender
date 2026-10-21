import argparse
import asyncio
import json
from pathlib import Path

from app.db import get_engine
from app.services.evaluation import evaluate_run, load_golden_set


async def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate an analysis run against a golden set")
    parser.add_argument("run_id")
    parser.add_argument("golden_set", type=Path)
    args = parser.parse_args()
    golden = load_golden_set(args.golden_set)
    from sqlalchemy.ext.asyncio import async_sessionmaker

    async with async_sessionmaker(get_engine(), expire_on_commit=False)() as session:
        result = await evaluate_run(session, args.run_id, golden)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
