"""Chat Service Tests"""
import pytest
from app.services.chat_service import chat_service

@pytest.mark.asyncio
async def test_process_query():
    result = await chat_service.process_query("How many sales documents?")
    assert "sql" in result
    assert "answer" in result
