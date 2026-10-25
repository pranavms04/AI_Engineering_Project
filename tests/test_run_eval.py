import json
from dataclasses import replace

import pytest

from app.config import Settings
from app.generation.llm_client import FakeLLMClient
from evaluation.run_eval import is_clean_abstain, load_dataset, min_score_sweep, run

# Invented sample documents, not real user files.
DOCS = {
    "ports.md": "Ollama listens on port 11434 on your own computer. The API uses port 8000.",
    "fruit.md": "Bananas are yellow when ripe. Apples can be red or green.",
}


def row(id_, question, sources=(), keywords=(), abstain=False) -> dict:
    return {
        "id": id_,
        "question": question,
        "expected_sources": [{"source": s} for s in sources],
        "expected_answer_keywords": list(keywords),
        "should_abstain": abstain,
    }


@pytest.fixture
def setup(tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    for name, text in DOCS.items():
        (docs / name).write_text(text, encoding="utf-8")
    dataset = tmp_path / "dataset.jsonl"
    rows = [
        row("q1", "Which port does Ollama listen on?", ["ports.md"], ["11434"]),
        row("q2", "What colour are ripe bananas?", ["fruit.md"], ["yellow"]),
        row("q3", "Who won the 1998 football world cup?", abstain=True),
    ]
    dataset.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    settings = Settings(docs_dir=docs, min_score=0.30, top_k=2, chunk_size=500, chunk_overlap=100)
    return settings, dataset, tmp_path / "results"


def test_load_dataset_reads_items(setup):
    _settings, dataset, _out = setup
    items = load_dataset(dataset)
    assert [i.id for i in items] == ["q1", "q2", "q3"]
    assert items[0].expected == {("ports.md", None)}
    assert items[2].should_abstain is True


@pytest.mark.parametrize(
    "bad_line, message",
    [
        ("{not json", "not valid JSON"),
        (json.dumps({"id": "x", "question": "q"}), "missing keys"),
        (json.dumps(row("x", "q", sources=[])), "needs expected_sources"),
    ],
)
def test_load_dataset_rejects_bad_lines_with_line_number(tmp_path, bad_line, message):
    path = tmp_path / "bad.jsonl"
    path.write_text(json.dumps(row("ok", "q", ["a.md"])) + "\n" + bad_line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=rf"bad.jsonl:2: .*{message}"):
        load_dataset(path)


def test_load_dataset_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "dup.jsonl"
    line = json.dumps(row("same", "q", ["a.md"]))
    path.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate id"):
        load_dataset(path)


def test_retrieval_only_run_records_config_and_never_calls_llm(setup):
    settings, dataset, out = setup
    llm = FakeLLMClient("should not be used")
    config, summary, rows, path = run(settings, dataset, with_llm=False, llm=llm, out_dir=out)

    assert llm.calls == []
    assert all("answer" not in r for r in rows)
    assert "llm" not in summary
    assert config["chunk_size"] == 500 and config["chunk_overlap"] == 100
    assert config["min_score"] == 0.30 and config["top_k"] == 2
    assert config["llm_model"] is None
    assert config["git_commit"]  # a hash, "...-dirty" or "unknown"
    saved = json.loads(path.read_text())
    assert saved["config"] == config
    assert len(saved["questions"]) == 3


def test_retrieval_finds_the_right_document(setup):
    settings, dataset, out = setup
    _config, summary, rows, _ = run(settings, dataset, with_llm=False, out_dir=None)

    by_id = {r["id"]: r for r in rows}
    assert by_id["q1"]["first_hit_rank"] == 1
    assert by_id["q2"]["first_hit_rank"] == 1
    assert summary["recall@1"] == 1.0
    assert summary["answerable"] == 2 and summary["should_abstain"] == 1


def test_with_llm_adds_answer_metrics_and_review_file(setup):
    settings, dataset, out = setup
    llm = FakeLLMClient("Ollama listens on 11434 [ports.md]. See also [made-up.pdf, p. 9].")
    _config, summary, rows, path = run(settings, dataset, with_llm=True, llm=llm, out_dir=out)

    answered = [r for r in rows if "answer" in r]
    assert len(llm.calls) == len([r for r in rows if not r["gate_abstained"]])
    assert summary["llm"]["answered"] == 3
    assert summary["llm"]["llm_errors"] == 0
    # The invented citation is caught: accuracy is below 1.
    assert summary["llm"]["citation_accuracy"] < 1.0
    assert summary["llm"]["answers_with_invalid_citation"] >= 1
    assert set(summary["llm"]["latency_ms"]) == {"retrieve", "generate", "total"}
    assert all(r["keyword_coverage"] is None for r in answered if r["should_abstain"])
    assert path.with_suffix(".review.md").exists()


def test_with_llm_fails_clearly_when_ollama_unreachable(setup):
    from app.generation.llm_client import LLMUnavailableError

    settings, dataset, out = setup
    with pytest.raises(LLMUnavailableError, match="ollama serve"):
        run(settings, dataset, with_llm=True, llm=FakeLLMClient(reachable=False), out_dir=out)


def test_min_score_sweep_abstains_more_as_threshold_rises():
    rows = [
        {"should_abstain": False, "best_score": 0.60},
        {"should_abstain": False, "best_score": 0.35},
        {"should_abstain": True, "best_score": 0.25},
        {"should_abstain": True, "best_score": 0.10},
    ]
    table = min_score_sweep(rows, [0.2, 0.3, 0.4])
    refusals = [t["true_positives"] + t["false_positives"] for t in table]
    assert refusals == sorted(refusals)
    assert table[1]["recall"] == 1.0 and table[1]["false_positives"] == 0  # 0.3 separates them perfectly
    assert table[2]["false_positives"] == 1  # 0.4 also refuses the 0.35 answerable question


def test_clean_abstain_rejects_invented_answer_that_ends_with_refusal():
    assert is_clean_abstain("I couldn't find this in the documents.")
    assert is_clean_abstain("  I couldn't find this in the documents  ")
    invented = "Run docker build -t app . to deploy.\n\nI couldn't find this in the documents."
    assert not is_clean_abstain(invented)


def test_strict_abstention_is_reported_with_llm(setup):
    settings, dataset, _out = setup
    settings = replace(settings, min_score=0.0)  # let every question reach the (fake) LLM
    invented = "Brazil won it.\n\nI couldn't find this in the documents."
    _config, summary, rows, _ = run(settings, dataset, with_llm=True, llm=FakeLLMClient(invented), out_dir=None)

    q3 = next(r for r in rows if r["id"] == "q3")
    assert q3["abstained"] is True  # the app's loose check is fooled
    assert q3["clean_abstained"] is False  # the strict check is not
    assert summary["llm"]["abstention"]["recall"] == 1.0
    assert summary["llm"]["strict_abstention"]["recall"] == 0.0
