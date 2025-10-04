from pkg.swagger.swagger import model_to_swagger_schema
from src.model.app import App

schemas = {
    "App": model_to_swagger_schema(App),
}

__all__ = ["schemas"]
