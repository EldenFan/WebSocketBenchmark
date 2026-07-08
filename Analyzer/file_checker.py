import csv
import glob
import os
import re
import subprocess

EXPECTED_DURATION = 30.0

WARN_THRESHOLD_PCT = 5.0


def run_capinfos(pcap_path):
    cmd = ["capinfos", pcap_path]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output = result.stdout + "\n" + result.stderr

    truncated = "cut short" in output.lower() or "error occurred after reading" in output.lower()

    duration_match = re.search(r"Capture duration:\s*([\d.]+)\s*seconds", output)
    packets_match = re.search(r"Number of packets:\s*([\d,]+)", output)
    size_match = re.search(r"File size:\s*([\d.]+)\s*(\w+)", output)

    duration = float(duration_match.group(1)) if duration_match else None

    packets = None
    if packets_match:
        raw = packets_match.group(1)
        try:
            packets = int(raw.replace(",", ""))
        except ValueError:
            packets = None

    if packets is None:
        alt_match = re.search(r"Number of packets:\s*([\d.]+)\s*k", output, re.IGNORECASE)
        if alt_match:
            packets = int(float(alt_match.group(1)) * 1000)

    file_size = f"{size_match.group(1)} {size_match.group(2)}" if size_match else None

    if result.returncode != 0 and duration is None:
        error_line = output.strip().splitlines()[-1] if output.strip() else "неизвестная ошибка"
        return {
            "duration": None,
            "packets": packets,
            "file_size": file_size,
            "truncated": True,
            "readable": False,
            "error": error_line,
        }

    return {
        "duration": duration,
        "packets": packets,
        "file_size": file_size,
        "truncated": truncated,
        "readable": True,
        "error": None,
    }


def parse_filename(filename):
    base = filename[:-5]
    parts = base.split("_")
    if len(parts) < 3:
        return None, None
    method = "_".join(parts[:-2])
    try:
        clients = int(parts[-2])
    except ValueError:
        return None, None
    return method, clients


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    capture_dirs = sorted(glob.glob(os.path.join(script_dir, "Captures (*)")))

    if not capture_dirs:
        print(f"Не найдено ни одной папки 'Captures (N)' в {script_dir}")
        return

    rows = []

    for captures_dir in capture_dirs:
        run_match = re.search(r"Captures \((\d+)\)", captures_dir)
        run_idx = run_match.group(1) if run_match else "?"

        pcap_files = sorted(
            f for f in os.listdir(captures_dir) if f.endswith(".pcap")
        )

        for filename in pcap_files:
            method, clients = parse_filename(filename)
            filepath = os.path.join(captures_dir, filename)

            info = run_capinfos(filepath)

            if info["duration"] is not None:
                loss_pct = max(0.0, (EXPECTED_DURATION - info["duration"]) / EXPECTED_DURATION * 100)
            else:
                loss_pct = None

            rows.append({
                "Run": run_idx,
                "Method": method or "?",
                "Clients": clients if clients is not None else "?",
                "File": filename,
                "Readable": info["readable"],
                "Truncated": info["truncated"],
                "Duration_s": round(info["duration"], 3) if info["duration"] is not None else "N/A",
                "Expected_s": EXPECTED_DURATION,
                "Loss_pct": round(loss_pct, 2) if loss_pct is not None else "N/A",
                "Packets": info["packets"] if info["packets"] is not None else "N/A",
                "FileSize": info["file_size"] or "N/A",
                "Error": info["error"] or "",
            })

            status = "OK"
            if not info["readable"]:
                status = "НЕ ЧИТАЕТСЯ"
            elif info["truncated"]:
                status = "ОБРЕЗАН"

            loss_str = f"{loss_pct:.2f}%" if loss_pct is not None else "N/A"
            print(
                f"[Run {run_idx}] {filename:45s} "
                f"| {status:12s} "
                f"| длительность: {info['duration'] if info['duration'] is not None else 'N/A'} c "
                f"| потеря: {loss_str}"
            )

    report_path = os.path.join(script_dir, "pcap_losses_report.csv")
    fieldnames = [
        "Run", "Method", "Clients", "File", "Readable", "Truncated",
        "Duration_s", "Expected_s", "Loss_pct", "Packets", "FileSize", "Error",
    ]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nОтчёт сохранён: {report_path}")

    print("\n=== Файлы с заметной потерей данных (>{:.0f}%) или ошибкой чтения ===".format(WARN_THRESHOLD_PCT))
    problems = [
        r for r in rows
        if not r["Readable"]
        or (isinstance(r["Loss_pct"], float) and r["Loss_pct"] > WARN_THRESHOLD_PCT)
    ]
    if not problems:
        print("Не найдено. Все файлы обрезаны незначительно (или не обрезаны вовсе).")
    else:
        for r in problems:
            print(
                f"  Run {r['Run']} | {r['Method']} | {r['Clients']} клиентов | "
                f"{r['File']} | потеря: {r['Loss_pct']} | читаемость: {r['Readable']}"
            )

    print("\n=== Сводка обрезанных файлов (Truncated=True) по методам ===")
    truncated_by_method = {}
    for r in rows:
        if r["Truncated"]:
            truncated_by_method.setdefault(r["Method"], []).append(f"Run{r['Run']}/{r['Clients']}cl")
    if not truncated_by_method:
        print("Обрезанных файлов не найдено.")
    else:
        for method, occurrences in truncated_by_method.items():
            print(f"  {method}: {len(occurrences)} файл(ов) -> {', '.join(occurrences)}")


if __name__ == "__main__":
    main()