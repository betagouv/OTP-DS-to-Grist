from queries_util import decode_base64_id


def test_decode_base64_id_valid():
    # ID encodé en Base64 pour "Champ-123"
    encoded = "Q2hhbXAtMTIz"  # base64.b64encode(b"Champ-123").decode()
    assert decode_base64_id(encoded) == "123"


def test_decode_base64_id_invalid():
    assert decode_base64_id("invalid") == "invalid"  # Fallback


def test_decode_base64_id_graphql():
    # Format GraphQL "Type:id"
    encoded = "Q2hhbXA6MTIz"  # "Champ:123"
    assert decode_base64_id(encoded) == "123"
