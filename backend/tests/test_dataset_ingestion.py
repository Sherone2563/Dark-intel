from app.services.dataset_ingestion import parse_jsonl_lines


def test_valid_jsonl_records_are_parsed():
    result = parse_jsonl_lines(
        [
            '{"payload":{"handle":"shadow_x"}}',
            '{"payload":{"handle":"shadowx"},"processing_version":"0.2.0"}',
        ]
    )

    assert result.accepted_count == 2
    assert result.rejected_count == 0
    assert result.records[0].record.payload == {"handle": "shadow_x"}
    assert result.records[1].record.processing_version == "0.2.0"


def test_malformed_record_does_not_block_later_records():
    result = parse_jsonl_lines(
        [
            '{"payload":{"handle":"shadow_x"}}',
            '{"payload":',
            '{"payload":{"handle":"shadowx"}}',
        ]
    )

    assert result.accepted_count == 2
    assert result.rejected_count == 1
    assert result.errors[0].line_number == 2


def test_non_object_json_is_rejected():
    result = parse_jsonl_lines(
        [
            '["not", "an", "object"]',
            '"not an object"',
            "42",
            "null",
        ]
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 4


def test_missing_payload_is_rejected():
    result = parse_jsonl_lines(
        ['{"handle":"shadow_x"}']
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 1


def test_unknown_fields_are_rejected():
    result = parse_jsonl_lines(
        [
            '{"payload":{"handle":"shadow_x"},"unexpected":true}'
        ]
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 1


def test_naive_timestamps_are_rejected():
    result = parse_jsonl_lines(
        [
            (
                '{"payload":{"handle":"shadow_x"},'
                '"observed_at":"2026-10-19T10:00:00"}'
            )
        ]
    )

    assert result.accepted_count == 0
    assert result.rejected_count == 1


def test_timezone_aware_timestamps_are_accepted():
    result = parse_jsonl_lines(
        [
            (
                '{"payload":{"handle":"shadow_x"},'
                '"observed_at":"2026-10-19T10:00:00Z"}'
            )
        ]
    )

    assert result.accepted_count == 1
    assert result.rejected_count == 0
    assert result.records[0].record.observed_at is not None


def test_blank_lines_are_ignored():
    result = parse_jsonl_lines(
        [
            "",
            "   ",
            '{"payload":{"handle":"shadow_x"}}',
        ]
    )

    assert result.accepted_count == 1
    assert result.rejected_count == 0

def test_original_line_numbers_survive_blank_and_invalid_lines():
    result = parse_jsonl_lines(
        [
            "",
            '{"payload":{"handle":"shadow_x"}}',
            '{"payload":',
            '{"payload":{"handle":"shadowx"}}',
        ]
    )

    assert [item.line_number for item in result.records] == [2, 4]
    assert [item.line_number for item in result.errors] == [3]