from dn.formatter import decode_base64_id


def test_decode_base64_id_valid():
    encoded = "Q2hhbXAtMTIz"  # base64.b64encode(b"Champ-123").decode()
    assert decode_base64_id(encoded) == "123"


def test_decode_base64_id_invalid():
    assert decode_base64_id("invalid") == "invalid"


def test_decode_base64_id_graphql():
    encoded = "Q2hhbXA6MTIz"  # "Champ:123"
    assert decode_base64_id(encoded) == "123"