# Changelog - Predictability Score™ SDK

All notable changes to the **Predictability Score™ SDK (Enterprise Edition)** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-02-05
### Added
- **Core Engine:** Initial release of the `fsr` module with the proprietary Predictability Score algorithm.
- **Sliding Window:** Added `sliding_window` module for temporal drift detection.
- **Performance:** Integrated `numba` JIT compilation for high-performance calculation.
- **Packaging:** Standardized `setup.py` configuration for `.whl` and `.tar.gz` distribution.
- **Documentation:** Added `SDK_README.md` with quickstart examples for Industrial and AI use cases.

### Security
- **Offline Mode:** SDK is configured to run 100% locally with no external API calls.
