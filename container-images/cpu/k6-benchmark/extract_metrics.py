# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import csv
import json
import logging
import os
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

# Optional: Google Cloud Monitoring
try:
    from google.cloud import monitoring_v3

    HAS_GCP = True
except ImportError:
    HAS_GCP = False


@dataclass
class ScenarioResult:
    name: str
    durations: List[float]
    start_time: datetime
    end_time: datetime
    tags: Dict[str, any]
    total_requests: int
    successful_requests: int
    vus: int


def parse_k6_output(filepath: str) -> List[ScenarioResult]:
    """Parses k6 JSONL and extracts data for all discovered scenarios."""
    scenarios_data = {}
    vus_points = []

    logging.info(f"Parsing k6 output file: {filepath}")
    with open(filepath, "r") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except:
                continue

            metric_name = record.get("metric")
            record_type = record.get("type")
            if record_type != "Point":
                continue

            data = record.get("data", {})
            req_tags = data.get("tags", {})
            value = data.get("value")
            time_str = data.get("time")
            if not time_str:
                continue

            if "." in time_str:
                base, frac = time_str.split(".")
                frac = frac.replace("Z", "")[:6]
                clean_time_str = f"{base}.{frac}Z"
            else:
                clean_time_str = time_str
            if clean_time_str.endswith("Z"):
                clean_time_str = clean_time_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean_time_str)

            if metric_name == "vus" and value is not None:
                vus_points.append((dt, int(value)))

            scenario_name = req_tags.get("scenario")
            if scenario_name:
                if scenario_name not in scenarios_data:
                    scenarios_data[scenario_name] = {
                        "durations": [],
                        "total_requests": 0,
                        "successful_requests": 0,
                        "start_time": dt,
                        "end_time": dt,
                        "tags": {},
                    }
                s_entry = scenarios_data[scenario_name]
                if dt < s_entry["start_time"]:
                    s_entry["start_time"] = dt
                if dt > s_entry["end_time"]:
                    s_entry["end_time"] = dt
                if metric_name == "http_reqs":
                    s_entry["total_requests"] += 1
                    if req_tags.get("expected_response") == "true":
                        s_entry["successful_requests"] += 1
                if metric_name == "http_req_duration" and value is not None:
                    s_entry["durations"].append(value)
                    if not s_entry["tags"]:
                        s_entry["tags"] = {
                            "model": req_tags.get("model", "unknown"),
                            "accelerator": req_tags.get("accelerator", "unknown"),
                            "inference_server": req_tags.get(
                                "inference_server", "unknown"
                            ),
                            "width": int(req_tags.get("width", 1024)),
                            "height": int(req_tags.get("height", 1024)),
                            "steps": int(req_tags.get("num_inference_steps", 20)),
                            "seed": req_tags.get("seed", "unknown"),
                            "batch_size": int(req_tags.get("batch_size", 1)),
                            "target_url": req_tags.get("target_url", "unknown"),
                            "deployment_name": req_tags.get(
                                "deployment_name", "unknown"
                            ),
                        }

    results = []
    for name, data in scenarios_data.items():
        if not (name.startswith("bench") or name == "benchmark"):
            continue
        if not data["durations"]:
            continue
        max_vus = 0
        import re

        m = re.search(r"_v(\d+)_", name)
        if m:
            max_vus = int(m.group(1))
        else:
            for v_dt, v_val in vus_points:
                if data["start_time"] <= v_dt <= data["end_time"]:
                    if v_val > max_vus:
                        max_vus = v_val
        results.append(
            ScenarioResult(
                name=name,
                durations=data["durations"],
                start_time=data["start_time"],
                end_time=data["end_time"],
                tags=data["tags"],
                total_requests=data["total_requests"],
                successful_requests=data["successful_requests"],
                vus=max_vus if max_vus > 0 else 1,
            )
        )
    results.sort(key=lambda x: x.start_time)
    return results


def get_typed_value(point_value):
    if hasattr(point_value, "_pb"):
        value_type = point_value._pb.WhichOneof("value")
    elif hasattr(point_value, "WhichOneof"):
        value_type = point_value.WhichOneof("value")
    else:
        value_type = None
    if value_type == "double_value":
        return point_value.double_value
    elif value_type == "int64_value":
        return point_value.int64_value
    else:
        if getattr(point_value, "double_value", 0.0) != 0.0:
            return point_value.double_value
        elif getattr(point_value, "int64_value", 0) != 0:
            return point_value.int64_value
        return 0.0


def fetch_dcgm_metrics(
    project_id,
    start_time,
    end_time,
    vram_metric,
    util_metric,
    power_metric,
    pod=None,
    pod_is_prefix=False,
    namespace=None,
    node=None,
):
    import sys

    print(f"DEBUG: sys.executable = {sys.executable}, HAS_GCP = {HAS_GCP}")
    if not HAS_GCP or not project_id:
        print("DEBUG: Exiting early because HAS_GCP is False or project_id is empty")
        return "N/A", "N/A", "N/A"
    try:
        client = monitoring_v3.MetricServiceClient()
        project_name = f"projects/{project_id}"
        interval = monitoring_v3.TimeInterval(
            {"start_time": start_time, "end_time": end_time}
        )
        base_filter = ' AND resource.type = "prometheus_target"'
        if pod:
            if pod_is_prefix:
                base_filter += f' AND metric.labels.pod = starts_with("{pod}")'
            else:
                base_filter += f' AND metric.labels.pod = "{pod}"'
        if node:
            base_filter += f' AND resource.labels.instance = starts_with("{node}")'

        def fetch(m_type):
            full_filter = f'metric.type = "{m_type}"{base_filter}'
            print(f"DEBUG: fetch_dcgm_metrics for {pod} with filter: {full_filter}")
            try:
                res = client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": full_filter,
                        "interval": interval,
                    }
                )
                print(f"DEBUG: Found {sum(1 for _ in res)} time series.")
                return client.list_time_series(
                    request={
                        "name": project_name,
                        "filter": full_filter,
                        "interval": interval,
                    }
                )
            except Exception as e:
                print(f"DEBUG: Exception in fetch_dcgm_metrics: {e}")
                return []

        vram_per_gpu = {}
        for result in fetch(vram_metric):
            gpu_idx = result.metric.labels.get("gpu", "0")
            vram_per_gpu.setdefault(gpu_idx, 0)
            for point in result.points:
                val = get_typed_value(point.value)
                if val > vram_per_gpu[gpu_idx]:
                    vram_per_gpu[gpu_idx] = val

        compute_per_gpu = {}
        for result in fetch(util_metric):
            gpu_idx = result.metric.labels.get("gpu", "0")
            compute_per_gpu.setdefault(gpu_idx, [])
            for point in result.points:
                compute_per_gpu[gpu_idx].append(get_typed_value(point.value))

        power_per_gpu = {}
        for result in fetch(power_metric):
            gpu_idx = result.metric.labels.get("gpu", "0")
            power_per_gpu.setdefault(gpu_idx, [])
            for point in result.points:
                power_per_gpu[gpu_idx].append(get_typed_value(point.value))

        avg_compute_per_gpu = {
            g: sum(vals) / len(vals) for g, vals in compute_per_gpu.items() if vals
        }
        avg_power_per_gpu = {
            g: sum(vals) / len(vals) for g, vals in power_per_gpu.items() if vals
        }

        total_vram = sum(vram_per_gpu.values())
        total_compute = sum(avg_compute_per_gpu.values())
        total_power = sum(avg_power_per_gpu.values())

        avg_compute = (
            total_compute / len(avg_compute_per_gpu) if avg_compute_per_gpu else 0
        )
        avg_power = total_power / len(avg_power_per_gpu) if avg_power_per_gpu else 0

        return {
            "vram_total": f"{total_vram} MiB" if vram_per_gpu else "N/A",
            "vram_per_gpu": (
                json.dumps({g: f"{v} MiB" for g, v in sorted(vram_per_gpu.items())})
                if vram_per_gpu
                else "N/A"
            ),
            "compute_total": f"{total_compute:.2f}%" if avg_compute_per_gpu else "N/A",
            "compute_avg": f"{avg_compute:.2f}%" if avg_compute_per_gpu else "N/A",
            "compute_per_gpu": (
                json.dumps(
                    {g: f"{v:.2f}%" for g, v in sorted(avg_compute_per_gpu.items())}
                )
                if avg_compute_per_gpu
                else "N/A"
            ),
            "power_total": f"{total_power:.2f} W" if avg_power_per_gpu else "N/A",
            "power_avg": f"{avg_power:.2f} W" if avg_power_per_gpu else "N/A",
            "power_per_gpu": (
                json.dumps(
                    {g: f"{v:.2f} W" for g, v in sorted(avg_power_per_gpu.items())}
                )
                if avg_power_per_gpu
                else "N/A"
            ),
            "raw_total_vram_mib": total_vram,
        }
    except Exception as e:
        logging.error(f"Failed to fetch metrics: {e}")
        return {}


EXPECTED_CSV_HEADER = [
    "Source File",
    "Deployment Name",
    "Target URL",
    "Model",
    "Inference Server",
    "Accelerator",
    "Resolution",
    "Inference Steps",
    "Batch Size",
    "Virtual Users (VUs)",
    "Start Time (UTC)",
    "End Time (UTC)",
    "Total Time (s)",
    "Total Requests",
    "Success Rate (%)",
    "Throughput (Images/s)",
    "Request Throughput (RPS)",
    "Request Latency p50 (s)",
    "Request Latency p95 (s)",
    "Request Latency p99 (s)",
    "Image Latency p50 (s)",
    "Image Latency p95 (s)",
    "Image Latency p99 (s)",
    "Peak VRAM (Total)",
    "Peak VRAM (Per GPU)",
    "Peak VRAM Utilization (%)",
    "Compute (Total)",
    "Compute (Average)",
    "Compute (Per GPU)",
    "Power (Total)",
    "Power (Average)",
    "Power (Per GPU)",
    "Node Hourly Cost ($)",
    "Cost per 1k Images ($)",
]


def get_gcp_project_id():
    import urllib.request

    try:
        url = "http://metadata.google.internal/computeMetadata/v1/project/project-id"
        req = urllib.request.Request(url, headers={"Metadata-Flavor": "Google"})
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.read().decode("utf-8")
    except:
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Extract metrics from multi-scenario k6 JSONL."
    )
    parser.add_argument("--file", required=True)
    parser.add_argument("--output-csv", default="k6-benchmark.csv")
    parser.add_argument("--hourly-cost", type=float, default=0.0)
    parser.add_argument("--project-id")
    parser.add_argument("--pod")
    parser.add_argument("--namespace")
    parser.add_argument("--node")
    parser.add_argument(
        "--vram-metric", default="prometheus.googleapis.com/DCGM_FI_DEV_FB_USED/gauge"
    )
    parser.add_argument(
        "--util-metric", default="prometheus.googleapis.com/DCGM_FI_DEV_GPU_UTIL/gauge"
    )
    parser.add_argument(
        "--power-metric",
        default="prometheus.googleapis.com/DCGM_FI_DEV_POWER_USAGE/gauge",
    )

    args = parser.parse_args()
    if not args.project_id:
        args.project_id = get_gcp_project_id()

    scenario_results = parse_k6_output(args.file)
    if not scenario_results:
        logging.error("No valid benchmark scenario data found.")
        sys.exit(1)

    csv_rows, report_sections = [], []
    input_path = Path(args.file)
    header = [
        "=" * 50,
        f" GKE Price/Performance Benchmark Consolidated Report",
        f" Source: {input_path.name}",
        "=" * 50,
    ]

    summary_cols = [
        "Scenario",
        "Res",
        "B",
        "VU",
        "Steps",
        "Suc%",
        "Img/s",
        "RPS",
        "ReqP50",
        "ImgP50",
        "VRAM",
        "GPU%",
        "Cost/1k",
    ]
    summary_fmt = "{:<20} {:<10} {:<2} {:<2} {:<5} {:<4} {:<7} {:<6} {:<7} {:<7} {:<7} {:<6} {:<8}"
    summary_table = ["SUMMARY TABLE:", summary_fmt.format(*summary_cols), "-" * 105]

    for res in scenario_results:
        total_time = (res.end_time - res.start_time).total_seconds()
        batch_size = res.tags.get("batch_size", 1)
        throughput = (
            (res.successful_requests * batch_size) / total_time if total_time > 0 else 0
        )
        rps = res.successful_requests / total_time if total_time > 0 else 0
        success_rate = (
            (res.successful_requests / res.total_requests) * 100
            if res.total_requests > 0
            else 0
        )
        p50 = statistics.median(res.durations)
        if len(res.durations) > 1:
            q = statistics.quantiles(res.durations, n=100, method="inclusive")
            p95, p99 = q[94], q[98]
        else:
            p95 = p99 = res.durations[0]
        img_p50, img_p95, img_p99 = p50 / batch_size, p95 / batch_size, p99 / batch_size
        cost_per_1k = (
            (args.hourly_cost / (throughput * 3600)) * 1000 if throughput > 0 else 0
        )

        dcgm_metrics = fetch_dcgm_metrics(
            args.project_id,
            res.start_time,
            res.end_time,
            args.vram_metric,
            args.util_metric,
            args.power_metric,
            pod=args.pod or res.tags.get("deployment_name"),
            pod_is_prefix=not args.pod,
            namespace=args.namespace,
            node=args.node,
        )

        vram_total = dcgm_metrics.get("vram_total", "N/A")
        vram_per_gpu = dcgm_metrics.get("vram_per_gpu", "N/A")
        comp_total = dcgm_metrics.get("compute_total", "N/A")
        comp_avg = dcgm_metrics.get("compute_avg", "N/A")
        comp_per_gpu = dcgm_metrics.get("compute_per_gpu", "N/A")
        pow_total = dcgm_metrics.get("power_total", "N/A")
        pow_avg = dcgm_metrics.get("power_avg", "N/A")
        pow_per_gpu = dcgm_metrics.get("power_per_gpu", "N/A")
        v_val_mib = dcgm_metrics.get("raw_total_vram_mib", 0)

        vram_util = "N/A"
        try:
            accel = res.tags.get("accelerator", "").lower()
            if "l4-x4" in accel:
                total_vram_max = 22528 * 4
            elif "l4-x2" in accel:
                total_vram_max = 22528 * 2
            elif "l4" in accel:
                total_vram_max = 22528
            elif "6000" in accel:
                total_vram_max = 98304
            else:
                total_vram_max = 0

            if total_vram_max and v_val_mib > 0:
                vram_util = f"{(v_val_mib / total_vram_max) * 100:.2f}%"
        except:
            pass

        summary_table.append(
            summary_fmt.format(
                res.name[:20],
                f"{res.tags.get('width')}x{res.tags.get('height')}",
                batch_size,
                res.vus,
                res.tags.get("steps", 20),
                f"{success_rate:.0f}",
                f"{throughput:.2f}",
                f"{rps:.2f}",
                f"{p50/1000:.2f}",
                f"{img_p50/1000:.2f}",
                f"{v_val_mib/1024:.0f}G" if v_val_mib else "N/A",
                comp_avg.replace("%", ""),
                f"${cost_per_1k:.2f}",
            )
        )

        report_sections.extend(
            [
                "",
                "=" * 50,
                " GKE Price/Performance Benchmark Report",
                "=" * 50,
                f"Scenario:            {res.name}",
                f"Model:               {res.tags.get('model')}",
                f"Inference Server:    {res.tags.get('inference_server')}",
                f"Accelerator:         {res.tags.get('accelerator')}",
                f"Resolution:          {res.tags.get('width')}x{res.tags.get('height')}",
                f"Inference Steps:     {res.tags.get('steps')}",
                f"Batch Size:          {batch_size}",
                f"Virtual Users (VUs): {res.vus}",
                f"Time Window:         {res.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} to {res.end_time.strftime('%H:%M:%S UTC')} ({total_time:.2f}s)",
                "-" * 50,
                "UX Metrics (Off-Node):",
                f"  Total Requests:    {res.total_requests}",
                f"  Success Rate:      {success_rate:.2f}%",
                f"  Throughput:        {throughput:.4f} Images/Second",
                f"  Request RPS:       {rps:.4f} RPS",
                f"  Request Latency p50: {p50/1000:.3f} s",
                f"  Request Latency p95: {p95/1000:.3f} s",
                f"  Request Latency p99: {p99/1000:.3f} s",
                f"  Image Latency p50:   {img_p50/1000:.3f} s",
                f"  Image Latency p95:   {img_p95/1000:.3f} s",
                f"  Image Latency p99:   {img_p99/1000:.3f} s",
                "-" * 50,
                "Hardware Metrics (On-Node DCGM):",
                f"  Peak VRAM (Total):   {vram_total}",
                f"  Peak VRAM (Per GPU): {vram_per_gpu}",
                f"  VRAM Utilization:    {vram_util}",
                f"  Compute (Total):     {comp_total}",
                f"  Compute (Average):   {comp_avg}",
                f"  Compute (Per GPU):   {comp_per_gpu}",
                f"  Power (Total):       {pow_total}",
                f"  Power (Average):     {pow_avg}",
                f"  Power (Per GPU):     {pow_per_gpu}",
                "-" * 50,
                "Business Metrics:",
                f"  Node Hourly Cost:  ${args.hourly_cost:.4f}",
                f"  Cost per 1k Images:  ${cost_per_1k:.4f}",
                "=" * 50,
            ]
        )

        csv_rows.append(
            [
                input_path.name,
                res.tags.get("deployment_name"),
                res.tags.get("target_url"),
                res.tags.get("model"),
                res.tags.get("inference_server"),
                res.tags.get("accelerator"),
                f"{res.tags.get('width')}x{res.tags.get('height')}",
                res.tags.get("steps"),
                batch_size,
                res.vus,
                res.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                res.end_time.strftime("%Y-%m-%d %H:%M:%S"),
                f"{total_time:.2f}",
                res.total_requests,
                f"{success_rate:.2f}",
                f"{throughput:.4f}",
                f"{rps:.4f}",
                f"{p50/1000:.3f}",
                f"{p95/1000:.3f}",
                f"{p99/1000:.3f}",
                f"{img_p50/1000:.3f}",
                f"{img_p95/1000:.3f}",
                f"{img_p99/1000:.3f}",
                vram_total,
                vram_per_gpu,
                vram_util,
                comp_total,
                comp_avg,
                comp_per_gpu,
                pow_total,
                pow_avg,
                pow_per_gpu,
                f"{args.hourly_cost:.4f}",
                f"{cost_per_1k:.4f}",
            ]
        )

    output_path = input_path.with_name(f"{input_path.stem}-report.txt")
    with open(output_path, "w") as f:
        f.write("\n".join(header + summary_table + report_sections) + "\n")

    csv_out = Path(args.output_csv)
    write_h = not csv_out.exists()
    existing_rows = set()
    if not write_h:
        with open(csv_out, "r") as f:
            reader = csv.reader(f)
            if next(reader, None) != EXPECTED_CSV_HEADER:
                ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                csv_out.rename(csv_out.with_name(f"{csv_out.stem}.mismatch.{ts}.csv"))
                write_h = True
            else:
                for row in reader:
                    if len(row) > 10:
                        existing_rows.add((row[0], row[6], row[9]))

    with open(csv_out, "a", newline="") as f:
        writer = csv.writer(f)
        if write_h:
            writer.writerow(EXPECTED_CSV_HEADER)
        appended = 0
        for row in csv_rows:
            if (row[0], row[6], row[9]) not in existing_rows:
                writer.writerow(row)
                appended += 1
            else:
                logging.info(
                    f"Row for {row[0]} @ {row[6]} with {row[9]} VUs already exists. Skipping."
                )
    logging.info(f"Consolidated report saved to {output_path}")
    logging.info(f"Appended {appended} new rows to {args.output_csv}")


if __name__ == "__main__":
    main()
