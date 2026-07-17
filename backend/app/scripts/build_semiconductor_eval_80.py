"""Derive public evaluation artifacts from an ignored private master file.

The source code intentionally contains no test/hidden labels. Maintainers may use
``--migrate-legacy`` once to move an existing labelled suite behind the private
repository boundary; normal operation reads only that private master.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


PUBLIC_QUESTION_FIELDS = (
    "id",
    "domain",
    "category",
    "split",
    "knowledge_base",
    "question",
)
LABELLED_PUBLIC_SPLITS = {"regression", "development"}
PRIVATE_KEY_SPLITS = {"test", "hidden"}
EXPECTED_SPLITS = LABELLED_PUBLIC_SPLITS | PRIVATE_KEY_SPLITS


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError(f"{path}: 必须是题目对象数组")
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def question_view(case: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in PUBLIC_QUESTION_FIELDS if key not in case]
    if missing:
        raise ValueError(f"{case.get('id', '<unknown>')}: 缺少公开字段 {missing}")
    return {key: case[key] for key in PUBLIC_QUESTION_FIELDS}


def validate_master(cases: list[dict[str, Any]]) -> None:
    ids = [str(case.get("id") or "") for case in cases]
    if not ids or "" in ids or len(ids) != len(set(ids)):
        raise ValueError("私有 master 存在空 ID 或重复 ID")
    split_counts = Counter(case.get("split") for case in cases)
    if set(split_counts) != EXPECTED_SPLITS:
        raise ValueError(f"分层不完整: {dict(split_counts)}")
    if len(set(split_counts.values())) != 1:
        raise ValueError(f"分层不均衡: {dict(split_counts)}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_artifacts(root: Path, cases: list[dict[str, Any]]) -> dict[str, Any]:
    validate_master(cases)
    sample_dir = root / "sample-data"
    private_dir = root / "data" / "evaluation-private"
    generated: list[Path] = []

    for split in sorted(LABELLED_PUBLIC_SPLITS):
        path = sample_dir / f"semiconductor_rag_eval_{split}.json"
        write_json(path, [case for case in cases if case["split"] == split])
        generated.append(path)

    for split in sorted(PRIVATE_KEY_SPLITS):
        private_cases = [case for case in cases if case["split"] == split]
        question_path = sample_dir / f"semiconductor_rag_eval_{split}_questions.json"
        answer_path = private_dir / f"semiconductor_rag_eval_{split}_answers.json"
        write_json(question_path, [question_view(case) for case in private_cases])
        write_json(answer_path, private_cases)
        generated.append(question_path)

    manifest_path = sample_dir / "semiconductor_rag_eval_manifest.json"
    manifest = {
        "version": 2,
        "case_count": len(cases),
        "split_counts": dict(sorted(Counter(case["split"] for case in cases).items())),
        "label_visibility": {
            "regression": "public",
            "development": "public",
            "test": "private",
            "hidden": "private",
        },
        "public_artifacts": {
            str(path.relative_to(root)): {"sha256": _sha256(path)}
            for path in generated
        },
        "private_key_directory": "data/evaluation-private (gitignored)",
    }
    write_json(manifest_path, manifest)
    return manifest


def main() -> int:
    root = Path(__file__).resolve().parents[3]
    private_master = root / "data/evaluation-private/semiconductor_rag_eval_master.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-master",
        type=Path,
        default=private_master,
        help="被 Git 忽略的完整评分主文件",
    )
    parser.add_argument(
        "--migrate-legacy",
        type=Path,
        help="一次性将历史带标签合并集移入私有 master",
    )
    args = parser.parse_args()

    master_path = args.private_master.resolve()
    if args.migrate_legacy:
        cases = load_cases(args.migrate_legacy.resolve())
        validate_master(cases)
        write_json(master_path, cases)
    elif not master_path.is_file():
        parser.error(
            f"私有 master 不存在: {master_path}；"
            "维护者首次迁移可使用 --migrate-legacy"
        )
    cases = load_cases(master_path)
    manifest = build_artifacts(root, cases)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
