from app.core.settings import settings

def test_settings_loaded_correctly():
    """Verifica que las variables de configuración carguen valores por defecto coherentes."""
    assert settings.APP_NAME == "Plan Review AI Hybrid"
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.DEFAULT_RENDER_DPI == 300
    assert 0.0 < settings.UNCERTAINTY_MIN_CONF < settings.UNCERTAINTY_MAX_CONF < 1.0
