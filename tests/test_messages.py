from __future__ import annotations

import json

import pytest

from kelvin.messages import (
    CATALOG,
    CONFIG_CACHE_DIR_INVALID,
    CONFIG_CASES_INVALID,
    CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID,
    CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING,
    CONFIG_DECISION_FIELD_INVALID,
    CONFIG_FILE_NOT_FOUND,
    CONFIG_GOVERNING_TYPES_INVALID,
    CONFIG_INTRA_SLOT_ENABLED_INVALID,
    CONFIG_INTRA_SLOT_FAMILIES_INVALID,
    CONFIG_INTRA_SLOT_MARKERS_INVALID,
    CONFIG_INTRA_SLOT_NOT_MAPPING,
    CONFIG_INTRA_SLOT_WHITELIST_INVALID,
    CONFIG_MISSING_KEYS,
    CONFIG_NOISE_FLOOR_ENABLED_INVALID,
    CONFIG_NOISE_FLOOR_NOT_MAPPING,
    CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID,
    CONFIG_NOT_MAPPING,
    CONFIG_RUN_INVALID,
    CONFIG_RUN_MISSING_PLACEHOLDERS,
    CONFIG_SEED_INVALID,
    CONFIG_TIMEOUT_INVALID,
    CONFIG_UNKNOWN_GOVERNING_TYPE,
    CONFIG_YAML_PARSE_ERROR,
    RETRY_GIVING_UP,
    RETRY_TRANSIENT_DETECTED,
    RUNNER_DECISION_FIELD_MISSING,
    RUNNER_OUTPUT_NOT_JSON,
    RUNNER_TIMEOUT,
    FormattedMessage,
    MessageTemplate,
    UnknownMessageIdError,
    catalog,
)


# ─── Snapshot: lock the set of entry IDs ──────────────────────────────────
# Commit 2 expands the catalog to cover all config.py raises. Adding or
# removing an entry is intentional and must update this snapshot in the
# same commit. This is the ratchet that keeps the catalog honest.

EXPECTED_ENTRY_IDS: frozenset[str] = frozenset({
    # config
    "config.file_not_found",
    "config.yaml_parse_error",
    "config.not_mapping",
    "config.missing_keys",
    "config.run_invalid",
    "config.run_missing_placeholders",
    "config.cases_invalid",
    "config.decision_field_invalid",
    "config.governing_types_invalid",
    "config.seed_invalid",
    "config.cache_dir_invalid",
    "config.timeout_invalid",
    "config.unknown_governing_type",
    "config.noise_floor_not_mapping",
    "config.noise_floor_enabled_invalid",
    "config.noise_floor_replications_invalid",
    "config.counterfactual_swap_not_mapping",
    "config.counterfactual_swap_enabled_invalid",
    "config.intra_slot_not_mapping",
    "config.intra_slot_enabled_invalid",
    "config.intra_slot_families_invalid",
    "config.intra_slot_markers_invalid",
    "config.intra_slot_whitelist_invalid",
    # runner
    "runner.timeout",
    "runner.output_not_json",
    "runner.decision_field_missing",
    # retry
    "retry.transient_detected",
    "retry.giving_up",
})


class TestCatalogSnapshot:
    def test_catalog_ids_match_snapshot_exactly(self) -> None:
        actual = frozenset(CATALOG.keys())
        missing = EXPECTED_ENTRY_IDS - actual
        extra = actual - EXPECTED_ENTRY_IDS
        assert not missing, f"missing from catalog: {sorted(missing)}"
        assert not extra, (
            f"unexpected in catalog: {sorted(extra)} — update "
            f"EXPECTED_ENTRY_IDS if intentional"
        )

    def test_every_entry_id_matches_its_dict_key(self) -> None:
        for key, template in CATALOG.items():
            assert template.id == key, (
                f"catalog key {key!r} does not match template.id "
                f"{template.id!r}"
            )

    def test_every_entry_has_nonempty_fields(self) -> None:
        for entry in CATALOG.values():
            assert entry.what.strip(), f"{entry.id}: empty `what`"
            assert entry.why.strip(), f"{entry.id}: empty `why`"
            assert entry.how_to_fix.strip(), f"{entry.id}: empty `how_to_fix`"


class TestFormat:
    def test_substitutes_params(self) -> None:
        msg = catalog(CONFIG_FILE_NOT_FOUND, path="/tmp/kelvin.yaml")
        assert "/tmp/kelvin.yaml" in msg.what

    def test_preserves_params_in_formatted_message(self) -> None:
        msg = catalog(CONFIG_MISSING_KEYS, path="x", missing="['run']")
        assert msg.params == {"path": "x", "missing": "['run']"}

    def test_missing_param_raises_keyerror(self) -> None:
        with pytest.raises(KeyError):
            # CONFIG_FILE_NOT_FOUND requires `path` — intentional template
            # bug surfaces here, not at the user's terminal.
            catalog(CONFIG_FILE_NOT_FOUND)

    def test_literal_braces_in_template_survive_format(self) -> None:
        # CONFIG_RUN_MISSING_PLACEHOLDERS refers to literal {input}/{output}
        # placeholders in the user's run: template. The message body must
        # render them as literal text, not consume them as format params.
        msg = catalog(CONFIG_RUN_MISSING_PLACEHOLDERS)
        assert "{input}" in msg.why
        assert "{output}" in msg.why
        assert "{input}" in msg.how_to_fix
        assert "{output}" in msg.how_to_fix


class TestUnknownId:
    def test_catalog_helper_raises_on_unknown_id(self) -> None:
        with pytest.raises(UnknownMessageIdError) as excinfo:
            catalog("no.such.id")
        assert "no.such.id" in str(excinfo.value)

    def test_unknown_message_error_lists_known_ids(self) -> None:
        with pytest.raises(UnknownMessageIdError) as excinfo:
            catalog("also.missing")
        # Informative: lists what *is* known so the user can fix the typo.
        assert "config.file_not_found" in str(excinfo.value)


class TestRendering:
    def test_as_text_contains_all_three_fields(self) -> None:
        msg = catalog(
            RETRY_GIVING_UP, context="case/pert-01", attempts=3
        )
        text = msg.as_text()
        assert msg.what in text
        assert msg.why in text
        assert msg.how_to_fix in text

    def test_as_dict_is_json_serializable(self) -> None:
        msg = catalog(
            CONFIG_UNKNOWN_GOVERNING_TYPE,
            unknown="['foo']",
            discovered="['gate_rule']",
        )
        d = msg.as_dict()
        encoded = json.dumps(d)
        decoded = json.loads(encoded)
        assert decoded["message_id"] == msg.id
        assert decoded["what"] == msg.what

    def test_as_dict_includes_params(self) -> None:
        msg = catalog(
            CONFIG_TIMEOUT_INVALID, value=0
        )
        assert msg.as_dict()["params"] == {"value": 0}


class TestImmutability:
    def test_message_template_is_frozen(self) -> None:
        t = CATALOG[CONFIG_FILE_NOT_FOUND]
        with pytest.raises((AttributeError, Exception)):
            t.what = "mutated"  # type: ignore[misc]

    def test_formatted_message_is_frozen(self) -> None:
        msg = catalog(CONFIG_FILE_NOT_FOUND, path="x")
        with pytest.raises((AttributeError, Exception)):
            msg.what = "mutated"  # type: ignore[misc]


class TestExportedConstantsCoverEveryEntry:
    """Every ID constant exported from kelvin.messages must appear in CATALOG.

    Catches the opposite of TestCatalogSnapshot: an exported constant that
    doesn't have a corresponding catalog entry.
    """

    EXPORTED_IDS = (
        CONFIG_FILE_NOT_FOUND,
        CONFIG_YAML_PARSE_ERROR,
        CONFIG_NOT_MAPPING,
        CONFIG_MISSING_KEYS,
        CONFIG_RUN_INVALID,
        CONFIG_RUN_MISSING_PLACEHOLDERS,
        CONFIG_CASES_INVALID,
        CONFIG_DECISION_FIELD_INVALID,
        CONFIG_GOVERNING_TYPES_INVALID,
        CONFIG_SEED_INVALID,
        CONFIG_CACHE_DIR_INVALID,
        CONFIG_TIMEOUT_INVALID,
        CONFIG_UNKNOWN_GOVERNING_TYPE,
        CONFIG_NOISE_FLOOR_NOT_MAPPING,
        CONFIG_NOISE_FLOOR_ENABLED_INVALID,
        CONFIG_NOISE_FLOOR_REPLICATIONS_INVALID,
        CONFIG_COUNTERFACTUAL_SWAP_NOT_MAPPING,
        CONFIG_COUNTERFACTUAL_SWAP_ENABLED_INVALID,
        CONFIG_INTRA_SLOT_NOT_MAPPING,
        CONFIG_INTRA_SLOT_ENABLED_INVALID,
        CONFIG_INTRA_SLOT_FAMILIES_INVALID,
        CONFIG_INTRA_SLOT_MARKERS_INVALID,
        CONFIG_INTRA_SLOT_WHITELIST_INVALID,
        RUNNER_TIMEOUT,
        RUNNER_OUTPUT_NOT_JSON,
        RUNNER_DECISION_FIELD_MISSING,
        RETRY_TRANSIENT_DETECTED,
        RETRY_GIVING_UP,
    )

    def test_every_exported_id_has_catalog_entry(self) -> None:
        for id_ in self.EXPORTED_IDS:
            assert id_ in CATALOG, f"exported id {id_!r} has no catalog entry"


def test_module_exposes_both_dataclasses() -> None:
    # Smoke check — callers should be able to type-annotate against these.
    assert MessageTemplate is not None
    assert FormattedMessage is not None
