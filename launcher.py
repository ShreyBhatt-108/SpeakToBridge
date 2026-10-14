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
        import time
        import_started = time.perf_counter()
        from SpeakToBridge.app import run
        import logging
        logging.getLogger(__name__).info(
            "GUI imports completed in %.3f seconds; torch=%s, ctranslate2=%s",
            time.perf_counter() - import_started, "torch" in sys.modules, "ctranslate2" in sys.modules)
        raise SystemExit(run())
    except Exception:
        import logging
        logging.getLogger(__name__).exception("Application startup failed")
        raise
