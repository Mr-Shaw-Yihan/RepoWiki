from grainpipe.validate import validate_rows


def test_required_and_type_rules():
    stage = validate_rows({"order_id": {"required": True, "type": "int"}})
    rows = [{"order_id": "7"}, {"sku": "x"}, {"order_id": "abc"}]
    assert list(stage(rows)) == [{"order_id": 7}]
