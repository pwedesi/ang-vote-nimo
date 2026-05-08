import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run multiple edge nodes for a fixed number of seconds."
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=2,
        help="Number of edge-node processes to start.",
    )
    parser.add_argument(
        "--seconds",
        type=int,
        default=30,
        help="How long to keep the edge nodes running.",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("API_URL", "http://localhost:8080/vote"),
        help="Vote API URL, including /vote.",
    )
    parser.add_argument(
        "--edge-script",
        default=str(Path(__file__).with_name("edge_node.py")),
        help="Path to the edge-node script.",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python executable used to start each edge node.",
    )
    parser.add_argument(
        "--edge-prefix",
        default="edge",
        help="Prefix used when assigning EDGE_ID values.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.nodes < 1:
        raise SystemExit("--nodes must be at least 1")
    if args.seconds < 1:
        raise SystemExit("--seconds must be at least 1")

    edge_script = Path(args.edge_script).resolve()
    if not edge_script.exists():
        raise SystemExit(f"Edge script not found: {edge_script}")

    processes = []
    print(
        f"Starting {args.nodes} edge nodes for {args.seconds}s against {args.api_url}",
        flush=True,
    )

    try:
        for index in range(1, args.nodes + 1):
            env = os.environ.copy()
            env["API_URL"] = args.api_url
            env["EDGE_ID"] = f"{args.edge_prefix}-{index}"
            process = subprocess.Popen(
                [args.python, str(edge_script)],
                env=env,
            )
            processes.append(process)
            print(f"Started {env['EDGE_ID']} with pid={process.pid}", flush=True)

        time.sleep(args.seconds)

    except KeyboardInterrupt:
        print("Interrupted. Stopping edge nodes...", flush=True)
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()

        deadline = time.time() + 5
        for process in processes:
            remaining = max(0, deadline - time.time())
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()

        print("All edge nodes stopped.", flush=True)


if __name__ == "__main__":
    main()
