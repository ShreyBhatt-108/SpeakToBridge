import sys


if __name__ == "__main__":
    if "--check-hardware" in sys.argv[1:]:
        from SpeakToBridge.diagnostics import main
        raise SystemExit(main([arg for arg in sys.argv[1:] if arg != "--check-hardware"]))
    from SpeakToBridge.app import run
    raise SystemExit(run())
