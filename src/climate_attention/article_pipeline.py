"""Runnable article-level GDELT collection and release orchestration.

This module composes the existing bounded Web NGrams provider with GAL and GKG
inventory queries.  Every stage writes an atomic checkpoint and raw response
archive before normalized release data is produced.  A fake executor can be
passed in tests; the default path uses BigQuery Application Default Credentials.
"""

from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from datetime import date, datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence

from pydantic import Field

from .config import load_config, load_country_config, load_political_config
from .contracts import (
    Article,
    ArticleSourceSnapshot,
    ArticleTagAssertion,
    CaptureMembership,
    ClassificationCoverage,
    DailyMetric,
    EvaluationStatus,
    TagDefinition,
    TagEvidence,
)
from .gdelt_pipeline import (
    article_from_gal,
    article_identity,
    build_capture_manifest,
    build_capture_membership_digest,
    build_daily_metrics,
    build_gal_inventory_sql,
    build_gkg_enrichment_sql,
    normalize_url,
    resolve_tag_assertions,
    candidate_event_links,
)
from .models import CollectionRequest, StrictModel, Topic
from .panel import load_outlet_registry, resolve_outlet
from .registries import load_event_registry
from .sources.gdelt_ngrams import (
    GDELTNGramsProvider,
    BigQueryExecutor,
    plan_ngram_windows,
    topic_phrases,
)
from .sources.gdelt_ngrams import _json_safe_row as _safe_row


EVENT_CATEGORY_PHRASES: dict[str, list[dict[str, Any]]] = {
    "event_storm": [{"text": value, "language": "en", "segmentation": "space"} for value in ("storm", "storms", "severe storm", "windstorm")],
    "event_flood": [{"text": value, "language": "en", "segmentation": "space"} for value in ("flood", "flooding", "flash flood", "river flood")],
    "event_wildfire": [{"text": value, "language": "en", "segmentation": "space"} for value in ("wildfire", "wildfires", "forest fire", "grass fire")],
}

# GKG codes are candidate mappings only.  They remain insufficient evidence
# until project-specific review confirms that the extracted theme is relevant.
GKG_THEME_TAGS = {
    "ENV_CLIMATECHANGE": "climate_change",
    "ENV_CLIMATECHANGE_IMPACT": "climate_change",
    "TRANSPORTATION": "clean_transport",
    "TRANSPORT_ELECTRIC": "electric_vehicles",
    "ECON_PRICES": "cost_of_living",
}


class ArticlePipelineExecutor(Protocol):
    def estimate(self, sql: str, parameters: dict[str, Any]) -> int: ...
    def query(self, sql: str, parameters: dict[str, Any], *, maximum_bytes_billed: int) -> tuple[list[dict[str, Any]], dict[str, Any]]: ...


class StageState(StrictModel):
    status: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    records: int = 0
    estimated_bytes: int | None = None
    actual_bytes: int | None = None
    error: str | None = None


class ArticlePipelineRun(StrictModel):
    state_version: int = 1
    run_id: str
    source: str = "gdelt_article_pipeline"
    status: str = "planned"
    requested_start: date
    requested_end: date
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    configuration_hash: str
    outlet_registry_version: str
    stages: dict[str, StageState] = Field(default_factory=lambda: {
        "inventory": StageState(), "evidence": StageState(), "gkg": StageState(),
        "normalize": StageState(), "validate": StageState(),
    })
    output_path: str | None = None
    error: str | None = None


class AtomicPipelineStore:
    def __init__(self, root: str | Path = "data") -> None:
        self.root = Path(root) / "gdelt_article_runs"

    def path(self, run_id: str) -> Path:
        if not run_id or Path(run_id).name != run_id:
            raise ValueError("invalid article pipeline run id")
        return self.root / run_id / "state.json"

    def save(self, state: ArticlePipelineRun) -> Path:
        path = self.path(state.run_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
        return path

    def load(self, run_id: str) -> ArticlePipelineRun:
        return ArticlePipelineRun.model_validate_json(self.path(run_id).read_text(encoding="utf-8"))


def prepare_gal_inventory_query(
    *, start: date, end: date, outlet_domains: Sequence[str],
    gal_table: str = "gdelt-bq.gdeltv2.gal",
) -> tuple[str, dict[str, Any]]:
    """Build a bounded inventory query for the reviewed outlet universe."""
    sql = build_gal_inventory_sql(gal_table=gal_table) + "\n  AND LOWER(domain) IN UNNEST(@outlet_domains)"
    return sql, {"start_date": start, "end_date": end, "languages": ["en"], "outlet_domains": sorted({item.lower().lstrip(".") for item in outlet_domains})}


def prepare_gkg_query(
    *, start: date, end: date, article_urls: Sequence[str],
    gkg_table: str = "gdelt-bq.gdeltv2.gkg_partitioned",
) -> tuple[str, dict[str, Any]]:
    sql = build_gkg_enrichment_sql(gkg_table=gkg_table)
    # The appended predicate must be inside the WHERE clause.  Keep the SQL
    # builder readable while ensuring URL filtering happens before aggregation.
    sql = sql.replace("  AND DocumentIdentifier IS NOT NULL", "  AND DocumentIdentifier IS NOT NULL\n  AND DocumentIdentifier IN UNNEST(@article_urls)")
    return sql, {"start_date": start, "end_date": end, "article_urls": list(article_urls)}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _configuration_hash(paths: Sequence[str | Path]) -> str:
    payload = "\n".join(f"{Path(path).name}:{sha256(Path(path).read_bytes()).hexdigest()}" for path in paths)
    return sha256(payload.encode("utf-8")).hexdigest()


def _configuration_hashes(paths: Sequence[str | Path]) -> dict[str, str]:
    return {Path(path).name: sha256(Path(path).read_bytes()).hexdigest() for path in paths}


def _archive(archive_dir: Path, name: str, payload: Any) -> dict[str, Any]:
    path = archive_dir / name
    _write_json(path, payload)
    raw = path.read_bytes()
    return {"path": str(path), "sha256": sha256(raw).hexdigest(), "bytes": len(raw)}


def _write_parquet_bundle(root: Path, tables: Mapping[str, Sequence[Mapping[str, Any]]]) -> list[str]:
    """Write immutable article-level Parquet snapshots for analytical reuse."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    outputs: list[str] = []
    for name, rows in tables.items():
        path = root / f"{name}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        table = pa.Table.from_pylist([dict(row) for row in rows])
        temporary = path.with_suffix(".parquet.tmp")
        pq.write_table(table, temporary, compression="zstd")
        os.replace(temporary, path)
        outputs.append(str(path))
    return outputs


def _stage(state: ArticlePipelineRun, name: str, status: str, *, records: int = 0, estimated: int | None = None, actual: int | None = None, error: str | None = None) -> None:
    stage = state.stages[name]
    now = datetime.now(timezone.utc)
    if status == "running": stage.started_at = now
    if status in {"success", "failed", "partial"}: stage.finished_at = now
    stage.status = status; stage.records = records; stage.estimated_bytes = estimated; stage.actual_bytes = actual; stage.error = error
    state.updated_at = now


def _topic_catalog(topics: Sequence[Topic], *, catalog_version: str) -> list[TagDefinition]:
    definitions = [TagDefinition(
        tag_id=topic.id, label=topic.label, family="theme", definition=topic.description or topic.label,
        aliases=[], phrases=[phrase.text for phrase in topic.ngram_phrases], catalog_version=catalog_version,
    ) for topic in topics]
    definitions.extend(TagDefinition(
        tag_id=tag_id, label=tag_id.replace("event_", "").replace("_", " ").title(), family="event_category",
        definition="Independent broad event-category candidate; requires hazard context review.",
        phrases=[phrase["text"] for phrase in phrases], catalog_version=catalog_version,
    ) for tag_id, phrases in EVENT_CATEGORY_PHRASES.items())
    return definitions


def _sample_to_article(sample: Any, inventory: Mapping[str, Article]) -> Article:
    canonical = normalize_url(sample.url)
    existing = inventory.get(canonical)
    if existing:
        return existing
    return Article(
        article_id=article_identity(canonical), canonical_url=canonical, raw_urls=[sample.url],
        outlet_domain=sample.domain, language=sample.language, first_seen_at=sample.published_at,
        source_date=sample.published_at, published_at=sample.published_at,
        date_basis="published_at" if sample.published_at else "unknown", title=sample.title,
        description=sample.description,
    )


def _assertions_from_samples(samples: Iterable[Any], inventory: dict[str, Article], evidence: list[TagEvidence], *, tagging_version: str) -> list[ArticleTagAssertion]:
    assertions: list[ArticleTagAssertion] = []
    for sample in samples:
        article = _sample_to_article(sample, inventory)
        inventory[article.canonical_url] = article
        for offset, item in enumerate(sample.match_evidence):
            evidence_id = "ev_" + sha256(f"{article.article_id}:{sample.topic_id}:{offset}:{item.phrase}".encode()).hexdigest()[:24]
            evidence.append(TagEvidence(
                evidence_id=evidence_id, article_id=article.article_id, source="webngrams",
                source_record_id=sample.record_id, phrase=item.phrase, context=item.context,
                source_field="pre_ngram_post", captured_at=sample.collected_at,
                metadata={"topic_id": sample.topic_id, "evidence_kind": item.evidence_kind, "language": item.phrase_language},
            ))
            assertions.append(ArticleTagAssertion(
                article_id=article.article_id, tag_id=sample.topic_id, method="phrase",
                assertion_type="mentions_theme", result="present", evaluation_status=EvaluationStatus.evaluated,
                tagging_version=tagging_version, evidence_ids=[evidence_id], rule_hash=sha256(item.phrase.encode()).hexdigest(),
            ))
        if not sample.match_evidence:
            assertions.append(ArticleTagAssertion(
                article_id=article.article_id, tag_id=sample.topic_id, method="phrase",
                assertion_type="mentions_theme", result="present", evaluation_status=EvaluationStatus.evaluated,
                tagging_version=tagging_version, rule_hash=sha256(sample.topic_id.encode()).hexdigest(),
            ))
    return assertions


def _gkg_evidence(rows: Iterable[Mapping[str, Any]], articles: Mapping[str, Article]) -> list[TagEvidence]:
    result: list[TagEvidence] = []
    for row in rows:
        raw_url = str(row.get("url") or "")
        if not raw_url: continue
        try: article_id = articles[normalize_url(raw_url)].article_id
        except KeyError: continue
        for field in ("persons", "organisations", "locations", "theme_codes"):
            for value in row.get(field) or []:
                token = str(value).strip()
                if not token: continue
                result.append(TagEvidence(
                    evidence_id="gkg_" + sha256(f"{article_id}:{field}:{token}".encode()).hexdigest()[:24],
                    article_id=article_id, source="gkg", source_record_id=raw_url,
                    context=token, source_field=field, metadata={"gkg_candidate": True},
                ))
    return result


def _gkg_candidate_assertions(
    evidence: Iterable[TagEvidence], *, tagging_version: str,
) -> list[ArticleTagAssertion]:
    assertions: list[ArticleTagAssertion] = []
    for item in evidence:
        if item.source_field != "theme_codes":
            continue
        tag_id = GKG_THEME_TAGS.get(item.context or "")
        if not tag_id:
            continue
        assertions.append(ArticleTagAssertion(
            article_id=item.article_id, tag_id=tag_id, method="gkg",
            assertion_type="mentions_theme", result="present",
            evaluation_status=EvaluationStatus.insufficient_evidence,
            tagging_version=tagging_version, evidence_ids=[item.evidence_id],
            rule_hash=sha256((item.context or "").encode()).hexdigest(),
        ))
    return assertions


def estimate_article_pipeline(*, start: date, end: date, billing_project: str, maximum_bytes_billed: int, config_path: str | Path = "config/topics.uk-pilot.yaml", country_config_path: str | Path = "config/countries.uk-pilot.yaml", outlet_registry_path: str | Path = "config/outlet_registry.yaml", executor: ArticlePipelineExecutor | None = None, window_days: int = 3) -> dict[str, Any]:
    """Dry-run all query shapes and return byte estimates without execution."""
    if maximum_bytes_billed <= 0: raise ValueError("maximum_bytes_billed must be greater than zero")
    topics_cfg = load_config(config_path); countries = load_country_config(country_config_path); outlets = load_outlet_registry(outlet_registry_path)
    executor = executor or __import__("climate_attention.sources.gdelt_ngrams", fromlist=["GoogleBigQueryExecutor"]).GoogleBigQueryExecutor(project=billing_project)
    domains = [outlet.domain for outlet in outlets if outlet.source_class == "news"] + [alias for outlet in outlets for alias in outlet.domain_aliases]
    inv_sql, inv_params = prepare_gal_inventory_query(start=start, end=end, outlet_domains=domains)
    inventory_bytes = executor.estimate(inv_sql, inv_params)
    selected = topics_cfg.enabled_topics(); request = CollectionRequest(start=start, end=end, topics=selected)
    windows, phrases = plan_ngram_windows(request, window_days=window_days)
    political = load_political_config(Path(config_path).with_name("political_signals.uk-pilot.yaml"))
    country_labels = {country.id: country.ngram_label for country in countries.enabled_countries({"unitedkingdom"})}
    provider = GDELTNGramsProvider(billing_project=billing_project, country_labels=country_labels, topic_phrases={**phrases, **EVENT_CATEGORY_PHRASES}, maximum_bytes_billed=maximum_bytes_billed, political_signals=political.phrase_mapping(), official_domains=political.official_domains, article_sample_size=-1, executor=executor)
    ngram_estimates = []
    for window in windows:
        selected_phrases = provider.topic_phrases
        sql, params = __import__("climate_attention.sources.gdelt_ngrams", fromlist=["prepare_ngram_batch_query"]).prepare_ngram_batch_query(window, phrases_by_topic=selected_phrases, country_labels=country_labels, political_signals=political.phrase_mapping(), official_domains=political.official_domains, article_sample_size=-1)
        ngram_estimates.append({"window_id": window.window_id, "estimated_bytes": executor.estimate(sql, params)})
    return {"status": "planned", "inventory_estimated_bytes": inventory_bytes, "ngram_windows": ngram_estimates, "max_bytes_per_query": maximum_bytes_billed, "billable": False}


def run_article_pipeline(*, start: date, end: date, billing_project: str, maximum_bytes_billed: int, run_id: str, config_path: str | Path = "config/topics.uk-pilot.yaml", country_config_path: str | Path = "config/countries.uk-pilot.yaml", outlet_registry_path: str | Path = "config/outlet_registry.yaml", data_root: str | Path = "data", executor: ArticlePipelineExecutor | None = None, window_days: int = 3, gkg_enabled: bool = True, max_total_bytes: int | None = None) -> Path:
    """Execute all stages and write an immutable article-level release bundle."""
    if maximum_bytes_billed <= 0: raise ValueError("maximum_bytes_billed must be greater than zero")
    root = Path(data_root); run_dir = root / "gdelt_article_runs" / run_id; archive = run_dir / "raw"; archive.mkdir(parents=True, exist_ok=True)
    topics_cfg = load_config(config_path); countries = load_country_config(country_config_path); outlets = load_outlet_registry(outlet_registry_path); political = load_political_config("config/political_signals.uk-pilot.yaml")
    event_registry_path = Path(config_path).with_name("events.uk-pilot.yaml")
    political_config_path = Path(config_path).with_name("political_signals.uk-pilot.yaml")
    config_paths = [config_path, country_config_path, outlet_registry_path, political_config_path]
    if event_registry_path.exists(): config_paths.append(event_registry_path)
    store = AtomicPipelineStore(root)
    existing: ArticlePipelineRun | None = None
    if store.path(run_id).exists():
        existing = store.load(run_id)
        if existing.status == "success" and existing.output_path and Path(existing.output_path).exists():
            return Path(existing.output_path)
    state = existing or ArticlePipelineRun(run_id=run_id, requested_start=start, requested_end=end, configuration_hash=_configuration_hash(config_paths), outlet_registry_version="uk-outlets-v1")
    if state.configuration_hash != _configuration_hash(config_paths):
        raise ValueError("run ID already exists with a different configuration")
    store.save(state); state.status = "running"; state.error = None; store.save(state)
    for source_path in config_paths:
        destination = run_dir / "config" / Path(source_path).name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, destination)
    spent_bytes = 0
    try:
        # Inventory
        _stage(state, "inventory", "running"); store.save(state)
        domains = [outlet.domain for outlet in outlets if outlet.source_class == "news"] + [alias for outlet in outlets for alias in outlet.domain_aliases]
        inv_sql, inv_params = prepare_gal_inventory_query(start=start, end=end, outlet_domains=domains)
        executor = executor or __import__("climate_attention.sources.gdelt_ngrams", fromlist=["GoogleBigQueryExecutor"]).GoogleBigQueryExecutor(project=billing_project)
        estimate = executor.estimate(inv_sql, inv_params)
        if estimate > maximum_bytes_billed: raise ValueError(f"GAL inventory dry run estimated {estimate} bytes, above cap {maximum_bytes_billed}")
        if max_total_bytes is not None and estimate > max_total_bytes: raise ValueError("cumulative byte budget exceeded by GAL inventory dry run")
        inv_rows, inv_job = executor.query(inv_sql, inv_params, maximum_bytes_billed=maximum_bytes_billed)
        spent_bytes += int(inv_job.get("total_bytes_billed", inv_job.get("total_bytes_processed", estimate)))
        _archive(archive, "gal_inventory.json", {"query": inv_sql, "parameters": inv_params, "job": inv_job, "rows": [_safe_row(row) for row in inv_rows]})
        inventory: dict[str, Article] = {}; memberships: list[CaptureMembership] = []
        for row in inv_rows:
            article = article_from_gal(row); matched_outlet = resolve_outlet(article.outlet_domain or "", outlets)
            if matched_outlet is None: continue
            article = article.model_copy(update={"outlet_id": matched_outlet.outlet_id, "publishing_geography": matched_outlet.publishing_geography, "source_class": matched_outlet.source_class})
            inventory[article.canonical_url] = article
            seen = article.first_seen_at.date() if article.first_seen_at else start
            memberships.append(CaptureMembership(snapshot_id=run_id, article_id=article.article_id, reporting_day=max(start, min(end, seen))))
        _stage(state, "inventory", "success", records=len(inventory), estimated=estimate, actual=int(inv_job.get("total_bytes_billed", inv_job.get("total_bytes_processed", 0)))); store.save(state)

        # Phrase evidence and event categories
        _stage(state, "evidence", "running"); store.save(state)
        selected = topics_cfg.enabled_topics(); request = CollectionRequest(start=start, end=end, topics=selected); windows, phrases = plan_ngram_windows(request, window_days=window_days)
        country_labels = {country.id: country.ngram_label for country in countries.enabled_countries({"unitedkingdom"})}
        response_files: list[dict[str, Any]] = []
        samples: list[Any] = []
        def response_sink(payload: dict[str, Any]) -> None:
            response_files.append(_archive(archive, f"ngrams_{payload['window_id']}.json", payload))
        def timeline_sink(event: str, window: Any, log: Any, records: list[Any], children: list[Any]) -> None:
            if event == "success": samples.extend([item for item in records if hasattr(item, "url")])
        provider = GDELTNGramsProvider(billing_project=billing_project, country_labels=country_labels, topic_phrases={**phrases, **EVENT_CATEGORY_PHRASES}, maximum_bytes_billed=maximum_bytes_billed, political_signals=political.phrase_mapping(), official_domains=political.official_domains, article_sample_size=-1, executor=executor, response_sink=response_sink, timeline_sink=timeline_sink)
        if max_total_bytes is not None:
            ngram_estimates = sum(item.get("estimated_bytes", 0) for item in estimate_article_pipeline(start=start, end=end, billing_project=billing_project, maximum_bytes_billed=maximum_bytes_billed, config_path=config_path, country_config_path=country_config_path, outlet_registry_path=outlet_registry_path, executor=executor, window_days=window_days).get("ngram_windows", []))
            if spent_bytes + ngram_estimates > max_total_bytes: raise ValueError("cumulative byte budget exceeded by NGrams dry run")
        result = provider.collect_windows(windows)
        spent_bytes += sum(int(json.loads((archive / Path(item["path"]).name).read_text()).get("job", {}).get("total_bytes_billed", 0)) for item in response_files)
        evidence: list[TagEvidence] = []; assertions = _assertions_from_samples(samples, inventory, evidence, tagging_version="gdelt-article-v1")
        _stage(state, "evidence", "success", records=len(assertions), actual=sum(int(item.get("total_bytes_billed", item.get("total_bytes_processed", 0))) for item in [json.loads((archive / Path(item["path"]).name).read_text()).get("job", {}) for item in response_files])); store.save(state)

        # GKG evidence is optional but still explicit in the release when unavailable.
        gkg_rows: list[dict[str, Any]] = []; gkg_job: dict[str, Any] = {}
        _stage(state, "gkg", "running"); store.save(state)
        if gkg_enabled and inventory:
            gkg_sql, gkg_params = prepare_gkg_query(start=start, end=end, article_urls=list(inventory))
            gkg_estimate = executor.estimate(gkg_sql, gkg_params)
            if gkg_estimate > maximum_bytes_billed: raise ValueError(f"GKG dry run estimated {gkg_estimate} bytes, above cap {maximum_bytes_billed}")
            if max_total_bytes is not None and spent_bytes + gkg_estimate > max_total_bytes: raise ValueError("cumulative byte budget exceeded by GKG dry run")
            gkg_rows, gkg_job = executor.query(gkg_sql, gkg_params, maximum_bytes_billed=maximum_bytes_billed)
            spent_bytes += int(gkg_job.get("total_bytes_billed", gkg_job.get("total_bytes_processed", gkg_estimate)))
            _archive(archive, "gkg_enrichment.json", {"query": gkg_sql, "parameters": gkg_params, "job": gkg_job, "rows": [_safe_row(row) for row in gkg_rows]})
            gkg_evidence = _gkg_evidence(gkg_rows, inventory)
            evidence.extend(gkg_evidence)
            assertions.extend(_gkg_candidate_assertions(gkg_evidence, tagging_version="gdelt-article-v1"))
        _stage(state, "gkg", "success", records=len(gkg_rows), actual=int(gkg_job.get("total_bytes_billed", gkg_job.get("total_bytes_processed", 0)))); store.save(state)

        # Normalize and aggregate one coherent release.
        _stage(state, "normalize", "running"); store.save(state)
        tags = resolve_tag_assertions(assertions, resolution_version="gdelt-resolution-v1")
        by_day: dict[date, set[str]] = defaultdict(set)
        for membership in memberships: by_day[membership.reporting_day].add(membership.article_id)
        metrics: list[DailyMetric] = []
        for day, article_ids in sorted(by_day.items()):
            for definition in _topic_catalog(selected, catalog_version="uk-pilot-v1"):
                metrics.extend(build_daily_metrics(release_id=run_id, reporting_day=day, universe_article_ids=article_ids, tags=tags, tag_id=definition.tag_id, tagging_version="gdelt-article-v1"))
        coverage = [ClassificationCoverage(article_id=article.article_id, tag_family="theme", evaluation_status=EvaluationStatus.evaluated if article.article_id in {tag.article_id for tag in tags} else EvaluationStatus.not_evaluated, available_text_scope="GAL metadata plus retained Web NGrams/GKG evidence", tagging_version="gdelt-article-v1") for article in inventory.values()]
        manifest = build_capture_manifest(snapshot_id=run_id, source="combined", requested_start=start, requested_end=end, memberships=memberships, outlet_registry_version="uk-outlets-v1")
        event_registry_path = Path(config_path).with_name("events.uk-pilot.yaml")
        event_registry_version, event_registry = load_event_registry(event_registry_path) if event_registry_path.exists() else ("events-v1", [])
        event_aliases = {event.event_id: [event.canonical_name, *event.aliases] for event in event_registry}
        article_event_links = []
        for article in inventory.values():
            text = " ".join(item for item in (article.title, article.description) if item)
            for event in event_registry:
                article_event_links.extend(candidate_event_links(article=article, aliases={event.event_id: event_aliases[event.event_id]}, text=text, event_type=event.event_type))
        retrieved_at = datetime.now(timezone.utc)
        source_snapshots = [ArticleSourceSnapshot(article_id=item.article_id, source="gal", retrieved_at=retrieved_at, status="available") for item in inventory.values()]
        ngram_article_ids = {item.article_id for item in assertions if item.method == "phrase"}
        source_snapshots.extend(ArticleSourceSnapshot(article_id=article_id, source="webngrams", retrieved_at=retrieved_at, status="available") for article_id in sorted(ngram_article_ids))
        gkg_article_ids = {item.article_id for item in evidence if item.source == "gkg"}
        source_snapshots.extend(ArticleSourceSnapshot(article_id=article_id, source="gkg", retrieved_at=retrieved_at, status="available" if gkg_enabled else "access_pending") for article_id in sorted(gkg_article_ids))
        output = {"release_id": run_id, "status": "candidate", "configuration_hash": state.configuration_hash, "configuration_files": _configuration_hashes(config_paths), "articles": [item.model_dump(mode="json") for item in inventory.values()], "article_source_snapshots": [item.model_dump(mode="json") for item in source_snapshots], "capture_membership": [item.model_dump(mode="json") for item in memberships], "capture_manifest": manifest.model_dump(mode="json"), "tag_catalog": [item.model_dump(mode="json") for item in _topic_catalog(selected, catalog_version="uk-pilot-v1")], "article_tag_assertions": [item.model_dump(mode="json") for item in assertions], "article_tags": [item.model_dump(mode="json") for item in tags], "tag_evidence": [item.model_dump(mode="json") for item in evidence], "classification_coverage": [item.model_dump(mode="json") for item in coverage], "daily_metrics": [item.model_dump(mode="json") for item in metrics], "events": [item.model_dump(mode="json") for item in event_registry], "article_event_links": [item.model_dump(mode="json") for item in article_event_links], "event_registry_version": event_registry_version, "source_jobs": {"gkg": gkg_job, "ngrams": [item.model_dump(mode="json") for item in result.requests]}, "raw_archives": response_files}
        parquet_outputs = _write_parquet_bundle(root / "processed" / f"gdelt-article-release-{run_id}", {
            "articles": output["articles"], "article_tags": output["article_tags"],
            "tag_evidence": output["tag_evidence"], "daily_metrics": output["daily_metrics"],
        })
        output["parquet_outputs"] = parquet_outputs
        output_path = root / "processed" / f"gdelt-article-release-{run_id}.json"; _write_json(output_path, output); state.output_path = str(output_path); _stage(state, "normalize", "success", records=len(inventory)); store.save(state)
        _stage(state, "validate", "running"); errors = validate_article_release(output); _stage(state, "validate", "success" if not errors else "failed", records=len(metrics), error="; ".join(errors) if errors else None); state.status = "success" if not errors else "failed"; state.error = "; ".join(errors) if errors else None; state.finished_at = datetime.now(timezone.utc); store.save(state)
        if errors: raise ValueError("article release validation failed: " + "; ".join(errors))
        return output_path
    except Exception as exc:
        state.status = "failed"; state.error = str(exc); state.finished_at = datetime.now(timezone.utc)
        for name, stage in state.stages.items():
            if stage.status == "running": _stage(state, name, "failed", error=str(exc))
        store.save(state); raise


def validate_article_release(data: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    articles = {item.get("article_id") for item in data.get("articles", [])}
    memberships = data.get("capture_membership", [])
    if len({(item.get("snapshot_id"), item.get("article_id"), item.get("reporting_day")) for item in memberships}) != len(memberships): errors.append("capture membership contains duplicate keys")
    if any(item.get("article_id") not in articles for item in memberships): errors.append("capture membership references unknown article")
    manifest = data.get("capture_manifest", {})
    if manifest.get("membership_digest") != build_capture_membership_digest([CaptureMembership.model_validate(item) for item in memberships]): errors.append("capture manifest digest does not match membership")
    for metric in data.get("daily_metrics", []):
        if metric.get("evaluable_count", 0) > metric.get("universe_count", 0): errors.append("metric evaluable count exceeds universe")
        if metric.get("positive_count", 0) > metric.get("evaluable_count", 0): errors.append("metric positive count exceeds evaluable")
    return sorted(set(errors))


def build_article_serving_payload(data: Mapping[str, Any]) -> dict[str, Any]:
    """Prepare a compact read-only payload for the existing serving path."""
    errors = validate_article_release(data)
    if errors:
        raise ValueError("cannot prepare an invalid article release: " + "; ".join(errors))
    return {
        "release_id": data.get("release_id"),
        "status": data.get("status"),
        "configuration_hash": data.get("configuration_hash"),
        "capture_manifest": data.get("capture_manifest", {}),
        "articles": data.get("articles", []),
        "article_tags": data.get("article_tags", []),
        "events": data.get("events", []),
        "article_event_links": data.get("article_event_links", []),
        "daily_metrics": data.get("daily_metrics", []),
        "source_jobs": data.get("source_jobs", {}),
    }
