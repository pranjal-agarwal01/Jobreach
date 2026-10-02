"""The model wrapper (both providers) and the S7 rewrite loop, against fake clients
(no network, no DB)."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app import llm
from app.pipeline import draft as draftmod
from app.pipeline.schemas import EmailDraft, Extracted, Selection, SectionSel, Stipend

from .test_pipeline_rules import POST, SIG, good_draft


class FakeAnthropic:
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
        return SimpleNamespace(parsed_output=out, stop_reason=stop, usage=usage, model="claude-sonnet-5-5",
                               stop_details=SimpleNamespace(category="cyber") if stop == "refusal" else None)


class FakeOpenAI:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.responses = SimpleNamespace(parse=self._parse)

    def _parse(self, **kw):
        self.calls.append(kw)
        out = self.outputs.pop(0)
        status, incomplete, content = "completed", None, []
        if out == "refusal":
            out, content = None, [SimpleNamespace(type="refusal", refusal="I can't help with that")]
        elif out == "max_tokens":
            out, status, incomplete = None, "incomplete", SimpleNamespace(reason="max_output_tokens")
        usage = SimpleNamespace(input_tokens=4000, output_tokens=300,
                                input_tokens_details=SimpleNamespace(cached_tokens=3000, cache_write_tokens=0))
        return SimpleNamespace(output_parsed=out, status=status, incomplete_details=incomplete,
                               output=[SimpleNamespace(type="message", content=content)],
                               usage=usage, model="gpt-6.1-sol")


@pytest.fixture
def fake(monkeypatch):
    """Install a fake client for a provider; the provider is pinned so tests never depend
    on backend/.env."""
    monkeypatch.setattr(llm, "_log", lambda *a, **k: None)

    def install(outputs, provider="anthropic"):
        monkeypatch.setattr(llm, "settings", replace(llm.settings, provider=provider, model="", model_fast=""))
        c = FakeOpenAI(outputs) if provider == "azure_openai" else FakeAnthropic(outputs)
        llm.set_client(c)
        return c
    yield install
    llm.set_client(None)


# ------------------------------------------------------------------ Claude

def test_claude_request_caches_stable_prefix_and_opts_into_fallbacks(fake):
    c = fake([good_draft()])
    llm.structured("t", EmailDraft, stable=["RULES", "FACTS"], volatile="POST", effort="medium")
    kw = c.calls[0]
    assert [b["text"] for b in kw["system"]] == ["RULES", "FACTS"]
    assert "cache_control" not in kw["system"][0] and kw["system"][1]["cache_control"] == {"type": "ephemeral"}
    assert kw["messages"] == [{"role": "user", "content": "POST"}]
    assert kw["fallbacks"] == "default" and kw["betas"] == [llm.FALLBACK_BETA]
    assert kw["output_config"] == {"effort": "medium"} and kw["output_format"] is EmailDraft
    assert kw["model"] == "claude-sonnet-5-5"
    assert kw["max_tokens"] >= llm.MIN_OUTPUT_BUDGET


def test_foundry_omits_server_side_fallbacks(fake):
    """Claude on Foundry has no server-side fallbacks (the client-side middleware covers it);
    sending the parameter or its beta header there would be rejected."""
    c = fake([good_draft()], provider="foundry")
    llm.structured("t", EmailDraft, stable=["R"], volatile="x")
    assert "fallbacks" not in c.calls[0] and "betas" not in c.calls[0]


def test_claude_refusal_and_truncation_raise_before_content_is_read(fake):
    fake(["refusal"])
    with pytest.raises(llm.LLMRefusal, match="cyber"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")
    fake(["max_tokens"])
    with pytest.raises(llm.LLMError, match="cap"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")


# ------------------------------------------------------------------ Azure OpenAI

def test_openai_request_shape(fake):
    c = fake([good_draft()], provider="azure_openai")
    llm.structured("s7_draft", EmailDraft, stable=["RULES", "FACTS"], volatile="POST", effort="medium",
                   ctx=llm.CallContext(user_id="u1"))
    kw = c.calls[0]
    assert kw["instructions"] == "RULES\n\nFACTS" and kw["input"] == "POST"   # stable prefix first
    assert kw["text_format"] is EmailDraft and kw["reasoning"] == {"effort": "medium"}
    assert kw["store"] is False                                            # nothing kept by OpenAI
    assert kw["prompt_cache_key"].startswith("s7_draft:") and "u1" not in kw["prompt_cache_key"]
    assert kw["model"] == "gpt-6.1-sol" and kw["max_output_tokens"] >= llm.MIN_OUTPUT_BUDGET
    assert "fallbacks" not in kw and "betas" not in kw


def test_openai_routes_extraction_to_the_fast_model(fake):
    c = fake([good_draft(), good_draft()], provider="azure_openai")
    llm.structured("s1_extract", EmailDraft, stable=["R"], volatile="x")
    llm.structured("s5_select", EmailDraft, stable=["R"], volatile="x")
    assert [k["model"] for k in c.calls] == ["gpt-6-luna", "gpt-6.1-sol"]


def test_openai_refusal_and_truncation_raise(fake):
    fake(["refusal"], provider="azure_openai")
    with pytest.raises(llm.LLMRefusal, match="can't help"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")
    fake(["max_tokens"], provider="azure_openai")
    with pytest.raises(llm.LLMError, match="cap"):
        llm.structured("t", EmailDraft, stable=["R"], volatile="x")


def test_endpoint_gets_the_v1_path():
    s = replace(llm.settings, azure_openai_endpoint="https://myres.openai.azure.com/")
    assert s.azure_openai_base_url == "https://myres.openai.azure.com/openai/v1/"
    s = replace(llm.settings, azure_openai_endpoint="https://myres.services.ai.azure.com/openai/v1")
    assert s.azure_openai_base_url == "https://myres.services.ai.azure.com/openai/v1/"
    s = replace(llm.settings, azure_openai_endpoint="https://myres.services.ai.azure.com/api/projects/proj1")
    assert s.azure_openai_base_url == "https://myres.services.ai.azure.com/openai/v1/"
    s = replace(llm.settings, azure_openai_endpoint=" https://myres.cognitiveservices.azure.com ")
    assert s.azure_openai_base_url == "https://myres.cognitiveservices.azure.com/openai/v1/"


# ------------------------------------------------------------------ cost

def test_cost_uses_each_models_rates():
    u = llm.Usage(input_uncached=1_000_000, cache_read=1_000_000)
    assert llm.cost_usd("claude-opus-5", u) == pytest.approx(5.0 + 0.5)
    assert llm.cost_usd("claude-sonnet-5-5", u) == pytest.approx(2.0 + 0.2)
    assert llm.cost_usd("claude-opus-5-5", u) == pytest.approx(4.0 + 0.2)        # 0.05x cache reads
    assert llm.cost_usd("jobreach-sonnet-5.5", u) == pytest.approx(2.0 + 0.2)    # deployment name
    assert llm.cost_usd("gpt-6.1-sol", u) == pytest.approx(2.0 + 0.1)            # $0.10 cached input
    assert llm.cost_usd("gpt-6-luna", u) == pytest.approx(0.10 + 0.01)
    assert llm.cost_usd("claude-haiku-4-5", llm.Usage(output=1_000_000)) == pytest.approx(5.0)
    assert llm.cost_usd("claude-sonnet-5-5", llm.Usage(cache_write=1_000_000)) == pytest.approx(2.5)
    assert llm.cost_usd("gpt-6.1-sol", llm.Usage(cache_write=1_000_000)) == pytest.approx(2.0)


# ------------------------------------------------------------------ S7 rewrite loop

def _write(fake_outputs, fake):
    c = fake(fake_outputs)
    ex = Extracted(title="Backend Intern", company_name="Acme Labs", poster_name="Priya", poster_type="employee",
                   stipend=Stipend(stated="figure"), discipline="backend")
    sel = Selection(role_title="Backend Intern", summary="",
                    left_sections=[SectionSel(heading="Projects", item_keys=["queuekit"])],
                    bullet_ids=[], lead_with="QueueKit")
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
