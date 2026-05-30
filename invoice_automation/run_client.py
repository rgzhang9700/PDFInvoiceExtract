import argparse
from pathlib import Path

from app.runner import run_client


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--client-config",
        default="clients/sample_client/config.yaml",
        help="Path to client config YAML file"
    )
    args = parser.parse_args()

    run_client(Path(args.client_config))


if __name__ == "__main__":
    main()