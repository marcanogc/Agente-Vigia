import sentinel
import sentinel.database
import sentinel.models
import sentinel.audit
import sentinel.insight
import sentinel.dashboard

def test_imports():
    assert sentinel.__version__ == "1.0.0"
    print("Todos los módulos de Agente Vigía importados correctamente.")
