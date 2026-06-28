import pandas as pd
import matplotlib.pyplot as plt

# Загрузка и подготовка метрик
metrics = pd.read_csv('metrics.csv')
metrics['Time'] = pd.to_datetime(metrics['Time'], format='%H:%M:%S')
metrics['CPU_val'] = metrics['CPU'].str.rstrip('%').astype(float)
metrics['Mem_val'] = metrics['MemPerc'].str.rstrip('%').astype(float)

# Данные из pcap (ваши временные метки)
test_starts = {
    "short_polling": {1: "20:17:11", 10: "20:18:46", 30: "20:20:20", 50: "20:21:55", 100: "20:23:29", 500: "20:25:04", 1000: "20:26:39"},
    "long_polling": {1: "20:17:42", 10: "20:19:17", 30: "20:20:52", 50: "20:22:26", 100: "20:24:01", 500: "20:25:36", 1000: "20:27:11"},
    "websocket": {1: "20:18:14", 10: "20:19:49", 30: "20:21:23", 50: "20:22:58", 100: "20:24:33", 500: "20:26:07", 1000: "20:27:42"}
}

test_duration = 30 
results = []

for method, clients_dict in test_starts.items():
    for clients, start_str in clients_dict.items():
        start_time = pd.to_datetime(start_str, format='%H:%M:%S')
        end_time = start_time + pd.Timedelta(seconds=test_duration)
        mask = (metrics['Time'] >= start_time) & (metrics['Time'] <= end_time)
        results.append({
            'Method': method, 'Clients': clients, 
            'CPU': metrics.loc[mask, 'CPU_val'].mean(),
            'Memory': metrics.loc[mask, 'Mem_val'].mean()
        })

df = pd.DataFrame(results)

# Построение графиков
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 12))

for method in df['Method'].unique():
    subset = df[df['Method'] == method].sort_values('Clients')
    ax1.plot(subset['Clients'], subset['CPU'], marker='o', label=method)
    ax2.plot(subset['Clients'], subset['Memory'], marker='o', label=method)

ax1.set_title('Нагрузка на CPU')
ax1.set_ylabel('Средний CPU (%)')
ax1.legend()
ax1.grid(True)

ax2.set_title('Использование оперативной памяти (RAM)')
ax2.set_ylabel('Среднее Memory (%)')
ax2.set_xlabel('Количество клиентов')
ax2.legend()
ax2.grid(True)

plt.tight_layout()
plt.show()