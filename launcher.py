import sys


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cpu-worker":
        from SpeakToBridge.cpu_worker import main
        raise SystemExit(main(sys.argv[2:]))
    if "--check-hardware" in sys.argv[1:]:
        from SpeakToBridge.diagnostics import main
        raise SystemExit(main([arg for arg in sys.argv[1:] if arg != "--check-hardware"]))
    from SpeakToBridge.app import run
    raise SystemExit(run())
