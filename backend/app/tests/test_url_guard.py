import pytest
from app.security.url_guard import validate_public_url, UnsafeURL
@pytest.mark.parametrize("url",["http://127.0.0.1","http://localhost","http://169.254.169.254/latest/meta-data","file:///etc/passwd"])
def test_blocks_private_destinations(url):
    with pytest.raises(UnsafeURL): validate_public_url(url)

def test_dead_public_hostname_can_be_saved_without_dns_resolution():
    from app.security.url_guard import validate_url_for_storage
    assert validate_url_for_storage("https://example.invalid") == "https://example.invalid"

def test_redirect_to_local_network_is_blocked():
    from app.security.url_guard import validate_redirect
    with pytest.raises(UnsafeURL): validate_redirect("https://example.com/shop","http://127.0.0.1/admin")
