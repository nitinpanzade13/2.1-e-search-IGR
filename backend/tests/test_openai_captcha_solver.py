import pytest
from unittest.mock import MagicMock, patch
import openai
from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver

def test_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENAI_API_KEY", "")
    with pytest.raises(ValueError, match="OpenAI API key is required"):
        OpenAICaptchaSolver()

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_successful_solve(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    
    choice1 = MagicMock()
    choice1.message.content = "abc1234" # 7 chars, ignored
    
    choice2 = MagicMock()
    choice2.message.content = "ABC123"
    
    choice3 = MagicMock()
    choice3.message.content = "ABC123"
    
    mock_response.choices = [choice1, choice2, choice3]
    mock_client.chat.completions.create.return_value = mock_response
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    # A valid image header or just random bytes to not crash PIL too hard, but PIL crash is handled
    result = solver.solve(b"fakeimage")
    assert result == "ABC123"

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_empty_image(mock_openai_class):
    solver = OpenAICaptchaSolver(api_key="test_key")
    with pytest.raises(ValueError, match="Empty image bytes"):
        solver.solve(b"")

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_malformed_response(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    choice = MagicMock()
    choice.message.content = "ABC" # 3 chars, ignored
    mock_response.choices = [choice, choice]
    mock_client.chat.completions.create.return_value = mock_response
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    with pytest.raises(ValueError, match="usable 6-character answers"):
        solver.solve(b"fakeimage")

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_authentication_failure(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    err = openai.AuthenticationError(message="bad auth", response=MagicMock(), body=None)
    mock_client.chat.completions.create.side_effect = err
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    with pytest.raises(ValueError, match="Authentication Error"):
        solver.solve(b"fakeimage")

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_network_failure(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    err = openai.APITimeoutError(request=MagicMock())
    mock_client.chat.completions.create.side_effect = err
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    with pytest.raises(RuntimeError, match="OpenAI API Error"):
        solver.solve(b"fakeimage")

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_model_configuration_used(mock_openai_class, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.OPENAI_CAPTCHA_MODEL", "custom-model-test")
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    choice1 = MagicMock()
    choice1.message.content = "123456"
    mock_response.choices = [choice1]
    mock_client.chat.completions.create.return_value = mock_response
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    solver.solve(b"fakeimage")
    
    # Assert custom model was passed
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "custom-model-test"

@patch("app.scraper.client.openai_captcha_solver.openai.OpenAI")
def test_image_preprocessing(mock_openai_class):
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    choice1 = MagicMock()
    choice1.message.content = "123456"
    mock_response.choices = [choice1]
    mock_client.chat.completions.create.return_value = mock_response
    
    # Real tiny PNG bytes
    valid_png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xef\x1f\x19\x00\x00\x00\x00IEND\xaeB`\x82'
    
    solver = OpenAICaptchaSolver(api_key="test_key")
    solver.solve(valid_png_bytes)
    
    call_kwargs = mock_client.chat.completions.create.call_args[1]
    messages = call_kwargs["messages"]
    assert len(messages) == 1
    content = messages[0]["content"]
    assert len(content) == 2
    
    image_url_obj = content[1]
    assert image_url_obj["type"] == "image_url"
    url_value = image_url_obj["image_url"]["url"]
    
    # Preprocessing should have output a valid PNG data URI
    assert url_value.startswith("data:image/png;base64,")
    
    # Ensure it's not exactly the original bytes, meaning preprocessing occurred
    import base64
    b64_data = url_value.split(",")[1]
    processed_bytes = base64.b64decode(b64_data)
    assert processed_bytes != valid_png_bytes
    assert processed_bytes.startswith(b'\x89PNG')
