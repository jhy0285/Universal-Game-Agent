from fastapi import FastAPI

from uga import __version__
from uga.capabilities import capabilities
from uga.core.contracts import CONTRACTS


def create_app() -> FastAPI:
    app = FastAPI(title="Universal Game Agent", version=__version__)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    @app.get("/api/v1/capabilities")
    def get_capabilities():
        return capabilities()

    @app.get("/api/v1/contracts")
    def contracts():
        return {model.__name__: model.model_json_schema() for model in CONTRACTS}

    return app
