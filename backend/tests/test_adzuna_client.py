import pytest
import httpx
from unittest.mock import MagicMock, patch
from app.clients.adzuna import AdzunaClient, AdzunaAPIError, get_adzuna_client

@pytest.fixture
def adzuna_client():
    return AdzunaClient()

@pytest.mark.asyncio
async def test_search_jobs_success(adzuna_client, mocker):
    # Mock response data
    mock_data = {
        "results": [
            {
                "title": "Software Engineer",
                "company": {"display_name": "Tech Corp"},
                "location": {"display_name": "San Francisco"},
                "description": "Develop cool stuff",
                "redirect_url": "https://example.com/job1"
            }
        ],
        "count": 1
    }
    
    # Mock httpx.AsyncClient.get
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        # Set dummy credentials for testing
        adzuna_client.app_id = "test-id"
        adzuna_client.app_key = "test-key"
        
        result = await adzuna_client.search_jobs(query="Software Engineer", location="San Francisco")
        
        assert "results" in result
        assert len(result["results"]) == 1
        assert result["results"][0]["title"] == "Software Engineer"

@pytest.mark.asyncio
async def test_search_jobs_missing_credentials(adzuna_client):
    adzuna_client.app_id = None
    adzuna_client.app_key = None
    
    with pytest.raises(ValueError, match="Adzuna API credentials not configured"):
        await adzuna_client.search_jobs(query="test")

@pytest.mark.asyncio
async def test_search_jobs_api_error(adzuna_client):
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        adzuna_client.app_id = "test-id"
        adzuna_client.app_key = "test-key"
        
        with pytest.raises(AdzunaAPIError, match="Adzuna API error: 500"):
            await adzuna_client.search_jobs(query="test")

@pytest.mark.asyncio
async def test_get_job_details_success(adzuna_client):
    mock_data = {"id": "123", "title": "Job 123"}
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_data
    
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        adzuna_client.app_id = "test-id"
        adzuna_client.app_key = "test-key"
        
        result = await adzuna_client.get_job_details(job_id="123")
        assert result["id"] == "123"

def test_get_adzuna_client_singleton():
    client1 = get_adzuna_client()
    client2 = get_adzuna_client()
    assert client1 is client2
