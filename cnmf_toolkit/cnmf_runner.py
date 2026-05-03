
#!/usr/bin/env python3
"""
CNMF Runner Script

This script runs CNMF with different configurations using the CNMFManager.

Usage:
    python cnmf_runner.py /path/to/movie.tif
    python cnmf_runner.py /path/to/movie.tif --config greedy_roi_no_patches_config
    python cnmf_runner.py /path/to/movie.tif --also-corr-pnr
"""

import argparse
import os
import sys

# Ensure sibling modules (cnmf_manager, instrumented_cnmf, ...) are importable
# when this file is run as a script.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)

from cnmf_manager import CNMFManager


def main():
    parser = argparse.ArgumentParser(description="Run CNMF via CNMFManager")
    parser.add_argument("movie", help="Path to input TIFF movie file")
    parser.add_argument(
        "--config",
        default="greedy_roi_no_patches_config",
        help="Configuration name (default: greedy_roi_no_patches_config)",
    )
    parser.add_argument(
        "--also-corr-pnr",
        action="store_true",
        help="Also run corr_pnr_no_patches_config for comparison",
    )
    args = parser.parse_args()

    # Initialize the manager
    manager = CNMFManager()

    print("CNMF Runner")
    print("=" * 30)

    # List available configurations
    print("\nAvailable Configurations:")
    manager.list_configs()

    # Run primary config
    config_info_1 = manager.get_config(args.config)
    print(f"\n\nRunning with {config_info_1['name']}...")

    try:
        cnm_1, results_file_1 = manager.run_cnmf(
            config_name=args.config,
            movie_file=args.movie,
            enable_debug=True,
            save_results=True,
        )
        print(f"✅ {config_info_1['name']} completed. "
              f"Found {cnm_1.estimates.A.shape[1]} components")
    except Exception as e:
        print(f"❌ {config_info_1['name']} failed: {e}")
        import traceback
        traceback.print_exc()

    # Optionally run Correlation PNR
    if args.also_corr_pnr:
        config_name_2 = 'corr_pnr_no_patches_config'
        config_info_2 = manager.get_config(config_name_2)
        print(f"\n\nRunning with {config_info_2['name']}...")

        try:
            cnm_2, results_file_2 = manager.run_cnmf(
                config_name=config_name_2,
                movie_file=args.movie,
                enable_debug=True,
                save_results=True,
            )
            print(f"✅ {config_info_2['name']} completed. "
                  f"Found {cnm_2.estimates.A.shape[1]} components")
        except Exception as e:
            print(f"❌ {config_info_2['name']} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n✅ Analysis complete.")


if __name__ == "__main__":
    main()
