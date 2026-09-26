"""The model wrapper and the S7 rewrite loop, against a fake Claude client (no network, no DB)."""
from types import SimpleNamespace

import pytest

from app import llm
from app.pipeline import draft as draftmod
from app.pipeline.schemas import EmailDraft, Extracted, Selection, SectionSel, Stipend

from .test_pipeline_rules import POST, SIG, good_draft


class FakeClient:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        stop = "end_turn"
        if isinstance(out, str):              # "refusal" / "max_tokens"
            stop, out = out, None
        usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=3000,
                                cache_creation_input_tokens=0)
        return SimpleNamespace(parsed_output=out, stop_reason=stop, usage=usage, model="claude-opus-5",
                               stop_details=SimpleNamespace(category="cyber") if stop == "refusal" else None)


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    def install(outputs):
        c = FakeClient(outputs)
        llm.set_client(c)
        return c
    yield install
    llm.set_client(None)


def test_request_shape_caches_stable_prefix_and_opts_into_fallbacks(fake):
    c = fake([good_draft()])
    llm.structured("t", EmailDraft, stable=["RULES", "FACTS"], volatile="POST", effort="medium")
    kw = c.calls[0]
    assert [b["text"] for b in kw["system"]] == ["RULES", "FACTS"]
    assert "cache_control" not in kw["system"][0] and kw["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert kw["messages"] == [{"role": "user", "content": "POST"}]
    assert kw["fallbacks"] == "default" and kw["betas"] == [llm.FALLBACK_BETA]
    assert kw["output_config"] == {"effort": "medium"} and kw["output_format"] is EmailDraft
    assert kw["model"] == llm.settings.model


def test_refusal_and_truncation_raise_before_content_is_read(fake):
    fake(["refusal"])
    with pytest.raises(llm.LLMRefusal, match="cyber"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")
    fake(["max_tokens"])
    with pytest.raises(llm.LLMError, match="max_tokens"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")


def test_cost_counts_cache_reads_at_a_tenth():
    u = SimpleNamespace(input_tokens=1_000_000, output_tokens=0, cache_read_input_tokens=1_000_000,
                        cache_creation_input_tokens=0)
    assert llm.cost_usd("claude-opus-5", u) == pytest.approx(5.0 + 0.5)


def _write(fake_outputs, fake):
    c = fake(fake_outputs)
    ex = Extracted(title="Backend Intern", company_name="Acme Labs", poster_name="Priya", poster_type="employee",
                   stipend=Stipend(stated="figure"), discipline="backend")
    sel = Selection(role_title="Backend Intern", track_key="sde",
                    left_sections=[SectionSel(heading="Projects", item_keys=["queuekit"])],
                    bullet_ids=[], fit_score=80, fit_reasons=[], lead_with="QueueKit")
    out = draftmod.write(ex=ex, raw_text=POST, sel=sel, selected_bullets=["b"],
                         facts=[{"id": "f1", "kind": "metric",
                                 "text": "QueueKit sustained 300 jobs per second with four workers"}],
                         profile={"name": "Aarav"}, prefs={"signature_html": SIG, "stipend_floor": 10000,
                                                            "duration_flex": "Flexible on duration",
                                                            "start_date": "Immediately"},
                         stipend_rule="none", to_addr="hr@acmelabs.io", allowed_extra=["2027"],
                         ctx=llm.CallContext())
    return out, c


def test_failed_lint_is_fed_back_and_rewritten(fake):
    bad = good_draft(paragraphs=["Hi Priya,", good_draft().paragraphs[1].replace("QueueKit is", "QueueKit — is")])
    out, c = _write([bad, good_draft()], fake)
    assert out.ok and out.attempts == 2
    assert "no_em_dash" in c.calls[1]["messages"][0]["content"]       # feedback reached the rewrite
    assert out.plain.endswith(SIG)
    assert out.facts_used == ["f1"]


def test_gives_up_after_two_rewrites_and_reports_failures(fake):
    bad = good_draft(paragraphs=["Hi Priya,", "Too short. My resume is attached."])
    out, c = _write([bad, bad, bad], fake)
    assert not out.ok and out.attempts == 3 and len(c.calls) == 3
    assert any(ch.name == "length" and not ch.ok for ch in out.checks)
