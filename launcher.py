import sys


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cpu-worker":
        from SpeakToBridge.cpu_worker import main
        raise SystemExit(main(sys.argv[2:]))
    if "--check-hardware" in sys.argv[1:]:
        from SpeakToBridge.diagnostics import main
        raise SystemExit(main([arg for arg in sys.argv[1:] if arg != "--check-hardware"]))
    # Record import failures too: app.run() configures logging too late for them.
    from SpeakToBridge.logging_utils import configure_logging
    configure_logging()
    try:
        from SpeakToBridge.app import run
        raise SystemExit(run())
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Application startup failed")
        raise
