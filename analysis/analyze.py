"""
Analyze - Phân tích kết quả benchmark và tạo biểu đồ
Đọc file benchmark_summary.json và tạo 3 biểu đồ:
1. Thời gian thực thi theo số node
2. Tỷ lệ tăng tốc thực tế vs lý tưởng
3. Hiệu suất song song theo số node
"""

import os
import sys
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Xác định thư mục gốc dự án
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)

# Dữ liệu mẫu khi chưa có kết quả benchmark thực tế
SAMPLE_DATA = {
    "timestamp": "2026-06-03T00:00:00",
    "configs": {
        "1": {"mean_ms": 280.0, "median_ms": 280.0, "std_ms": 15.0, "min_ms": 260.0, "max_ms": 300.0, "p99_ms": 299.0, "runs": [275, 280, 285, 278, 282]},
        "2": {"mean_ms": 155.0, "median_ms": 155.0, "std_ms": 10.0, "min_ms": 142.0, "max_ms": 168.0, "p99_ms": 167.0, "runs": [150, 155, 160, 152, 158]},
        "4": {"mean_ms": 85.0, "median_ms": 85.0, "std_ms": 8.0, "min_ms": 75.0, "max_ms": 95.0, "p99_ms": 94.0, "runs": [82, 85, 88, 80, 90]},
    },
    "speedup": {"1": 1.0, "2": 1.8065, "4": 3.2941},
    "efficiency": {"1": 1.0, "2": 0.9032, "4": 0.8235},
}


def load_results():
    json_path = os.path.join(PROJECT_ROOT, "results", "benchmark_summary.json")

    if os.path.exists(json_path):
        print(f"Đọc kết quả từ: {json_path}")
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print(f"Không tìm thấy file: {json_path}")
        print("Tạo dữ liệu mẫu để demo biểu đồ...")

        # Tạo thư mục results nếu chưa có
        results_dir = os.path.join(PROJECT_ROOT, "results")
        os.makedirs(results_dir, exist_ok=True)

        # Lưu dữ liệu mẫu
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_DATA, f, indent=2, ensure_ascii=False)
        print(f"Đã tạo file mẫu: {json_path}")

        return SAMPLE_DATA


def setup_chart_style():
    """Thiết lập style chung cho tất cả biểu đồ."""
    plt.rcParams.update({
        "font.size": 11,
        "axes.titlesize": 16,
        "axes.labelsize": 13,
        "xtick.labelsize": 11,
        "ytick.labelsize": 11,
        "figure.figsize": (10, 6),
        "figure.dpi": 150,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.facecolor": "#fafafa",
        "figure.facecolor": "white",
    })


def chart_execution_time(configs, charts_dir):
    """
    Biểu đồ 1: So sánh Mean, Median và P99 theo số lượng node.
    """
    # Sắp xếp theo số node
    sorted_keys = sorted(configs.keys(), key=lambda x: int(x))
    nodes = [int(k) for k in sorted_keys]
    means = [configs[k]["mean_ms"] for k in sorted_keys]
    medians = [configs[k].get("median_ms", configs[k]["mean_ms"]) for k in sorted_keys]
    p99s = [configs[k].get("p99_ms", configs[k]["max_ms"]) for k in sorted_keys]
    stds = [configs[k]["std_ms"] for k in sorted_keys]

    x = list(range(len(nodes)))
    width = 0.25 
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Tính tọa độ cho từng cột trong nhóm
    x_mean = [val - width for val in x]
    x_median = x
    x_p99 = [val + width for val in x]
    # Vẽ các cột
    rects1 = ax.bar(x_mean, means, width, label='Mean (Trung bình)', color='#2980b9', edgecolor='white', yerr=stds, capsize=4, error_kw={"linewidth": 1.2, "capthick": 1.2})
    rects2 = ax.bar(x_median, medians, width, label='Median (Trung vị)', color='#5dade2', edgecolor='white')
    rects3 = ax.bar(x_p99, p99s, width, label='P99 (Độ trễ đuôi - Tail Latency)', color='#e67e22', edgecolor='white')

    # Thêm nhãn giá trị trên đầu cột
    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.annotate(f'{height:.1f}',
                        xy=(rect.get_x() + rect.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom', fontsize=9, fontweight='bold')

    autolabel(rects1)
    autolabel(rects2)
    autolabel(rects3)

    ax.set_xlabel("Số lượng Node")
    ax.set_ylabel("Thời gian thực thi (ms)")
    ax.set_title("So sánh chỉ số thời gian thực thi: Mean vs Median vs P99")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{n} Nodes" for n in nodes])
    ax.legend(loc="upper right", fontsize=10)
    ax.yaxis.grid(True, alpha=0.3)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    plt.tight_layout()
    save_path = os.path.join(charts_dir, "execution_time.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Đã lưu biểu đồ: {save_path}")

def chart_speedup(speedup_data, charts_dir):
    """
    Biểu đồ 2: Tỷ lệ tăng tốc thực tế so với lý tưởng.
    """
    sorted_keys = sorted(speedup_data.keys(), key=lambda x: int(x))
    nodes = [int(k) for k in sorted_keys]
    actual = [speedup_data[k] for k in sorted_keys]
    ideal = [float(n) for n in nodes]  # Speedup lý tưởng = số node

    fig, ax = plt.subplots()

    # Đường lý tưởng 
    ax.plot(
        nodes, ideal,
        "--o",
        color="#2ecc71",
        label="Speedup lý tưởng",
        linewidth=2,
        markersize=8,
        alpha=0.7,
    )

    # Đường thực tế
    ax.plot(
        nodes, actual,
        "-s",
        color="#e74c3c",
        label="Speedup thực tế",
        linewidth=2.5,
        markersize=10,
        markerfacecolor="white",
        markeredgewidth=2,
    )

    # Nhãn giá trị tại mỗi điểm
    for n, sp in zip(nodes, actual):
        ax.annotate(
            f"{sp:.2f}x",
            (n, sp),
            textcoords="offset points",
            xytext=(0, 15),
            ha="center",
            fontweight="bold",
            fontsize=11,
            color="#e74c3c",
        )

    for n, sp in zip(nodes, ideal):
        ax.annotate(
            f"{sp:.1f}x",
            (n, sp),
            textcoords="offset points",
            xytext=(0, -20),
            ha="center",
            fontsize=10,
            color="#2ecc71",
        )

    ax.set_xticks(nodes)
    ax.set_xlabel("Số lượng Node")
    ax.set_ylabel("Tỷ lệ tăng tốc (Speedup Ratio)")
    ax.set_title("Tỷ lệ tăng tốc: Thực tế vs Lý tưởng")
    ax.legend(loc="upper left", fontsize=11)
    ax.yaxis.grid(True, alpha=0.3)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    plt.tight_layout()
    save_path = os.path.join(charts_dir, "speedup_ratio.png")
    plt.savefig(save_path)
    plt.close()
    print(f"Đã lưu biểu đồ: {save_path}")


def chart_efficiency(efficiency_data, charts_dir):
    """
    Biểu đồ 3: Hiệu suất song song E(n) = S(n)/n.
    """
    sorted_keys = sorted(efficiency_data.keys(), key=lambda x: int(x))
    nodes = [int(k) for k in sorted_keys]
    efficiencies = [efficiency_data[k] for k in sorted_keys]

    fig, ax = plt.subplots()

    bars = ax.bar(
        range(len(nodes)), efficiencies,
        color="#27ae60",
        edgecolor="white",
        linewidth=1.5,
        width=0.5,
        alpha=0.85,
    )

    # Đường tham chiếu 100% efficiency
    ax.axhline(
        y=1.0,
        color="#e74c3c",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
        label="Hiệu suất lý tưởng (100%)",
    )

    # Nhãn phần trăm trên mỗi cột
    for bar, eff in zip(bars, efficiencies):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.02,
            f"{eff * 100:.1f}%",
            ha="center", va="bottom",
            fontweight="bold", fontsize=11,
        )

    ax.set_xticks(range(len(nodes)))
    ax.set_xticklabels([str(n) for n in nodes])
    ax.set_xlabel("Số lượng Node")
    ax.set_ylabel("Hiệu suất (Efficiency)")
    ax.set_title("Hiệu suất song song theo số lượng Node")
    ax.legend(loc="upper right", fontsize=10)
    ax.yaxis.grid(True, alpha=0.3)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    # Giới hạn trục Y
    ax.set_ylim(0, max(efficiencies) * 1.2)

    plt.tight_layout()
    save_path = os.path.join(charts_dir, "efficiency.png")
    plt.savefig(save_path)
    plt.close()
    print(f"  [OK] Đã lưu biểu đồ: {save_path}")


def print_summary_table(configs, speedup, efficiency):
    """In bảng tổng kết ra console."""
    print()
    print("╔══════════╦═══════════════╦═══════════════╦═══════════════╦═══════════╦════════════╦════════════╗")
    print("║  Nodes   ║   Mean (ms)   ║  Median (ms)  ║   P99 (ms)    ║ Std (ms)  ║  Speedup   ║ Efficiency ║")
    print("╠══════════╬═══════════════╬═══════════════╬═══════════════╬═══════════╬════════════╬════════════╣")

    for n_str in sorted(configs.keys(), key=lambda x: int(x)):
        cfg = configs[n_str]
        sp = speedup.get(n_str, 1.0)
        eff = efficiency.get(n_str, 1.0)
        print(
            f"║    {n_str:<5} ║   {cfg['mean_ms']:>8.1f}    ║   {cfg.get('median_ms', cfg['mean_ms']):>8.1f}    ║   {cfg.get('p99_ms', cfg['max_ms']):>8.1f}    ║   {cfg['std_ms']:>5.1f}   "
            f"║   {sp:>5.3f}x   ║  {eff * 100:>5.1f}%    ║"
        )

    print("╚══════════╩═══════════════╩═══════════════╩═══════════════╩═══════════╩════════════╩════════════╝")


def main():
    """Hàm chính: đọc kết quả, tính toán, tạo biểu đồ."""
    sys.stdout.reconfigure(encoding='utf-8')
    print("=" * 60)
    print("  ShardMasters — Phân tích kết quả Benchmark")
    print("=" * 60)

    # Đọc dữ liệu
    data = load_results()
    configs = data["configs"]

    # Tính lại speedup và efficiency để xác minh
    baseline_mean = configs.get("1", {}).get("mean_ms", 1.0)
    speedup = {}
    efficiency = {}

    for n_str in configs:
        n = int(n_str)
        cfg = configs[n_str]
        
        # Backfill median_ms và p99_ms từ dữ liệu thô runs nếu thiếu
        if "median_ms" not in cfg or "p99_ms" not in cfg:
            runs = cfg.get("runs", [])
            if runs:
                import statistics
                cfg["median_ms"] = round(statistics.median(runs), 2)
                sorted_runs = sorted(runs)
                n_len = len(sorted_runs)
                if n_len == 1:
                    cfg["p99_ms"] = sorted_runs[0]
                else:
                    k_val = (n_len - 1) * 0.99
                    idx_val = int(k_val)
                    frac_val = k_val - idx_val
                    cfg["p99_ms"] = round(sorted_runs[idx_val] + frac_val * (sorted_runs[idx_val + 1] - sorted_runs[idx_val]), 2)
            else:
                cfg["median_ms"] = cfg["mean_ms"]
                cfg["p99_ms"] = cfg["max_ms"]
                
        sp = baseline_mean / configs[n_str]["mean_ms"] if configs[n_str]["mean_ms"] > 0 else 1.0
        speedup[n_str] = round(sp, 4)
        efficiency[n_str] = round(sp / n, 4)

    # Tạo thư mục biểu đồ
    charts_dir = os.path.join(PROJECT_ROOT, "analysis", "charts")
    os.makedirs(charts_dir, exist_ok=True)

    # Thiết lập style
    setup_chart_style()

    # Tạo 3 biểu đồ
    print("\n[Tạo biểu đồ]")
    chart_execution_time(configs, charts_dir)
    chart_speedup(speedup, charts_dir)
    chart_efficiency(efficiency, charts_dir)

    # In bảng tổng kết
    print_summary_table(configs, speedup, efficiency)

    print(f"\nBiểu đồ đã được lưu tại: {charts_dir}")


if __name__ == "__main__":
    main()
