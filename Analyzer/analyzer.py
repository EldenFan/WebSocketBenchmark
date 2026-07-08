from datetime import datetime
import json
import os
import subprocess
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def get_pcap_stats(pcap_file):
   cmd_size = ['tshark', '-r', pcap_file, '-T', 'fields', '-e', 'frame.len']
   total_bytes = 0
   try:
        result = subprocess.run(cmd_size, capture_output=True, text=True)
        if result.returncode == 0 or result.stdout:
            total_bytes = sum(int(line) for line in result.stdout.splitlines() if line)
   except Exception as e:
        print(f"Пропуск битого файла {pcap_file} при расчете размера: {e}")
        return 0, 0
   cmd_data = [
        "tshark", "-n", "-r", pcap_file, "-Y", "http.file_data || websocket.payload",
        "-T", "fields", "-e", "http.file_data", "-e", "websocket.payload"
    ]
   payload_bytes = 0
   try:
        result_data = subprocess.run(cmd_data, capture_output=True, text=True)
        if result_data.stdout:
            for line in result_data.stdout.splitlines():
                fields = line.split("\t")
                hex_data = fields[0] or fields[1]
                if hex_data:
                    # Корректная обработка hex-строки
                    clean_hex = hex_data.replace(":", "").strip()
                    payload_bytes += len(bytes.fromhex(clean_hex))
   except Exception as e:
        print(f"Ошибка при чтении данных из {pcap_file}: {e}")
        return total_bytes, 0
   
   return total_bytes, payload_bytes


def get_test_starts_from_pcaps(captures_dir):
    test_starts = {}
    for filename in os.listdir(captures_dir):
        if not filename.endswith('.pcap'):
            continue
        base = filename[:-5]
        parts = base.split('_')
        if len(parts) < 3:
            print(f"Пропускаем {filename}: не распознаётся имя")
            continue
        method = '_'.join(parts[:-2])
        clients = int(parts[-2])
        
        filepath = os.path.join(captures_dir, filename)
        delays = get_packet_delays(filepath)

        if delays:
            min_delay = min(delays)

            for i in range(len(delays)):
                delays[i] -= min_delay

            all_delays.append({
                "Method": method,
                "Clients": clients,
                "Run": run_idx,
                "Delay": sum(delays) / len(delays)
            })

        total, payload = get_pcap_stats(filepath)
        efficiency_data.append({
            'Method': method, 'Clients': clients,
            'Payload': payload, 'Overhead': total - payload
        })

        cmd = ['tshark', '-r', filepath, '-c', '1', '-T', 'fields', '-e', 'frame.time']
        try:
            output = subprocess.check_output(cmd, text=True).strip()
            if output:
                time_str = output
                match = re.search(r'(\d{2}:\d{2}:\d{2})', time_str)
                if match:
                    time_str = match.group(1)
                else:
                    time_str = time_str
            else:
                time_str = None
        except Exception as e:
            print(f"Ошибка при обработке {filename}: {e}")
            time_str = None
        
        if time_str:
            if method not in test_starts:
                test_starts[method] = {}
            test_starts[method][clients] = time_str
    
    return test_starts

def get_packet_delays(pcap_file):
    cmd = [
        "tshark",
        "-n",
        "-r", pcap_file,
        "-Y", "http.response || websocket",
        "-T", "fields",
        "-e", "frame.time_epoch",
        "-e", "http.file_data",
        "-e", "websocket.payload"
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        output = result.stdout
        if result.returncode != 0:
            print(f"Предупреждение при чтении {pcap_file} (код {result.returncode}): {result.stderr.strip()}")
    except Exception as e:
        print(e)
        return []

    if not output:
        return []

    delays = []
    for line in output.splitlines():
        if not line.strip():
            continue

        fields = line.split("\t")
        if len(fields) < 3:
            continue

        frame_epoch = fields[0]
        payload_hex = fields[1] or fields[2]
        if not payload_hex:
            continue

        try:
            payload = bytes.fromhex(payload_hex.replace(":", "")).decode("utf-8")
            obj = json.loads(payload)
            server_time = datetime.fromisoformat(obj["timeStamp"].replace("Z", "+00:00"))
            delay_ms = (float(frame_epoch) - server_time.timestamp()) * 1000
            delays.append(delay_ms)
        except Exception:
            continue

    return delays

script_dir = os.path.dirname(os.path.abspath(__file__))
test_duration = 30

all_results = []
all_delays = []
efficiency_data = []

for run_idx in range(5):
    captures_dir = os.path.join(script_dir, f"Captures ({run_idx})")
    test_starts = get_test_starts_from_pcaps(captures_dir)
    print(f"Run {run_idx}: получены времена старта:", test_starts)

    csv_path = os.path.join(captures_dir, "metrics.csv")
    metrics = pd.read_csv(csv_path)
    metrics['Time'] = pd.to_datetime(metrics['Time'], format='%H:%M:%S')
    metrics['CPU_val'] = metrics['CPU'].str.rstrip('%').astype(float)
    metrics['Mem_val'] = metrics['MemPerc'].str.rstrip('%').astype(float)

    for method, clients_dict in test_starts.items():
        for clients, start_str in clients_dict.items():
            start_time = pd.to_datetime(start_str, format='%H:%M:%S')
            end_time = start_time + pd.Timedelta(seconds=test_duration)
            mask = (metrics['Time'] >= start_time) & (metrics['Time'] <= end_time)
            cpu_mean = metrics.loc[mask, 'CPU_val'].mean()
            mem_mean = metrics.loc[mask, 'Mem_val'].mean()
            all_results.append({
                'Method': method,
                'Clients': clients,
                'CPU': cpu_mean,
                'Memory': mem_mean,
                'Run': run_idx
            })

df_all = pd.DataFrame(all_results)

grouped = df_all.groupby(['Method', 'Clients']).agg(
    cpu_mean=('CPU', 'mean'),
    cpu_std=('CPU', 'std'),
    mem_mean=('Memory', 'mean'),
    mem_std=('Memory', 'std')
).reset_index()

df_delay = pd.DataFrame(all_delays)

if df_delay.empty:
    print("Внимание: не удалось извлечь ни одной задержки из pcap-файлов.")
    delay_grouped = pd.DataFrame(columns=["Method", "Clients", "delay_mean", "delay_std"])
else:
    delay_grouped = (
        df_delay
        .groupby(["Method", "Clients"])
        .agg(delay_mean=("Delay", "mean"), delay_std=("Delay", "std"))
        .reset_index()
    )
    delay_grouped["delay_std"] = delay_grouped["delay_std"].fillna(0)

grouped['cpu_std'] = grouped['cpu_std'].fillna(0)
grouped['mem_std'] = grouped['mem_std'].fillna(0)

df_eff = pd.DataFrame(efficiency_data).groupby(['Method', 'Clients']).mean().reset_index()

fig1, ax1 = plt.subplots(figsize=(10, 6))
fig2, ax2 = plt.subplots(figsize=(10, 6))
fig3, ax3 = plt.subplots(figsize=(10, 6))

for method in grouped['Method'].unique():
    subset = grouped[grouped['Method'] == method].sort_values('Clients')
    x = subset['Clients']
    y_cpu = subset['cpu_mean']
    yerr_cpu = subset['cpu_std']
    y_mem = subset['mem_mean']
    yerr_mem = subset['mem_std']
    
    ax1.errorbar(x, y_cpu, yerr=yerr_cpu, marker='o', capsize=5, label=method)
    ax2.errorbar(x, y_mem, yerr=yerr_mem, marker='o', capsize=5, label=method)

ax1.set_title('Нагрузка на CPU')
ax1.set_ylabel('Средний CPU (%)')
ax1.set_xlabel('Количество клиентов')
ax1.legend()
ax1.grid(True)
fig1.tight_layout()

ax2.set_title('Использование оперативной памяти')
ax2.set_ylabel('Среднее Memory (%)')
ax2.set_xlabel('Количество клиентов')
ax2.legend()
ax2.grid(True)
fig2.tight_layout()

for method in delay_grouped["Method"].unique():

    subset = delay_grouped[
        delay_grouped["Method"] == method
    ].sort_values("Clients")

    ax3.errorbar(
        subset["Clients"],
        subset["delay_mean"],
        yerr=subset["delay_std"],
        marker="o",
        capsize=5,
        label=method
    )

ax3.set_title("Задержка доставки сообщения")
ax3.set_xlabel("Количество клиентов")
ax3.set_ylabel("Нормализованная задержка (мс)")
ax3.grid(True)
ax3.legend()
fig3.tight_layout()

methods = sorted(df_eff['Method'].unique())
clients_list = sorted(df_eff['Clients'].unique())
n_methods = len(methods)
bar_width = 0.8 / n_methods
x_base = np.arange(len(clients_list))
colors = plt.cm.tab10(np.linspace(0, 1, max(n_methods, 2)))


fig4, ax4 = plt.subplots(figsize=(12, 7))

for i, method in enumerate(methods):
    subset = (
        df_eff[df_eff['Method'] == method]
        .set_index('Clients')
        .reindex(clients_list)
        .fillna(0)
    )
    offset = (i - (n_methods - 1) / 2) * bar_width
    positions = x_base + offset

    payload = subset['Payload'].values
    overhead = subset['Overhead'].values

    ax4.bar(
        positions - bar_width / 4, payload, bar_width / 2,
        label=f'{method} — полезные данные',
        color=colors[i], edgecolor='black', linewidth=0.5, zorder=3
    )
    ax4.bar(
        positions + bar_width / 4, overhead, bar_width / 2,
        label=f'{method} — служебные данные',
        color=colors[i], alpha=0.35, hatch='//',
        edgecolor='black', linewidth=0.5, zorder=3
    )

ax4.set_xticks(x_base)
ax4.set_xticklabels([str(c) for c in clients_list])
ax4.set_yscale('log')
ax4.set_title(
    'Декомпозиция сетевого трафика: абсолютные объёмы\n'
    'полезной нагрузки (payload) и накладных расходов (overhead), логарифмическая шкала',
    fontsize=13, fontweight='bold'
)
ax4.set_ylabel('Объём данных, байт (логарифмическая шкала)')
ax4.set_xlabel('Количество клиентов')
ax4.grid(True, axis='y', which='both', alpha=0.3, zorder=0)
ax4.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9, frameon=False)
fig4.tight_layout()

fig5, ax5 = plt.subplots(figsize=(12, 7))

for i, method in enumerate(methods):
    subset = (
        df_eff[df_eff['Method'] == method]
        .set_index('Clients')
        .reindex(clients_list)
        .fillna(0)
    )
    offset = (i - (n_methods - 1) / 2) * bar_width
    positions = x_base + offset

    payload = subset['Payload'].values
    overhead = subset['Overhead'].values
    total = payload + overhead
    total_safe = np.where(total == 0, 1, total)

    payload_pct = payload / total_safe * 100
    overhead_pct = overhead / total_safe * 100

    ax5.bar(
        positions, payload_pct, bar_width,
        label=f'{method} — полезные данные',
        color=colors[i], edgecolor='black', linewidth=0.5, zorder=3
    )
    ax5.bar(
        positions, overhead_pct, bar_width, bottom=payload_pct,
        label=f'{method} — служебные данные',
        color=colors[i], alpha=0.35, hatch='//',
        edgecolor='black', linewidth=0.5, zorder=3
    )

    for pos, o_pct in zip(positions, overhead_pct):
        ax5.text(
            pos, 100 + 1.5, f'{o_pct:.0f}%',
            ha='center', va='bottom', fontsize=8, color='dimgray'
        )

ax5.set_xticks(x_base)
ax5.set_xticklabels([str(c) for c in clients_list])
ax5.set_ylim(0, 112)
ax5.set_title(
    'Доля полезной нагрузки и накладных расходов\n'
    'в общем объёме трафика',
    fontsize=13, fontweight='bold'
)
ax5.set_ylabel('Доля от общего объёма трафика, %')
ax5.set_xlabel('Количество клиентов')
ax5.grid(True, axis='y', alpha=0.3, zorder=0)
ax5.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9, frameon=False)
fig5.tight_layout()

plt.show()