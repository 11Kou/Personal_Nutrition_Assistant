import argparse
import json
from pathlib import Path

from app.evaluation.runner import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local RAG evaluation suite.")
    parser.add_argument("--eval-path", default="data/evaluation/eval_set.jsonl")
    parser.add_argument("--index-dir", default="data/index")
    parser.add_argument("--food-csv-path", default="data/food/foods.csv")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--use-chroma", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    result = run_evaluation(
        eval_path=args.eval_path,
        index_dir=args.index_dir,
        csv_path=args.food_csv_path,
        top_k=args.top_k,
        use_chroma=args.use_chroma,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()

