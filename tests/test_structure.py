import vigia
import vigia.database
import vigia.models
import vigia.audit
import vigia.insight
import vigia.dashboard

def test_imports():
    assert vigia.__version__ == "2.0.0"
    print("Todos los módulos de Agente Vigía importados correctamente.")
