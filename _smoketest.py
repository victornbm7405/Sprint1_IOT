from persistence import save_telemetria_file, list_telemetria_file
from types import SimpleNamespace
t = SimpleNamespace(id_moto=1, temp_c=36.5, vib=0.9, batt_pct=82.3)
print('novo id:', save_telemetria_file(t))
print('ultimos:', list_telemetria_file(3))
