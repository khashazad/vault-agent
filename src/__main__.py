import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="vault-agent")
    parser.add_argument("--port", type=int, default=3000)
    parser.add_argument("--env-file", type=str, default=None)
    args = parser.parse_args()

    if args.env_file:
        from dotenv import load_dotenv

        load_dotenv(args.env_file, override=True)

    uvicorn.run("src.server:app", host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
