from fastapi.testclient import TestClient

from src.api import main as api_main


class DummyVectorStore:
	pass


class DummyRetriever:
	def __init__(self, vector_store):
		self.vector_store = vector_store


class DummyIngestor:
	def __init__(self, retriever, vector_store):
		self.retriever = retriever
		self.vector_store = vector_store


class DummyOrchestrator:
	def __init__(self, retriever):
		self.retriever = retriever

	def run(self, query: str, thread_id: str, tenant_id: int | None = None) -> str:
		tenant_label = tenant_id if tenant_id is not None else "unknown"
		return f"echo:{query}|thread:{thread_id}|tenant:{tenant_label}"


def create_test_client(monkeypatch) -> TestClient:
	api_main.state.clear()
	monkeypatch.setattr(api_main, "init_database", lambda: None)
	monkeypatch.setattr(api_main, "VectorStore", DummyVectorStore)
	monkeypatch.setattr(api_main, "MultimodalRetriever", DummyRetriever)
	monkeypatch.setattr(api_main, "DocumentIngestor", DummyIngestor)
	monkeypatch.setattr(api_main, "PropertyOrchestrator", DummyOrchestrator)
	return TestClient(api_main.app)


def test_health_endpoint_reports_online(monkeypatch):
	with create_test_client(monkeypatch) as client:
		response = client.get("/health")

	assert response.status_code == 200
	assert response.json() == {"status": "online", "version": "1.0.0"}


def test_chat_endpoint_returns_orchestrator_response(monkeypatch):
	payload = {
		"message": "Hello",
		"thread_id": "test-thread",
		"tenant_id": 7,
	}

	with create_test_client(monkeypatch) as client:
		response = client.post("/chat", json=payload)

	assert response.status_code == 200
	assert response.json() == {
		"response": "echo:Hello|thread:test-thread|tenant:7",
		"thread_id": "test-thread",
	}
