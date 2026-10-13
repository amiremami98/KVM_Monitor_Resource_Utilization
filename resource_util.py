#!/usr/bin/env python3
import sys
import time
import subprocess
import re

def get_vm_stats(domain_name):
    """Extract VM domstats variables via virsh."""
    try:
        cmd = ["virsh", "domstats", "--cpu-total", "--balloon", domain_name]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, universal_newlines=True)
    except subprocess.CalledProcessError:
        return None

    stats = {}
    for line in out.splitlines():
        line = line.strip()
        if "=" in line:
            key, val = line.split("=", 1)
            try:
                stats[key] = int(val)
            except ValueError:
                stats[key] = val
    return stats

def get_vcpu_count(domain_name):
    """Retrieve the number of vCPUs for the virtual machine."""
    try:
        cmd = ["virsh", "vcpucount", "--active", "--live", domain_name]
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, universal_newlines=True)
        return int(out.strip())
    except Exception:
        return 1

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <domain_name_or_uuid_or_instance_id> [interval_sec]")
        print("Example: python3 resource_util.py instance-0000001a 1")
        sys.exit(1)

    domain = sys.argv[1]
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0

    stats = get_vm_stats(domain)
    if not stats:
        print(f"Error: VM '{domain}' not found or is not running.")
        sys.exit(1)

    vcpus = get_vcpu_count(domain)
    prev_cpu_time = stats.get("cpu.time", 0)
    prev_time = time.time()

    print(f"=== Monitoring VM: {domain} | vCPUs: {vcpus} ===")
    print("-" * 75)
    header = "{:<10} | {:<12} {:<12} | {:<12} {:<12} {:<10}"
    row_fmt = "{:<10} | {:<11.1f}% {:<11.1f}% | {:<10.1f}MB {:<10.1f}MB {:<9.1f}%"
    print(header.format("Time", "CPU (Total)", "CPU (Avg/Core)", "Host RSS", "Guest Max", "RAM %"))
    print("-" * 75)

    try:
        while True:
            time.sleep(interval)
            now = time.time()
            curr_stats = get_vm_stats(domain)
            
            if not curr_stats:
                print(f"VM {domain} stopped or unreachable.")
                break

            curr_cpu_time = curr_stats.get("cpu.time", 0)
            
            # Calculate CPU usage
            time_delta = now - prev_time
            cpu_delta_ns = curr_cpu_time - prev_cpu_time
            
            # Percentage relative to total host cores
            total_cpu_pct = (cpu_delta_ns / (time_delta * 1e9)) * 100.0
            # Average percentage per vCPU
            avg_vcpu_pct = total_cpu_pct / vcpus if vcpus > 0 else total_cpu_pct

            # Calculate RAM (libvirt values are in KiB)
            rss_mb = curr_stats.get("balloon.rss", 0) / 1024.0
            max_mb = curr_stats.get("balloon.maximum", curr_stats.get("balloon.current", 0)) / 1024.0
            
            # If guest balloon driver provides memory statistics
            unused_kb = curr_stats.get("balloon.unused", None)
            if unused_kb is not None:
                used_guest_mb = max_mb - (unused_kb / 1024.0)
                ram_pct = (used_guest_mb / max_mb * 100.0) if max_mb > 0 else 0.0
            else:
                # If guest stats are missing, use host RSS percentage
                ram_pct = (rss_mb / max_mb * 100.0) if max_mb > 0 else 0.0

            current_time = time.strftime('%H:%M:%S')
            print(row_fmt.format(
                current_time,
                total_cpu_pct,
                avg_vcpu_pct,
                rss_mb,
                max_mb,
                ram_pct
            ))

            prev_cpu_time = curr_cpu_time
            prev_time = now

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == '__main__':
    main()
