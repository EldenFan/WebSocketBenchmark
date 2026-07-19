from datetime import datetime
import json
import os
import subprocess
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Times New Roman'],
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 12,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'legend.fontsize': 10,
    'figure.titlesize': 14,
    'text.usetex': False
})

RU_METHODS = {
    'websocket': 'Веб-сокет (WebSocket)',
    'long_polling': 'Длинный опрос (Long Polling)',
    'short_polling': 'Короткий опрос (Short Polling)'
}

METHOD_STYLES = {
    'websocket': {'marker': 'o', 'linestyle': '-', 'color': '#1f77b4'},
    'long_polling': {'marker': 's', 'linestyle': '--', 'color': '#2ca02c'},
    'short_polling': {'marker': '^', 'linestyle': ':', 'color': '#ff7f0e'}
}

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
                    clean_hex = hex_data.replace(":", "").strip()
                    payload_bytes += len(bytes.fromhex(clean_hex))
    except Exception as e:
        print(f"Ошибка при чтении данных из {pcap_file}: {e}")
        return total_bytes, 0
    
    return total_bytes, payload_bytes


def check_pcap_truncated(pcap_file):
    cmd = ['tshark', '-r', pcap_file, '-c', '1', '-T', 'fields', '-e', 'frame.number']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return 'cut short' in (result.stderr or '').lower()
    except Exception:
        return False


def get_tcp_stats(pcap_file, verbose=True):
    def count_matches(display_filter):
        cmd = ['tshark', '-r', pcap_file, '-Y', display_filter, '-T', 'fields', '-e', 'frame.number']
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            return len([l for l in result.stdout.splitlines() if l.strip()])
        except Exception as e:
            print(f"Ошибка при подсчёте '{display_filter}' в {pcap_file}: {e}")
            return 0

    syn_count = count_matches('tcp.flags.syn==1 && tcp.flags.ack==0')
    retrans_count = count_matches('tcp.analysis.retransmission')
    total_tcp_count = count_matches('tcp')

    retrans_pct = (retrans_count / total_tcp_count * 100) if total_tcp_count > 0 else 0.0

    truncated = check_pcap_truncated(pcap_file)

    if verbose:
        flag = " [ФАЙЛ ОБРЕЗАН]" if truncated else ""
        print(
            f"  [TCP] {os.path.basename(pcap_file)}: "
            f"retrans={retrans_count}, total_tcp={total_tcp_count}, "
            f"retrans_pct={retrans_pct:.2f}%, syn={syn_count}{flag}"
        )

    return syn_count, retrans_count, total_tcp_count, retrans_pct, truncated


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

        if not delays:
            print(f"Пропуск {filename}: не удалось извлечь задержки — файл исключён из статистики")
            continue

        min_delay = min(delays)
        normalized_delays = [d - min_delay for d in delays]
        avg_delay_for_run = sum(normalized_delays) / len(normalized_delays)

        for d in normalized_delays:
            all_delays.append({
                "Method": method,
                "Clients": clients,
                "Run": run_idx,
                "Delay": d
            })

        total, payload = get_pcap_stats(filepath)
        efficiency_data.append({
            'Method': method, 'Clients': clients,
            'Payload': payload, 'Overhead': total - payload
        })

        syn_count, retrans_count, total_tcp_count, retrans_pct, truncated = get_tcp_stats(filepath)
        connection_data.append({
            'Method': method, 'Clients': clients, 'Run': run_idx,
            'NewConnections': syn_count,
            'Retransmissions': retrans_count,
            'TotalTcpPackets': total_tcp_count,
            'RetransmissionsPct': retrans_pct,
            'AvgApplicationRTT_ms': avg_delay_for_run,
            'Truncated': truncated,
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
        "tshark", "-n", "-r", pcap_file, "-Y", "http.response || websocket",
        "-T", "fields", "-e", "frame.time_epoch", "-e", "http.file_data", "-e", "websocket.payload"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
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
connection_data = []

for run_idx in range(5):
    captures_dir = os.path.join(script_dir, f"Captures ({run_idx})")
    if not os.path.exists(captures_dir):
        continue

    print(f"\n=== Run {run_idx}: {captures_dir} ===")
    test_starts = get_test_starts_from_pcaps(captures_dir)
    csv_path = os.path.join(captures_dir, "metrics.csv")
    if os.path.exists(csv_path):
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
                    'Method': method, 'Clients': clients, 'CPU': cpu_mean, 'Memory': mem_mean, 'Run': run_idx
                })

df_all = pd.DataFrame(all_results)
if not df_all.empty:
    grouped = df_all.groupby(['Method', 'Clients']).agg(
        cpu_mean=('CPU', 'mean'), cpu_std=('CPU', 'std'),
        mem_mean=('Memory', 'mean'), mem_std=('Memory', 'std')
    ).reset_index()
else:
    grouped = pd.DataFrame(columns=['Method', 'Clients', 'cpu_mean', 'cpu_std', 'mem_mean', 'mem_std'])

df_delay = pd.DataFrame(all_delays)
if df_delay.empty:
    delay_grouped = pd.DataFrame(columns=["Method", "Clients", "delay_mean", "delay_std", "delay_p50", "delay_p95", "delay_p99", "delay_max"])
else:
    delay_grouped = df_delay.groupby(["Method", "Clients"]).agg(
        delay_mean=("Delay", "mean"), delay_std=("Delay", "std"),
        delay_p50=("Delay", lambda x: np.percentile(x, 50)),
        delay_p95=("Delay", lambda x: np.percentile(x, 95)),
        delay_p99=("Delay", lambda x: np.percentile(x, 99)),
        delay_max=("Delay", "max")
    ).reset_index()

df_conn = pd.DataFrame(connection_data)

if not df_conn.empty:
    pd.set_option('display.width', 140)
    print("\n=== Сырые TCP-метрики по всем файлам (для проверки) ===")
    print(
        df_conn[['Method', 'Clients', 'Run', 'Retransmissions', 'TotalTcpPackets',
                 'RetransmissionsPct', 'Truncated']]
        .sort_values(['Method', 'Clients', 'Run'])
        .to_string(index=False)
    )
    n_truncated = df_conn['Truncated'].sum()
    if n_truncated > 0:
        print(
            f"\nВНИМАНИЕ: {n_truncated} из {len(df_conn)} pcap-файлов помечены tshark "
            f"как обрезанные ('cut short'). Метрики по ним могут быть недостоверны."
        )
    for method, sub in df_conn.groupby('Method'):
        pct_std = sub['RetransmissionsPct'].std()
        pct_mean = sub['RetransmissionsPct'].mean()

if not df_conn.empty:
    conn_grouped = df_conn.groupby(["Method", "Clients"]).agg(
        new_conn_mean=("NewConnections", "mean"),
        retrans_pct_mean=("RetransmissionsPct", "mean"),
        rtt_mean=("AvgApplicationRTT_ms", "mean"),
        any_truncated=("Truncated", "any"),
    ).reset_index()
else:
    conn_grouped = pd.DataFrame(columns=["Method", "Clients", "new_conn_mean", "retrans_pct_mean", "rtt_mean", "any_truncated"])

df_eff = pd.DataFrame(efficiency_data)
if not df_eff.empty:
    df_eff = df_eff.groupby(['Method', 'Clients']).mean().reset_index()

if not grouped.empty:
    fig1, ax1 = plt.subplots(figsize=(10, 6))
    for method in grouped['Method'].unique():
        subset = grouped[grouped['Method'] == method].sort_values('Clients')
        style = METHOD_STYLES.get(method, {})
        ax1.errorbar(subset['Clients'], subset['cpu_mean'], yerr=subset['cpu_std'], capsize=5, 
                     label=RU_METHODS.get(method, method), **style)
    ax1.set_title('Вычислительная нагрузка на центральный процессор (CPU)')
    ax1.set_ylabel('Средняя загрузка CPU (%)')
    ax1.set_xlabel('Количество параллельных клиентов')
    ax1.legend(loc='upper left')
    ax1.grid(True, linestyle=':', alpha=0.6)
    fig1.tight_layout()

    fig2, ax2 = plt.subplots(figsize=(10, 6))
    for method in grouped['Method'].unique():
        subset = grouped[grouped['Method'] == method].sort_values('Clients')
        style = METHOD_STYLES.get(method, {})
        ax2.errorbar(subset['Clients'], subset['mem_mean'], yerr=subset['mem_std'], capsize=5, 
                     label=RU_METHODS.get(method, method), **style)
    ax2.set_title('Потребление оперативной памяти (RAM)')
    ax2.set_ylabel('Среднее использование памяти (%)')
    ax2.set_xlabel('Количество параллельных клиентов')
    ax2.legend(loc='upper left')
    ax2.grid(True, linestyle=':', alpha=0.6)
    fig2.tight_layout()

if not df_eff.empty:
    methods = sorted(df_eff['Method'].unique())
    clients_list = sorted(df_eff['Clients'].unique())
    n_methods = len(methods)
    bar_width = 0.8 / n_methods
    x_base = np.arange(len(clients_list))

    fig3, ax3 = plt.subplots(figsize=(11, 6))
    for i, method in enumerate(methods):
        subset = df_eff[df_eff['Method'] == method].set_index('Clients').reindex(clients_list).fillna(0)
        offset = (i - (n_methods - 1) / 2) * bar_width
        positions = x_base + offset
        color = METHOD_STYLES.get(method, {}).get('color', '#000')

        ax3.bar(positions - bar_width / 4, subset['Payload'].values, bar_width / 2, 
                label=f'{RU_METHODS.get(method, method)} — Полезные данные', color=color, edgecolor='black', linewidth=0.5, zorder=3)
        ax3.bar(positions + bar_width / 4, subset['Overhead'].values, bar_width / 2, 
                label=f'{RU_METHODS.get(method, method)} — Служебные данные', color=color, alpha=0.3, hatch='//', edgecolor='black', linewidth=0.5, zorder=3)

    ax3.set_xticks(x_base)
    ax3.set_xticklabels([str(c) for c in clients_list])
    ax3.set_yscale('log')
    ax3.set_title('Декомпозиция сетевого трафика: абсолютные объёмы данных', fontweight='bold')
    ax3.set_ylabel('Объём переданных данных, байт (логарифмическая шкала)')
    ax3.set_xlabel('Количество клиентов')
    ax3.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    ax3.grid(True, which='both', linestyle=':', alpha=0.5)
    fig3.tight_layout()

    fig4, ax4 = plt.subplots(figsize=(11, 6))
    for i, method in enumerate(methods):
        subset = df_eff[df_eff['Method'] == method].set_index('Clients').reindex(clients_list).fillna(0)
        offset = (i - (n_methods - 1) / 2) * bar_width
        positions = x_base + offset
        color = METHOD_STYLES.get(method, {}).get('color', '#000')

        total = subset['Payload'].values + subset['Overhead'].values
        total_safe = np.where(total == 0, 1, total)
        payload_pct = subset['Payload'].values / total_safe * 100
        overhead_pct = subset['Overhead'].values / total_safe * 100

        ax4.bar(positions, payload_pct, bar_width, label=f'{RU_METHODS.get(method, method)} — Полезные данные', color=color, edgecolor='black', linewidth=0.5, zorder=3)
        ax4.bar(positions, overhead_pct, bar_width, bottom=payload_pct, label=f'{RU_METHODS.get(method, method)} — Служебные данные', color=color, alpha=0.3, hatch='//', edgecolor='black', linewidth=0.5, zorder=3)

        for pos, o_pct in zip(positions, overhead_pct):
            ax4.text(pos, 101.5, f'{o_pct:.0f}%', ha='center', va='bottom', fontsize=8, color='dimgray')

    ax4.set_xticks(x_base)
    ax4.set_xticklabels([str(c) for c in clients_list])
    ax4.set_ylim(0, 115)
    ax4.set_title('Доля полезной нагрузки и накладных расходов в общем объёме трафика', fontweight='bold')
    ax4.set_ylabel('Доля от общего объёма трафика (%)')
    ax4.set_xlabel('Количество клиентов')
    ax4.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    ax4.grid(True, axis='y', linestyle=':', alpha=0.5)
    fig4.tight_layout()

if not delay_grouped.empty:
    fig5, ax5 = plt.subplots(figsize=(10, 6))
    for method in sorted(delay_grouped['Method'].unique()):
        subset = delay_grouped[delay_grouped['Method'] == method].sort_values('Clients')
        style = METHOD_STYLES.get(method, {})
        color = style.get('color', '#000')
        
        ax5.plot(subset['Clients'], subset['delay_p50'], marker=style.get('marker'), linestyle='-', color=color, label=f'{RU_METHODS.get(method, method)} — p50 (Медиана)')
        ax5.plot(subset['Clients'], subset['delay_p95'], marker='s', linestyle='--', color=color, alpha=0.7, label=f'{RU_METHODS.get(method, method)} — p95')
        ax5.plot(subset['Clients'], subset['delay_p99'], marker='^', linestyle=':', color=color, alpha=0.5, label=f'{RU_METHODS.get(method, method)} — p99')

    ax5.set_title('Перцентили прикладной задержки доставки сообщений (Предсказуемость канала)')
    ax5.set_xlabel('Количество параллельных клиентов')
    ax5.set_ylabel('Время доставки сообщения (мс)')
    ax5.grid(True, linestyle=':', alpha=0.6)
    ax5.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)
    fig5.tight_layout()

if not conn_grouped.empty:
    fig6, ax6a = plt.subplots(figsize=(10, 6))

    for method in sorted(conn_grouped['Method'].unique()):
        subset = conn_grouped[conn_grouped['Method'] == method].sort_values('Clients')
        style = METHOD_STYLES.get(method, {})
        color = style.get('color', '#000')

        ax6a.plot(subset['Clients'], subset['new_conn_mean'], marker=style.get('marker'), linestyle='-', color=color, label=RU_METHODS.get(method, method))

    ax6a.set_title('Количество новых TCP-соединений (SYN-пакетов) за тест')
    ax6a.set_xlabel('Количество клиентов')
    ax6a.set_ylabel('Число зарегистрированных SYN-пакетов')
    ax6a.grid(True, linestyle=':', alpha=0.6)
    ax6a.legend(loc='upper left')
    fig6.tight_layout()
 
plt.show()